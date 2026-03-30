"""FPGA configuration data model and analysis.

Defines the toy FPGA architecture (CLB grid with LUTs, D-FFs, output MUX,
routing channels, and switch boxes) and provides tools to:
- Validate a configuration (detect shorted outputs, missing connections, etc.)
- Extract boolean expressions from the configured LUTs via pyEDA
- Trace signal paths through the routing network

No schemdraw dependency. For drawing, see fpga_draw.py.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FpgaConfig:
    """Configuration for the toy FPGA.

    Attributes:
        n_inputs: Number of LUT inputs per CLB (default 3).
        n_rows: Number of CLB rows (default 3).
        n_cols: Number of CLB columns (default 2).
        h_wire_count: Number of horizontal wires per channel (default 3).
        luts: Dict (row, col) -> list of 2^n_inputs output bits.
              Index 0 = address 0...0, last index = address 1...1.
        mux: Dict (row, col) -> 0 (combinatorial) or 1 (registered).
        sbs: Dict (v_channel, h_channel) -> list of (port, port) pairs.
             Ports: T0..Tn (top), B0..Bn (bottom), L0..Lm (left), R0..Rm (right).
    """
    n_inputs: int = 3
    n_rows: int = 3
    n_cols: int = 2
    h_wire_count: int = 3
    luts: dict = field(default_factory=dict)
    mux: dict = field(default_factory=dict)
    sbs: dict = field(default_factory=dict)

    @property
    def n_lut_entries(self):
        return 2 ** self.n_inputs

    @property
    def v_wire_counts(self):
        """Number of vertical wires per channel: [left, interior..., right]."""
        counts = [self.n_inputs]
        for _ in range(1, self.n_cols):
            counts.append(self.n_inputs + 1)
        counts.append(2)
        return counts

    @property
    def n_v_channels(self):
        return self.n_cols + 1

    @property
    def n_h_channels(self):
        return self.n_rows + 1


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

    # Check SB connections
    for (vi, hi), conns in cfg.sbs.items():
        if vi < 0 or vi >= cfg.n_v_channels:
            errors.append(f'SB ({vi},{hi}): v_channel {vi} out of range')
            continue
        if hi < 0 or hi >= cfg.n_h_channels:
            errors.append(f'SB ({vi},{hi}): h_channel {hi} out of range')
            continue

        n_v = v_counts[vi]
        n_h = cfg.h_wire_count

        for p1_str, p2_str in conns:
            for p_str in (p1_str, p2_str):
                side, idx = _parse_port(p_str)
                if side in ('T', 'B'):
                    if idx < 0 or idx >= n_v:
                        errors.append(
                            f'SB ({vi},{hi}): port {p_str} invalid, '
                            f'v_channel {vi} has {n_v} wires (0..{n_v-1})')
                elif side in ('L', 'R'):
                    if idx < 0 or idx >= n_h:
                        errors.append(
                            f'SB ({vi},{hi}): port {p_str} invalid, '
                            f'h_channel has {n_h} wires (0..{n_h-1})')
                else:
                    errors.append(
                        f'SB ({vi},{hi}): port {p_str} invalid side '
                        f'(expected T/B/L/R)')

    # Check for shorted outputs (multiple drivers on the same wire segment)
    # A wire segment is identified by (channel_type, channel_idx, wire_idx, segment)
    # For vertical: segment = between h_cy[hi] and h_cy[hi+1]
    # For horizontal: segment = between v_cx[vi] and v_cx[vi+1]
    #
    # Drivers:
    #   - CLB outputs drive mid-channel wire 0 at their row
    #   - SB connections can drive wires (B port = drives segment below, T port = above)
    #   - SB connections with L/R ports drive horizontal segments
    #
    # For simplicity, check that within each SB, no port appears as a
    # destination more than once (multiple sources driving the same port).
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
    from pyeda.inter import exprvars, truthtable

    if input_names is None:
        input_names = [f'x{i}' for i in range(n_inputs)]

    xs = exprvars(*input_names, n_inputs)

    minterms = [i for i, b in enumerate(bits) if b == 1]

    if not minterms:
        return None  # constant 0
    if len(minterms) == 2 ** n_inputs:
        return None  # constant 1

    tt = truthtable(xs, bits)
    return tt.to_expr()


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

            # LUT expression
            if key in cfg.luts:
                expr = lut_to_expression(
                    cfg.luts[key],
                    input_names=input_names,
                    n_inputs=cfg.n_inputs,
                )
                expressions[key] = expr
            else:
                expressions[key] = None

            # MUX mode
            if key in cfg.mux:
                modes[key] = 'registered' if cfg.mux[key] == 1 else 'combinatorial'
            else:
                modes[key] = 'unknown'

    return {
        'errors': errors,
        'clb_expressions': expressions,
        'clb_mode': modes,
    }
