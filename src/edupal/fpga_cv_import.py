"""CircuitVerse JSON to FpgaConfig converter.

Reads a CircuitVerse circuit JSON file, extracts the FPGA element
configuration, and converts it to an FpgaConfig for edupal/schemdraw
rendering.

Usage:
    from edupal.fpga_cv_import import cv_to_fpga_config
    cfg = cv_to_fpga_config('circuit.json')
"""

import json

from .fpga import FpgaConfig


def _find_fpga_element(data):
    """Find the first FPGA element in a CircuitVerse JSON structure.

    Searches through scopes for an element with FPGA constructor parameters
    (7-element array: rows, cols, luts, muxSel, preSel, clrSel, sbMuxes).

    Returns:
        The FPGA element dict, or None if not found.
    """
    # Try direct top-level access
    if 'FPGA' in data and isinstance(data['FPGA'], list) and data['FPGA']:
        return data['FPGA'][0]

    # Search through scopes (CircuitVerse nests elements inside scope dicts)
    scopes = data.get('scopes', [])
    if not isinstance(scopes, list):
        scopes = [scopes]
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        # Check for FPGA key directly in scope
        fpga_list = scope.get('FPGA', [])
        if isinstance(fpga_list, list) and fpga_list:
            return fpga_list[0]
        # Fallback: search all lists for FPGA-shaped elements
        for key, val in scope.items():
            if isinstance(val, list):
                for elem in val:
                    if not isinstance(elem, dict):
                        continue
                    if elem.get('objectType') == 'FPGA':
                        return elem
                    cd = elem.get('customData', {})
                    params = cd.get('constructorParamaters', [])
                    if isinstance(params, list) and len(params) == 7:
                        return elem

    return None


def _convert_sb_muxes(sb_muxes_raw, cfg):
    """Convert CircuitVerse SB mux encoding to (port, port) pairs.

    CircuitVerse stores each output port's mux select index (1-indexed into
    the input port list, 0 = not connected). This reconstructs the input
    port ordering via cfg.sb_ports() and maps each non-zero select to a
    (input_port, output_port) connection pair.
    """
    sbs = {}
    for key_str, mux_dict in sb_muxes_raw.items():
        vi, hi = map(int, key_str.split(','))
        inputs, outputs, _ = cfg.sb_ports(vi, hi)

        conns = []
        for port_name, sel_idx in mux_dict.items():
            if sel_idx == 0:
                continue  # not connected
            if sel_idx < 1 or sel_idx > len(inputs):
                raise ValueError(
                    f'SB ({vi},{hi}) port {port_name}: selIdx {sel_idx} '
                    f'out of range (1..{len(inputs)})')
            in_port = inputs[sel_idx - 1]
            conns.append((in_port['name'], port_name))

        if conns:
            sbs[(vi, hi)] = conns

    return sbs


def cv_to_fpga_config(circuit_json_path, n_inputs=3):
    """Read a CircuitVerse circuit JSON and extract the FPGA configuration.

    Args:
        circuit_json_path: Path to the CircuitVerse JSON file.
        n_inputs: Number of LUT inputs (default 3, must match the CV element).

    Returns:
        FpgaConfig instance.

    Raises:
        ValueError: If no FPGA element is found in the JSON.
    """
    with open(circuit_json_path) as f:
        data = json.load(f)

    fpga_elem = _find_fpga_element(data)
    if fpga_elem is None:
        raise ValueError('No FPGA element found in CircuitVerse JSON')

    params = fpga_elem['customData']['constructorParamaters']
    rows = params[0]
    cols = params[1]
    luts_raw = params[2]      # {"r,c": [8 bits]}
    mux_sel_raw = params[3]   # {"r,c": 0|1}
    # params[4] = preSel, params[5] = clrSel -- ignored (no reset logic)
    sb_muxes_raw = params[6]  # {"vi,hi": {"portName": selIdx}}

    # Convert LUTs: "r,c" string keys -> (int, int) tuple keys
    luts = {}
    for k, v in luts_raw.items():
        luts[tuple(map(int, k.split(',')))] = v

    # Convert MUX select
    mux = {}
    for k, v in mux_sel_raw.items():
        mux[tuple(map(int, k.split(',')))] = v

    # Create config with empty SBs first (needed for sb_ports())
    cfg = FpgaConfig(
        n_inputs=n_inputs,
        n_rows=rows,
        n_cols=cols,
        luts=luts,
        mux=mux,
        sbs={},
    )

    # Convert SB mux encoding to connection pairs
    cfg.sbs = _convert_sb_muxes(sb_muxes_raw, cfg)

    return cfg
