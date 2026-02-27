"""
Convert a truth table into WaveDrom JSON with dot-extended waves.
Uses 'l' for low, 'h' for high, and 'x' for unknown.

Features:
- Accepts truth as a bit string ('0','1','x','X') OR as an integer encoding the bitstring.
- pre_context/post_context: wrap-around context
- randomize: fully shuffle the displayed sequence (including context duplicates)
- seed: optional RNG seed for reproducible shuffles
- No clock (purely combinational visualization)
"""

import json
import random
from typing import Dict, List, Optional, Union

def _map_first_numeric_then_lh(raw: str) -> str:
    """
    Convert a raw per-step sequence of symbols in {'0','1','x'} into a WaveDrom
    sequence where the FIRST step stays numeric ('0'/'1'/'x'), and subsequent
    steps use 'l'/'h'/'x' with dot-extension for holds.

    Example:
      raw = '00110011' -> '0 0 1 . 0 0 1 1' (without spaces)
      after mapping with dots: '0 0 1 . 0 0 1 1' -> '001.0011'
      and with l/h for the rest: '0 0 h . l l h h' -> '0 0 h . l l h h'
      final: '00h.llhh' (dots inserted for holds)
    """
    if not raw:
        return ""

    # Helper to map 0/1/x to l/h/x for non-first positions
    def to_lh(c: str) -> str:
        if c == '0': return 'l'
        if c == '1': return 'h'
        return 'x'

    out = [raw[0]]  # first symbol remains numeric '0'/'1'/'x'
    # Build subsequent symbols with l/h/x and dot extension
    prev_symbol_numeric = raw[0]  # for comparing holds against raw input
    for i in range(1, len(raw)):
        curr_numeric = raw[i]
        # If numeric value didn't change, emit '.'
        if curr_numeric == prev_symbol_numeric:
            out.append('.')
        else:
            out.append(to_lh(curr_numeric))
            prev_symbol_numeric = curr_numeric
    return ''.join(out)

def _normalize_truth(truth: Union[str, int], steps: int) -> str:
    """
    Normalize truth into a '0'/'1'/'x' string of length `steps`.
    - str: must be length `steps` of 0/1/x/X.
    - int: formatted to exactly `steps` bits of 0/1 (no 'x').
    """
    if isinstance(truth, int):
        if truth < 0:
            raise ValueError("truth integer must be non-negative.")
        max_val = (1 << steps) - 1
        if truth > max_val:
            raise ValueError(
                f"truth integer {truth} requires more than {steps} bits. "
                f"Maximum allowed is {max_val} (binary length {steps})."
            )
        return format(truth, f'0{steps}b')
    clean = ''.join(ch for ch in str(truth) if not ch.isspace())
    if not all(c in '01xX' for c in clean):
        raise ValueError("truth string must contain only '0', '1', 'x', or 'X' (whitespace is ignored).")
    if len(clean) != steps:
        raise ValueError(f"truth string length must be {steps}; got {len(clean)}.")
    # Normalize X to x
    return ''.join('x' if c in 'xX' else c for c in clean)

def truth_table_to_wavedrom(
    inputs: List[str],
    output_name: str,
    truth: Union[str, int],
    msb_first: bool = True,
    pre_context: int = 0,
    post_context: int = 0,
    randomize: bool = False,
    seed: Optional[int] = None,
    first_step_numeric: bool = True
) -> Dict:
    """
    Build WaveDrom JSON for a combinational truth table across all input combinations.

    Features:
      - inputs: list of input signal names
      - output_name: name of the output signal
      - truth: str of length 2^n ('0','1','x' allowed) or int encoding bits
      - msb_first: whether inputs[0] maps to MSB of the combination index
      - pre_context/post_context: wrap-around context
      - randomize (+seed): shuffle displayed sequence incl. context duplicates
      - first_step_numeric: if True, the very first step is '0'/'1'/'x';
                            all subsequent steps are 'l'/'h'/'x' with dots
    """
    n = len(inputs)
    if n <= 0:
        raise ValueError("inputs list must not be empty.")
    steps = 1 << n

    if pre_context < 0 or post_context < 0:
        raise ValueError("pre_context and post_context must be non-negative integers.")

    truth_bits = _normalize_truth(truth, steps)

    # Build displayed index sequence with wrap-around (includes duplicates from context)
    idx_seq = [((t % steps) + steps) % steps for t in range(-pre_context, steps + post_context)]

    # Optional randomization of display order
    if randomize:
        rng = random.Random(seed)
        rng.shuffle(idx_seq)

    # Construct raw sequences (in numeric '0'/'1'/'x' domain)
    input_waves_raw = ['' for _ in range(n)]
    for idx in idx_seq:
        bits = format(idx, f'0{n}b')  # MSB ... LSB
        for i in range(n):
            b = bits[i] if msb_first else bits[n - 1 - i]
            input_waves_raw[i] += b  # numeric '0'/'1'

    out_wave_raw = ''.join(truth_bits[idx] for idx in idx_seq)  # numeric '0'/'1'/'x'

    # Map to WaveDrom waves:
    # - If first_step_numeric=True: first char numeric, rest l/h/x with dots
    # - Else: all l/h/x with dots (the previous behavior)
    def _to_wave(raw: str) -> str:
        if first_step_numeric:
            return _map_first_numeric_then_lh(raw)
        else:
            # previous l/h mapping with dots for holds
            if not raw:
                return ""
            def to_lh(c: str) -> str:
                if c == '0': return 'l'
                if c == '1': return 'h'
                return 'x'
            mapped = [to_lh(raw[0])]
            for i in range(1, len(raw)):
                mapped.append('.' if raw[i] == raw[i-1] else to_lh(raw[i]))
            return ''.join(mapped)

    input_waves = [_to_wave(w) for w in input_waves_raw]
    out_wave = _to_wave(out_wave_raw)

    signals = [{"name": name, "wave": wave} for name, wave in zip(inputs, input_waves)]
    signals.append({"name": output_name, "wave": out_wave})

    return {
        "signal": signals,
        "note": (
            f"Base order: binary ascending 0..{steps - 1}, "
            f"{'MSB' if msb_first else 'LSB'} corresponds to inputs[0]. "
            f"States: first={'numeric' if first_step_numeric else 'l/h'}, then l/h/x with dots. "
            f"Context: pre={pre_context}, post={post_context}. "
            f"Display: {'randomized' if randomize else 'sequential'}. "
            f"Truth source: {'int' if isinstance(truth, int) else 'string'}."
        )}

def set_linewidth(wavedrom: dict, lw: int = 2) -> dict:
    """
    Set the line width for all signals in a WaveDrom JSON dict.

    Parameters
    ----------
    wavedrom : dict
        WaveDrom JSON object with a 'signal' list.
    lw : int
        Line width to apply to all signals.

    Returns
    -------
    dict
        A new WaveDrom dict with 'lw' added to each signal.
    """
    if "signal" not in wavedrom or not isinstance(wavedrom["signal"], list):
        raise ValueError("Invalid WaveDrom object: missing 'signal' list.")

    # Make a copy so we don't mutate the original
    out = {**wavedrom, "signal": []}

    for sig in wavedrom["signal"]:
        s = dict(sig)      # copy one signal
        s["lw"] = lw       # set line width
        out["signal"].append(s)

    return out



if __name__ == "__main__":
    # --- Examples ---
    inputs = ['x0', 'x1', 'x2']
    output_name = 'y'

    # Example A: truth as STRING (length 8 for 3 inputs)
    wd_str = truth_table_to_wavedrom(
        inputs, output_name, truth="00101100",
        msb_first=True, pre_context=2, post_context=2,
        randomize=False
    )
    print("From string:\n", json.dumps(wd_str, indent=2), "\n")

    # Example B: truth as INTEGER (same as 0b00101100 == 44)
    wd_int = truth_table_to_wavedrom(
        inputs, output_name, truth=0b00101100,
        msb_first=True, pre_context=2, post_context=2,
        randomize=True, seed=123
    )