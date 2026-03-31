"""FPGA schemdraw drawing functions.

Renders the toy FPGA architecture using schemdraw's SVG backend.
Requires: schemdraw (with Felix's hm-mods fork for IEC flip-flops).

Usage:
    from edupal.fpga import FpgaConfig
    from edupal.fpga_draw import draw_fpga

    cfg = FpgaConfig(n_inputs=3, n_rows=3, n_cols=2, luts={...}, ...)
    draw_fpga(cfg, filename='fpga.svg', base_fig=False)
"""

import schemdraw
import schemdraw.elements as elm
import schemdraw.flow as flow
from schemdraw.elements.intcircuits import IcPin
from schemdraw.segments import SegmentBezier
from schemdraw.util import Point

from .fpga import FpgaConfig

# Drawing constants
unit = 1
linedist = unit / 2

# LUT cell dimensions
row_h = 0.5
bit_w = 0.45
addr_w = 0.65


def make_clb(n_inputs=3):
    """Build a single CLB as a reusable schemdraw.Drawing.

    Anchors: in0..in{n_inputs-1} (left), out (right), CLK (left),
             config_sb (MUX select box top), config_sb_center (box center),
             lut_bit_0..lut_bit_{2^n-1} (NW corner of each bit cell).
    """
    n_rows = 2 ** n_inputs
    lut_total_h = n_rows * row_h
    lut_total_w = addr_w + bit_w
    in_lead = linedist
    in_spacing = lut_total_h / (n_inputs + 1) / 2
    lut_box_pad = 0.1

    # Address weight labels: MSB first (e.g., 4, 2, 1 for 3 inputs)
    addr_weights = [2 ** (n_inputs - 1 - i) for i in range(n_inputs)]

    with schemdraw.Drawing(show=False, fontsize=12, unit=unit, lw=1) as dcell:
        origin = dcell.here

        # LUT truth table
        for row in range(n_rows):
            row_top_y = origin.y - row * row_h
            dcell.here = Point((origin.x, row_top_y))
            flow.Box(w=addr_w, h=row_h, lw=0.5).anchor('NW').label(
                format(row, f'0{n_inputs}b'), fontsize=11)
            dcell.here = Point((origin.x + addr_w, row_top_y))
            flow.Box(w=bit_w, h=row_h, lw=0.5).anchor('NW')
            dcell.set_anchor(f'lut_bit_{row}')

        # LUT outer box
        dcell.here = Point((origin.x - lut_box_pad, origin.y + lut_box_pad))
        flow.Box(w=lut_total_w + 2 * lut_box_pad,
                 h=lut_total_h + 2 * lut_box_pad,
                 lw=1).anchor('NW').label('LUT', loc='top', ofst=(0, 0.05))

        lut_mid_y = origin.y - lut_total_h / 2
        lut_right_x = origin.x + lut_total_w + lut_box_pad

        # Input lead lines with address weight labels
        for i in range(n_inputs):
            y_in = origin.y - (i + 1) * in_spacing
            dcell.here = Point((origin.x - in_lead, y_in))
            dcell.set_anchor(f'in{i}')
            elm.Line().right(in_lead - lut_box_pad).label(
                str(addr_weights[i]), loc='left', ofst=(0, 0.12), fontsize=9)

        # LUT output -> fork
        dcell.here = Point((lut_right_x, lut_mid_y))
        elm.Line().right(2 * linedist)
        fork_pt = dcell.here
        elm.Dot()

        # D Flip-Flop
        ff = elm.IecDFlipFlop(
            qbar=False, nameqpin='').right().anchor('D').label(
                'clk', loc='CLK')

        # Output MUX
        mux_pins = [
            IcPin('1', anchorname='in1', side='left'),
            IcPin('0', anchorname='in0', side='left'),
            IcPin('', anchorname='out', side='right'),
            IcPin('', anchorname='sel', side='bottom'),
        ]
        mux = elm.Multiplexer(
            pins=mux_pins, size=(0.75, 1.25)).right().at(
                ff.Q).anchor('in1').side('L', spacing=1)

        # Combinatorial bypass: fork -> MUX.in0
        dcell.here = fork_pt
        elm.Line().toy(mux.in0.y)
        elm.Line().tox(mux.in0.x)

        # CLB output
        out_line = elm.Line().at(mux.out).right(linedist)
        dcell.here = out_line.end
        dcell.set_anchor('out')

        # CLK anchor
        dcell.here = ff.CLK
        dcell.set_anchor('CLK')

        # MUX select config bit box
        flow.Box(w=0.5, h=0.5).at(mux.sel).anchor('N')
        dcell.here = mux.sel
        dcell.set_anchor('config_sb')
        dcell.here = Point((mux.sel.x, mux.sel.y - 0.25))
        dcell.set_anchor('config_sb_center')

        # CLB dashed border
        clb_pad = 0.5
        border_left = origin.x - 0.3
        border_right = mux.out.x + 0.15
        border_top = origin.y + lut_box_pad + clb_pad
        border_bot = origin.y - lut_total_h - lut_box_pad - clb_pad
        border_w = border_right - border_left
        border_h = border_top - border_bot

        dcell.here = Point((border_left, border_top))
        flow.Box(w=border_w, h=border_h, lw=1, ls='--').anchor('NW').label(
            'CLB', loc='top', ofst=(0, 0.05))

    return dcell


def draw_fpga(cfg, filename='fpga.svg', base_fig=False):
    """Draw a complete FPGA figure.

    Args:
        cfg: FpgaConfig instance.
        filename: Output SVG file path.
        base_fig: If True, omit the configuration overlay (blank for exercises).
    """
    n_inputs = cfg.n_inputs
    n_clb_rows = cfg.n_rows
    n_clb_cols = cfg.n_cols
    h_wire_count = cfg.h_wire_count

    clb_cell = make_clb(n_inputs=n_inputs)
    bb = clb_cell.get_bbox()

    # Routing parameters
    wire_pitch = 0.4
    sb_pad = 0.3
    ch_gap = 0.5
    stub_len = 0.9

    v_wire_counts = cfg.v_wire_counts

    # CLB pin offsets
    in_dx = clb_cell.anchors['in0'].x
    out_dx = clb_cell.anchors['out'].x
    in_dy = [clb_cell.anchors[f'in{i}'].y for i in range(n_inputs)]
    out_dy = clb_cell.anchors['out'].y

    # Bundle widths and SB size
    v_bw = [(n - 1) * wire_pitch for n in v_wire_counts]
    h_bw = (h_wire_count - 1) * wire_pitch
    sb = max(max(v_bw), h_bw) + 2 * sb_pad

    # X layout: SB right edge aligns with CLB left edge, CLB right with next SB left
    v_cx = [0.0]
    clb_ox = []
    for c in range(n_clb_cols):
        clb_ox.append(v_cx[-1] + sb / 2 - bb.xmin)
        v_cx.append(clb_ox[-1] + bb.xmax + sb / 2)

    # Y layout
    h_cy = [0.0]
    clb_oy = []
    for r in range(n_clb_rows):
        clb_oy.append(h_cy[-1] - sb / 2 - ch_gap - bb.ymax)
        h_cy.append(clb_oy[-1] + bb.ymin - ch_gap - sb / 2)

    # Check for top/bottom I/O ports (non-corner interior SBs exist)
    has_top_io = n_clb_cols > 1
    has_bot_io = n_clb_cols > 1

    with schemdraw.Drawing(file=filename, show=False, fontsize=10, unit=unit, lw=1) as d:

        # Place CLBs
        clbs = {}
        for r in range(n_clb_rows):
            for c in range(n_clb_cols):
                clbs[(r, c)] = elm.ElementDrawing(clb_cell).at(
                    (clb_ox[c], clb_oy[r]))

        # Switch boxes
        for vcx in v_cx:
            for hcy in h_cy:
                d.here = Point((vcx - sb / 2, hcy + sb / 2))
                flow.Box(w=sb, h=sb, lw=0.5).anchor('NW')

        # Vertical wire segments
        for vi, vcx in enumerate(v_cx):
            n_w = v_wire_counts[vi]
            bw = v_bw[vi]
            for w in range(n_w):
                wx = vcx - bw / 2 + w * wire_pitch
                for hi in range(len(h_cy) - 1):
                    y_top = h_cy[hi] - sb / 2
                    y_bot = h_cy[hi + 1] + sb / 2
                    elm.Line().at((wx, y_top)).down(y_top - y_bot)

        # Horizontal wire segments
        for hi, hcy in enumerate(h_cy):
            for w in range(h_wire_count):
                wy = hcy + h_bw / 2 - w * wire_pitch
                for vi in range(len(v_cx) - 1):
                    x_left = v_cx[vi] + sb / 2
                    x_right = v_cx[vi + 1] - sb / 2
                    elm.Line().at((x_left, wy)).right(x_right - x_left)

        # ── I/O ports ─────────────────────────────────────────
        pin_idx = 0

        # Left side (one per H channel)
        for hi, hcy in enumerate(h_cy):
            wy = hcy
            elm.Line().at(
                (v_cx[0] - sb / 2 - stub_len, wy)).right(stub_len)
            elm.Label().at(
                (v_cx[0] - sb / 2 - stub_len, wy)).label(
                    f'$\\mathrm{{P_{{{pin_idx}}}}}$', loc='top', fontsize=12)
            pin_idx += 1

        # Top edge: inputs on non-corner interior SBs
        for vi in range(1, len(v_cx) - 1):
            vcx = v_cx[vi]
            elm.Line().at((vcx, h_cy[0] + sb / 2)).up(stub_len)
            elm.Label().at(
                (vcx, h_cy[0] + sb / 2 + stub_len)).label(
                    f'$\\mathrm{{P_{{{pin_idx}}}}}$', loc='top', fontsize=12)
            pin_idx += 1

        # Right side (one per H channel)
        for hi, hcy in enumerate(h_cy):
            wy = hcy
            elm.Line().at(
                (v_cx[-1] + sb / 2, wy)).right(stub_len)
            elm.Label().at(
                (v_cx[-1] + sb / 2 + stub_len, wy)).label(
                    f'$\\mathrm{{P_{{{pin_idx}}}}}$', loc='top', fontsize=12)
            pin_idx += 1

        # Bottom edge: non-corner interior SBs
        for vi in range(1, len(v_cx) - 1):
            vcx = v_cx[vi]
            elm.Line().at(
                (vcx, h_cy[-1] - sb / 2)).down(stub_len)
            elm.Label().at(
                (vcx, h_cy[-1] - sb / 2 - stub_len)).label(
                    f'$\\mathrm{{P_{{{pin_idx}}}}}$', loc='bottom', fontsize=12)
            pin_idx += 1

        # ── FPGA outer border ─────────────────────────────────
        fpga_pad = 0.4
        fpga_left = v_cx[0] - sb / 2 - fpga_pad
        fpga_right = v_cx[-1] + sb / 2 + fpga_pad
        fpga_top = h_cy[0] + sb / 2 + fpga_pad
        fpga_bot = h_cy[-1] - sb / 2 - fpga_pad
        d.here = Point((fpga_left, fpga_top))
        flow.Box(w=fpga_right - fpga_left, h=fpga_top - fpga_bot,
                 lw=2).anchor('NW')

        # ── Fixed connections: vertical wires <-> CLB pins ────
        for r in range(n_clb_rows):
            cy = clb_oy[r]
            for vi in range(len(v_cx)):
                bw = v_bw[vi]
                inp_off = cfg.clb_input_wire_offset(vi)

                if vi == 0:
                    # Left channel: CLB inputs on wires inp_off..inp_off+n-1
                    for i in range(n_inputs):
                        wx = v_cx[0] - bw / 2 + (inp_off + i) * wire_pitch
                        pin_x = clb_ox[0] + in_dx
                        pin_y = cy + in_dy[i]
                        elm.Dot(radius=0.06).at((wx, pin_y))
                        elm.Line().at((wx, pin_y)).right(pin_x - wx)

                elif vi <= n_clb_cols - 1:
                    # Interior: wire 0 = CLB output, wires inp_off.. = CLB inputs
                    wx0 = v_cx[vi] - bw / 2
                    pin_x = clb_ox[vi - 1] + out_dx
                    pin_y = cy + out_dy
                    elm.Line().at((pin_x, pin_y)).right(wx0 - pin_x)
                    elm.Dot(radius=0.06).at((wx0, pin_y))

                    for i in range(n_inputs):
                        wx = v_cx[vi] - bw / 2 + (inp_off + i) * wire_pitch
                        pin_x = clb_ox[vi] + in_dx
                        pin_y = cy + in_dy[i]
                        elm.Dot(radius=0.06).at((wx, pin_y))
                        elm.Line().at((wx, pin_y)).right(pin_x - wx)

                else:
                    # Right channel: wire 0 = CLB output
                    wx0 = v_cx[vi] - bw / 2
                    pin_x = clb_ox[vi - 1] + out_dx
                    pin_y = cy + out_dy
                    elm.Line().at((pin_x, pin_y)).right(wx0 - pin_x)
                    elm.Dot(radius=0.06).at((wx0, pin_y))

        # Apply configuration overlay
        if not base_fig:
            _draw_config(d, cfg, clbs, v_cx, h_cy, v_bw, h_bw,
                         sb, wire_pitch)


def _draw_config(d, cfg, clbs, v_cx, h_cy, v_bw, h_bw, sb, wire_pitch):
    """Draw the configuration overlay (LUT bits, MUX select, SB connections)."""

    # LUT contents
    for (r, c), bits in cfg.luts.items():
        ed = clbs[(r, c)]
        for i, bit in enumerate(bits):
            ax = getattr(ed, f'lut_bit_{i}')
            cx = ax.x + bit_w / 2
            cy = ax.y - row_h / 2
            d.here = Point((cx, cy))
            flow.Box(w=0.01, h=0.01).anchor('center').color('white').label(
                str(bit), color='black')

    # MUX select
    for (r, c), sel in cfg.mux.items():
        ed = clbs[(r, c)]
        d.here = ed.config_sb_center
        flow.Box(w=0.01, h=0.01).anchor('center').color('white').label(
            str(sel), color='black')

    # Switch box connections
    n_v_ch = cfg.n_v_channels
    n_h_ch = cfg.n_h_channels

    def sb_port_pos(vi, hi, port):
        """Return (x, y) of a named port on an SB edge.

        Edge SBs with a single I/O port (L0 on left, R0 on right,
        T0 on top non-corner, B0 on bottom non-corner) are centered
        in the SB rather than placed at the first wire position.
        """
        vcx, hcy = v_cx[vi], h_cy[hi]
        side, idx = port[0], int(port[1:])

        if side in ('T', 'B'):
            # Top-edge non-corner or bottom-edge non-corner: single centered port
            if (side == 'T' and hi == 0 and 0 < vi < n_v_ch - 1) or \
               (side == 'B' and hi == n_h_ch - 1 and 0 < vi < n_v_ch - 1):
                px = vcx
            else:
                bw = v_bw[vi]
                px = vcx - bw / 2 + idx * wire_pitch
            py = hcy + sb / 2 if side == 'T' else hcy - sb / 2
        else:
            px = vcx - sb / 2 if side == 'L' else vcx + sb / 2
            # Left-edge or right-edge: single centered port
            if (side == 'L' and vi == 0) or \
               (side == 'R' and vi == n_v_ch - 1):
                py = hcy
            else:
                py = hcy + h_bw / 2 - idx * wire_pitch
        return px, py

    for (vi, hi), conns in cfg.sbs.items():
        vcx, hcy = v_cx[vi], h_cy[hi]
        for p1_name, p2_name in conns:
            x1, y1 = sb_port_pos(vi, hi, p1_name)
            x2, y2 = sb_port_pos(vi, hi, p2_name)

            # Same-side connections: draw arc bowing toward SB center
            if p1_name[0] == p2_name[0]:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                bow = 0.5
                ctrl_x = mx + bow * (vcx - mx)
                ctrl_y = my + bow * (hcy - my)
                d.here = Point((x1, y1))
                arc = elm.Element().theta(0)
                arc.segments.append(
                    SegmentBezier(
                        [(0, 0),
                         (ctrl_x - x1, ctrl_y - y1),
                         (x2 - x1, y2 - y1)]))
                d.add(arc)
            else:
                # Different sides: straight line
                d.here = Point((x1, y1))
                elm.Line().to(Point((x2, y2)))
