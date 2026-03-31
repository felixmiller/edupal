"""FPGA configuration data model and analysis.

Defines the toy FPGA architecture (CLB grid with LUTs, D-FFs, output MUX,
routing channels, and switch boxes) and provides tools to:
- Validate a configuration (detect shorted outputs, missing connections, etc.)
- Extract boolean expressions from the configured LUTs via pyEDA
- Trace signal paths through the routing network

Vertical wire layout per channel:
  Left (vi=0):     w0=SB-down, w1=SB-up, w2..w(1+n)=CLB inputs
  Interior:        w0=CLB output, w1=SB-down, w2=SB-up, w3..w(2+n)=CLB inputs
  Right (vi=cols): w0=CLB output

Horizontal wires: 4 per channel, interleaved direction in CircuitVerse
(even=rightward, odd=leftward). Bidirectional in the paper model.

No schemdraw dependency. For drawing, see fpga_draw.py.
"""

from dataclasses import dataclass, field


@dataclass
class FpgaConfig:
    """Configuration for the toy FPGA.

    Attributes:
        n_inputs: Number of LUT inputs per CLB (default 3).
        n_rows: Number of CLB rows (default 3).
        n_cols: Number of CLB columns (default 2).
        h_wire_count: Number of horizontal wires per channel (default 4).
        luts: Dict (row, col) -> list of 2^n_inputs output bits.
              Index 0 = address 0...0, last index = address 1...1.
        mux: Dict (row, col) -> 0 (combinatorial) or 1 (registered).
        sbs: Dict (v_channel, h_channel) -> list of (port, port) pairs.
             Ports: T0..Tn (top), B0..Bn (bottom), L0..Lm (left), R0..Rm (right).
    """
    n_inputs: int = 3
    n_rows: int = 3
    n_cols: int = 2
    h_wire_count: int = 4
    luts: dict = field(default_factory=dict)
    mux: dict = field(default_factory=dict)
    sbs: dict = field(default_factory=dict)

    @property
    def n_lut_entries(self):
        return 2 ** self.n_inputs

    @property
    def v_wire_counts(self):
        """Number of vertical wires per channel: [left, interior..., right].

        Left:     2 (SB-routing) + n_inputs (CLB inputs)
        Interior: 1 (CLB output) + 2 (SB-routing) + n_inputs (CLB inputs)
        Right:    1 (CLB output only)
        """
        counts = [2 + self.n_inputs]
        for _ in range(1, self.n_cols):
            counts.append(1 + 2 + self.n_inputs)
        counts.append(1)
        return counts

    @property
    def n_v_channels(self):
        return self.n_cols + 1

    @property
    def n_h_channels(self):
        return self.n_rows + 1

    def clb_input_wire_offset(self, vi):
        """Return the wire index of the first CLB input in vertical channel vi.

        Left channel: CLB inputs start at wire 2.
        Interior channels: CLB inputs start at wire 3.
        Right channel: no CLB inputs.
        """
        if vi == 0:
            return 2
        elif vi < self.n_cols:
            return 3
        else:
            return None  # rightmost has no CLB inputs

    def sb_ports(self, vi, hi):
        """Return port metadata for switch box at (vi, hi).

        Matches the CircuitVerse _sbPorts() logic exactly so that
        mux select indices map correctly during import.

        Returns:
            (inputs, outputs, all_ports) where each is a list of dicts
            with keys: name, side, wireIdx, isOutput.
        """
        nv = self.v_wire_counts[vi]
        is_top = hi == 0
        is_bot = hi == self.n_rows
        is_left = vi == 0
        is_right = vi == self.n_cols

        def v_wire_is_output(w, side):
            if is_right:
                return False  # wire 0 = CLB output, always input to SB
            if is_left:
                if w >= 2:
                    return True   # CLB inputs: always outputs from SB
                if w == 0:
                    return side == 'B'  # SB-down: top=in, bottom=out
                if w == 1:
                    return side == 'T'  # SB-up: top=out, bottom=in
            else:
                if w == 0:
                    return False  # CLB output: always input to SB
                if w >= 3:
                    return True   # CLB inputs: always outputs from SB
                if w == 1:
                    return side == 'B'  # SB-down: top=in, bottom=out
                if w == 2:
                    return side == 'T'  # SB-up: top=out, bottom=in
            return False

        ports = []

        # Top vertical ports
        if not is_top:
            for w in range(nv):
                ports.append(dict(name=f'T{w}', side='T', wireIdx=w,
                                  isOutput=v_wire_is_output(w, 'T')))
        elif not is_left and not is_right:
            ports.append(dict(name='T0', side='T', wireIdx=0, isOutput=False))

        # Bottom vertical ports
        if not is_bot:
            for w in range(nv):
                ports.append(dict(name=f'B{w}', side='B', wireIdx=w,
                                  isOutput=v_wire_is_output(w, 'B')))
        elif not is_left and not is_right:
            ports.append(dict(name='B0', side='B', wireIdx=0, isOutput=True))

        # Left horizontal ports
        if is_left:
            ports.append(dict(name='L0', side='L', wireIdx=0, isOutput=False))
        else:
            for w in range(self.h_wire_count):
                ports.append(dict(name=f'L{w}', side='L', wireIdx=w,
                                  isOutput=(w % 2 == 1)))

        # Right horizontal ports
        if is_right:
            ports.append(dict(name='R0', side='R', wireIdx=0, isOutput=True))
        else:
            for w in range(self.h_wire_count):
                ports.append(dict(name=f'R{w}', side='R', wireIdx=w,
                                  isOutput=(w % 2 == 0)))

        inputs = [p for p in ports if not p['isOutput']]
        outputs = [p for p in ports if p['isOutput']]
        return inputs, outputs, ports


def _parse_port(port_str):
    """Parse port string like 'T0' into (side, index)."""
    return port_str[0], int(port_str[1:])


def validate_config(cfg):
    """Validate an FPGA configuration and return a list of error strings.

    Checks:
    - LUT entries have correct length
    - LUT bits are 0 or 1
    - MUX values are 0 or 1
    - SB port names are valid for their switch box position
    - No two outputs drive the same wire segment (shorted outputs)

    Returns:
        List of error message strings. Empty list means valid.
    """
    errors = []
    n_entries = cfg.n_lut_entries
    v_counts = cfg.v_wire_counts

    # Check LUTs
    for (r, c), bits in cfg.luts.items():
        if r < 0 or r >= cfg.n_rows or c < 0 or c >= cfg.n_cols:
            errors.append(f'LUT ({r},{c}): position out of range')
            continue
        if len(bits) != n_entries:
            errors.append(
                f'LUT ({r},{c}): expected {n_entries} entries, got {len(bits)}')
        for i, b in enumerate(bits):
            if b not in (0, 1):
                errors.append(f'LUT ({r},{c})[{i}]: invalid bit value {b}')

    # Check MUX
    for (r, c), sel in cfg.mux.items():
        if r < 0 or r >= cfg.n_rows or c < 0 or c >= cfg.n_cols:
            errors.append(f'MUX ({r},{c}): position out of range')
        if sel not in (0, 1):
            errors.append(f'MUX ({r},{c}): invalid select value {sel}')

    # Check SB connections: validate port names against sb_ports()
    for (vi, hi), conns in cfg.sbs.items():
        if vi < 0 or vi >= cfg.n_v_channels:
            errors.append(f'SB ({vi},{hi}): v_channel {vi} out of range')
            continue
        if hi < 0 or hi >= cfg.n_h_channels:
            errors.append(f'SB ({vi},{hi}): h_channel {hi} out of range')
            continue

        _, _, all_ports = cfg.sb_ports(vi, hi)
        valid_names = {p['name'] for p in all_ports}

        for p1_str, p2_str in conns:
            for p_str in (p1_str, p2_str):
                if p_str not in valid_names:
                    errors.append(
                        f'SB ({vi},{hi}): port {p_str} not valid at this '
                        f'position (valid: {sorted(valid_names)})')

    # Check for shorted outputs (multiple sources driving the same port)
    for (vi, hi), conns in cfg.sbs.items():
        dest_counts = {}
        for _, p2_str in conns:
            dest_counts[p2_str] = dest_counts.get(p2_str, 0) + 1
        for port, count in dest_counts.items():
            if count > 1:
                errors.append(
                    f'SB ({vi},{hi}): port {port} driven by {count} sources '
                    f'(possible short)')

    return errors


def lut_to_expression(bits, input_names=None, n_inputs=3):
    """Convert a LUT truth table to a pyEDA boolean expression.

    Requires pyeda (imported on first call).

    Args:
        bits: List of 2^n_inputs output bits (index 0 = all inputs low).
        input_names: List of input variable name strings (default: x0..xn).
        n_inputs: Number of inputs (default 3).

    Returns:
        pyEDA Expression, or None if the LUT is all-zero or all-one.
    """
    from pyeda.inter import exprvar, truthtable, espresso_tts

    if input_names is None:
        input_names = [f'x{i}' for i in range(n_inputs)]

    xs = tuple(exprvar(name) for name in input_names)

    minterms = [i for i, b in enumerate(bits) if b == 1]

    if not minterms:
        return None  # constant 0
    if len(minterms) == 2 ** n_inputs:
        return None  # constant 1

    tt = truthtable(xs, bits)
    return espresso_tts(tt)[0]


def analyze_config(cfg, input_names=None):
    """Analyze a full FPGA configuration and return boolean expressions.

    Args:
        cfg: FpgaConfig instance.
        input_names: Optional list of n_inputs variable names for LUT inputs.

    Returns:
        Dict with:
        - 'errors': list of validation error strings
        - 'clb_expressions': dict (row, col) -> pyEDA Expression or None
        - 'clb_mode': dict (row, col) -> 'registered' or 'combinatorial'
    """
    errors = validate_config(cfg)

    expressions = {}
    modes = {}

    for r in range(cfg.n_rows):
        for c in range(cfg.n_cols):
            key = (r, c)

            if key in cfg.luts:
                expr = lut_to_expression(
                    cfg.luts[key],
                    input_names=input_names,
                    n_inputs=cfg.n_inputs,
                )
                expressions[key] = expr
            else:
                expressions[key] = None

            if key in cfg.mux:
                modes[key] = 'registered' if cfg.mux[key] == 1 else 'combinatorial'
            else:
                modes[key] = 'unknown'

    return {
        'errors': errors,
        'clb_expressions': expressions,
        'clb_mode': modes,
    }
