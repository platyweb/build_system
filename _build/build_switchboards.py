#!/usr/bin/env python3
r"""
Generate switchboard diagram pages from METER_REGISTRY + _data/switchboards.yaml.

A board is defined by an incomer meter id; its "ways" are every meter whose
parent_id == incomer_id. For each board this writes:

    img/<key><suffix>.svg    the busbar background (busbar + connectors), generated
    <key><suffix>.htm        the page: <img> background + live HTML widget overlays

The widgets are positioned in native SVG coordinates (data-position, centred by
the .data-overlay CSS) and bound to live data via data-bacnet/data-format
(computed from the registry, exactly like the hand-built pages), plus a
segmented gauge rendered live by js/project/2.0/switchboard-gauge.js.

While validating, <suffix> is ".generated" so the live swb_*.htm / img/lvNN.svg
are left untouched. Set GEN_SUFFIX = "" (or pass --inplace) to overwrite them.

Usage:
    .\.venv\Scripts\python.exe _build\build_switchboards.py            # all boards
    .\.venv\Scripts\python.exe _build\build_switchboards.py swb_lv01   # one board
    .\.venv\Scripts\python.exe _build\build_switchboards.py --inplace  # write live names
"""
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
import yaml
from build import DATA_DIR, SITE_DIR, make_env, read_meters

# Output lives under the site directory (project/<slug>/, see building.yaml), not the repo
# root — this mirrors every other builder in _build/ (all write under SITE_DIR).
IMG_DIR = SITE_DIR / "img"
GEN_SUFFIX = ".generated"     # overridden to "" by --inplace


# ─── live-data address rules (mirror meter-templates.js) ─────────────────────
def power_offset(meter_type: str) -> int:
    return 40 if meter_type == "Modbus" else 82 if meter_type == "Calculation" else 0


def demand_bacnet(meter: dict) -> str:
    return f"300|0|{meter['base'] + power_offset(meter['type'])}|85|-1"


# ─── layout ──────────────────────────────────────────────────────────────────
def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


TAG_PREFIX_RE = re.compile(r"^LV\d+\s*-\s*")  # "LV03 - " etc. — redundant, the board itself says which LV


def make_box(meter, cx, cy, w, h, cfg, default_rating, is_incomer=False):
    return {
        "meter_id": meter["id"],
        "title":    TAG_PREFIX_RE.sub("", meter["tag"]),
        "ct":       cfg.get("ct", ""),
        "rating":   cfg.get("rating", default_rating),
        "bacnet":   demand_bacnet(meter),
        "cx": round(cx, 1), "cy": round(cy, 1), "w": w, "h": h,
        "is_incomer": is_incomer,
    }


def compute_board(key, board, defaults, by_id, children, boards):
    L = deep_merge(defaults["layout"], board.get("layout", {}))
    inc_id = board["incomer_id"]
    if inc_id not in by_id:
        raise SystemExit(f"{key}: incomer_id={inc_id} not in METER_REGISTRY")
    ways = sorted(children.get(inc_id, []), key=lambda m: m["id"])
    n = max(len(ways), 1)
    bw, bh = L["box"]["w"], L["box"]["h"]
    margin, gap = L["margin"], L["gap"]
    row_top = L["row_top"]
    default_rating = board.get("default_rating", defaults.get("default_rating", 150))

    # A bus_tie reserves extra canvas on one side of the busbar for an arrow
    # + link to another board (see build_svg for the arrow, ctx["bus_tie"]
    # for the HTML label). It shifts the whole box grid over rather than
    # squeezing it, so a board without one is laid out exactly as before.
    bus_tie = board.get("bus_tie")
    if bus_tie and bus_tie.get("side") not in ("left", "right"):
        raise SystemExit(f"{key}: bus_tie.side must be 'left' or 'right'")
    if bus_tie and bus_tie.get("to") not in boards:
        raise SystemExit(f"{key}: bus_tie.to={bus_tie.get('to')!r} is not a known board key")
    tie_margin = L.get("tie_margin", 200)
    left_pad = tie_margin if bus_tie and bus_tie["side"] == "left" else 0
    right_pad = tie_margin if bus_tie and bus_tie["side"] == "right" else 0

    # Ways are laid out in a grid: `rows` (default 1, i.e. the original
    # single-row layout) boxes stacked per column, filled column-major (fill
    # column 0 top-to-bottom before starting column 1) so a board with a lot
    # of ways stays bounded in width instead of one very wide row. Boards
    # that don't set layout.rows are unaffected — rows=1 makes cols == n,
    # identical to the original per-row math.
    rows = max(1, L.get("rows", 1))
    row_gap = L.get("row_gap", gap)
    # Boxes stacked in a column cascade sideways a little per row (instead of
    # sitting exactly on top of one another) so each is legible as its own
    # box rather than one solid stack of overlapping edges.
    row_stagger = L.get("row_stagger", 24)
    cols = math.ceil(n / rows)
    # Each stacked column needs enough width around its box for its lane fan
    # (see build_svg) to actually space out — a flat min_width doesn't scale
    # with column count, so a 5-column board (LV03) got squeezed into the
    # same canvas as a 3-column one (LV04) and its lanes came out ~10x
    # tighter. Size each column for a target minimum lane pitch instead
    # (inverts the avail/pitch formula in build_svg), so more columns means
    # a wider canvas rather than tighter lanes.
    lane_pitch_target = L.get("lane_pitch_target", 20)
    col_w = (bw + gap) if rows == 1 else max(bw + gap, lane_pitch_target * (rows + 1) + 1.5 * bw + gap)
    content_width = max(L["min_width"], margin * 2 + cols * col_w + (rows - 1) * row_stagger)
    width = content_width + left_pad + right_pad
    x1 = margin + left_pad
    x2 = x1 + (content_width - margin * 2)
    step = (x2 - x1) / cols
    stack_h = rows * bh + (rows - 1) * row_gap
    # Busbar sits below the tallest column stack — computed rather than a
    # fixed y so it never overlaps a multi-row board's bottom row.
    busbar_y = row_top + stack_h + L.get("riser_gap", L["incomer_gap"])

    boxes = []
    for i, m in enumerate(ways):
        col, r = divmod(i, rows)
        cx = x1 + step * (col + 0.5) + r * row_stagger
        cy = row_top + r * (bh + row_gap) + bh / 2
        wcfg = (board.get("ways") or {}).get(m["id"], {})
        box = make_box(m, cx, cy, bw, bh, wcfg, default_rating)
        box["col"] = col          # groups a stagger-column's connectors in build_svg
        box["col_cx"] = round(x1 + step * (col + 0.5), 1)  # unstaggered anchor x
        boxes.append(box)

    inc_cfg = board.get("incomer", {})
    inc_cy = busbar_y + L["incomer_gap"] + bh / 2
    incomer = make_box(by_id[inc_id], x1 + (x2 - x1) / 2, inc_cy, bw, bh,
                       inc_cfg, inc_cfg.get("rating", 1500), is_incomer=True)

    tie = None
    if bus_tie:
        arrow_len = L.get("tie_arrow_len", 70)
        side = bus_tie["side"]
        base_x = (x1 - 20) if side == "left" else (x2 + 20)
        tip_x = base_x - arrow_len if side == "left" else base_x + arrow_len
        target = boards[bus_tie["to"]]
        tie = {
            "side":     side,
            "base_x":   round(base_x, 1),
            "tip_x":    round(tip_x, 1),
            "arrow_head": L.get("tie_arrow_head", 26),
            "label":    bus_tie.get("label") or target.get("heading", bus_tie["to"]),
            "href":     f"{bus_tie['to']}{GEN_SUFFIX}.htm",
            "label_cx": round(tip_x, 1),
            "label_cy": round(busbar_y - 30, 1),
        }

    height = inc_cy + bh / 2 + margin
    svg = build_svg(L, width, height, busbar_y, boxes, incomer, step, x1 - 20, x2 + 20, tie)
    ctx = {
        "heading":       board.get("heading", key),
        "page_title":    board.get("page_title", board.get("heading", key)),
        "container_class": "floor-container",
        "svg_path":      f"img/{key}{GEN_SUFFIX}.svg",
        "boxes":         boxes + [incomer],
        "bus_tie":       tie,
    }
    return ctx, svg


def build_svg(L, width, height, busbar_y, boxes, incomer, col_step, busbar_x1, busbar_x2, tie=None):
    bc, bw = L["busbar"]["color"], L["busbar"]["width"]
    cc, cw = L["conn"]["color"], L["conn"]["width"]
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
         f'viewBox="0 0 {width} {height}">']
    # busbar — stops at the box-grid content bounds, not the full canvas, so
    # a bus_tie's reserved pad space stays empty for the arrow rather than
    # having the busbar itself drawn straight through it.
    p.append(f'<line x1="{busbar_x1:.1f}" y1="{busbar_y}" x2="{busbar_x2:.1f}" '
             f'y2="{busbar_y}" stroke="{bc}" stroke-width="{bw}" stroke-linecap="round"/>')
    # way connectors: every box taps the busbar directly and independently —
    # no line ever touches another box or shares a segment with another
    # way's line. A single box in a column drops straight down (nothing to
    # avoid). A stacked column (rows>1) fans its taps out to one side (left)
    # of the column's anchor x — not the individual (staggered) box
    # positions, so the lanes stay a tidy straight fan regardless of how far
    # boxes cascade — using the generous unused space before the previous
    # column. Nested by depth: the box closest to the busbar gets the
    # innermost/shortest lane, the farthest gets the outermost, so lanes run
    # parallel and never cross. Each box's own stub (at its own row height,
    # so stubs never share a y) joins its own edge to its lane.
    box_w = L["box"]["w"]
    avail = max(box_w / 2, col_step - box_w - L["gap"])  # clear of the previous column
    by_col = defaultdict(list)
    for b in boxes:
        by_col[b["col"]].append(b)
    for col_boxes in by_col.values():
        col_boxes.sort(key=lambda b: b["cy"])  # top -> bottom
        anchor_x = col_boxes[0]["col_cx"]
        if len(col_boxes) == 1:
            b = col_boxes[0]
            y1 = b["cy"] + b["h"] / 2
            p.append(f'<line x1="{b["cx"]}" y1="{y1:.1f}" x2="{b["cx"]}" y2="{busbar_y}" '
                     f'stroke="{cc}" stroke-width="{cw}"/>')
            continue
        pitch = (avail - box_w / 2) / (len(col_boxes) + 1)
        for depth, b in enumerate(reversed(col_boxes)):  # depth 0 = closest to busbar
            lane_x = anchor_x - box_w / 2 - pitch * (depth + 1)
            edge_x = b["cx"] - box_w / 2
            p.append(f'<line x1="{edge_x:.1f}" y1="{b["cy"]:.1f}" '
                     f'x2="{lane_x:.1f}" y2="{b["cy"]:.1f}" stroke="{cc}" stroke-width="{cw}"/>')
            p.append(f'<line x1="{lane_x:.1f}" y1="{b["cy"]:.1f}" x2="{lane_x:.1f}" y2="{busbar_y}" '
                     f'stroke="{cc}" stroke-width="{cw}"/>')
    # incomer connector: busbar -> incomer top edge
    iy = incomer["cy"] - incomer["h"] / 2
    p.append(f'<line x1="{incomer["cx"]}" y1="{iy:.1f}" x2="{incomer["cx"]}" y2="{busbar_y}" '
             f'stroke="{cc}" stroke-width="{cw}"/>')
    # bus-tie arrow: the busbar's own color/weight extended past its end,
    # capped with a filled arrowhead — reads as "this busbar continues via a
    # tie", not as just another way. The HTML label alongside it (drawn by
    # the template from ctx["bus_tie"]) carries the link to the other board.
    if tie:
        base_x, tip_x, head = tie["base_x"], tie["tip_x"], tie["arrow_head"]
        # shaft stops `head` short of the tip so the triangle isn't buried
        # under it — that gap sits BETWEEN base_x and tip_x, i.e. toward
        # base_x, on both sides (tip_x < base_x on the left, > on the right).
        shaft_x = tip_x + head if tie["side"] == "left" else tip_x - head
        p.append(f'<line x1="{base_x}" y1="{busbar_y}" x2="{shaft_x:.1f}" y2="{busbar_y}" '
                 f'stroke="{bc}" stroke-width="{bw}" stroke-linecap="round"/>')
        p.append(f'<polygon points="{tip_x},{busbar_y} {shaft_x:.1f},{busbar_y - head / 2:.1f} '
                 f'{shaft_x:.1f},{busbar_y + head / 2:.1f}" fill="{bc}"/>')
    p.append("</svg>\n")
    return "\n".join(p)


# ─── driver ──────────────────────────────────────────────────────────────────
def main(argv):
    global GEN_SUFFIX
    only = None
    for a in argv:
        if a == "--inplace":
            GEN_SUFFIX = ""
        else:
            only = a

    cfg = yaml.safe_load((DATA_DIR / "switchboards.yaml").read_text(encoding="utf-8")) or {}
    defaults, boards = cfg.get("defaults", {}), cfg.get("boards", {})

    meters = read_meters()
    by_id = {m["id"]: m for m in meters}
    children = defaultdict(list)
    for m in meters:
        if m["parent_id"] is not None:
            children[m["parent_id"]].append(m)

    env = make_env()
    template = env.get_template("switchboard.html.j2")

    written = []
    print("Building switchboards...")
    for key, board in boards.items():
        if only and only != key:
            continue
        ctx, svg = compute_board(key, board, defaults, by_id, children, boards)
        # heading/page_title in switchboards.yaml may reference {{ building.* }}
        # (kept as data so a rename only touches building.yaml).
        for meta_key in ("heading", "page_title"):
            if isinstance(ctx.get(meta_key), str):
                ctx[meta_key] = env.from_string(ctx[meta_key]).render()
        svg_path = IMG_DIR / f"{key}{GEN_SUFFIX}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        html_path = SITE_DIR / f"{key}{GEN_SUFFIX}.htm"
        html_path.write_text(template.render(**ctx), encoding="utf-8")
        n_ways = len(ctx["boxes"]) - 1
        print(f"  wrote {svg_path.relative_to(SITE_DIR)} + {html_path.relative_to(SITE_DIR)}  ({n_ways} ways)")
        written += [svg_path, html_path]
    print(f"Done. {len(written)} file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
