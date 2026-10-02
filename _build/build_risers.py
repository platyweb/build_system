#!/usr/bin/env python3
r"""
Generate riser diagram pages from METER_REGISTRY + _data/risers.yaml.

A riser is any meter with function == "Riser-meter" (see _data/meters.csv
— edit there, then regenerate via _build/generate_meter_registry.py). Risers
are auto-discovered from the registry, not hand-listed: this mirrors
_build/build_switchboards.py's "ways are every meter whose parent_id equals
the incomer id" approach, one tier further down — a riser's floor tap-offs
are every meter whose parent_id equals the riser meter's own id.

Where a switchboard's single-line diagram is horizontal (busbar left-right,
ways tapping up from it), a riser diagram is the same idea turned 90°: the
busbar runs vertically, the riser's own incomer sits at the bottom (fed from
its LV switchboard), and floor tap-offs run up it in physical floor order
(FLOOR_ORDER below) — a floor can carry more than one tap (e.g. "LTG/FCU" +
"SP" + "Comms"), fanned out with their own independent, non-crossing lanes
to the busbar exactly like a switchboard column's stacked ways.

A riser taller than layout.floors_per_page floor-rows splits across multiple
pages (<key>_p1, <key>_p2, ...), linked end to end by an arrow off the top/
bottom of the busbar — the vertical counterpart of a switchboard's bus_tie.

For each riser page this writes:
    img/<key><suffix>.svg    the vertical busbar background, generated
    <key><suffix>.htm        the page: <img> background + live HTML widget overlays

While validating, <suffix> is ".generated" so nothing live is touched. Set
GEN_SUFFIX = "" (or pass --inplace) to write live names.

Usage:
    .\.venv\Scripts\python.exe _build\build_risers.py            # all risers
    .\.venv\Scripts\python.exe _build\build_risers.py riser_41    # one riser
    .\.venv\Scripts\python.exe _build\build_risers.py --inplace   # write live names
"""
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
import yaml
from build import DATA_DIR, SITE_DIR, make_env, read_meters

IMG_DIR = SITE_DIR / "img"
GEN_SUFFIX = ".generated"     # overridden to "" by --inplace

TAG_PREFIX_RE = re.compile(r"^LV\d+\s*-\s*")  # "LV03 - " etc. — redundant, the riser's own name says which board


# ─── canonical bottom-to-top floor order ──────────────────────────────────────
def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


FLOOR_ORDER = ["B4", "B3", "B2", "B1", "ground"] + [_ordinal(n) for n in range(1, 47)]
FLOOR_RANK = {f: i for i, f in enumerate(FLOOR_ORDER)}


# ─── live-data address rules (mirror meter-templates.js / build_switchboards.py) ──
def power_offset(meter_type: str) -> int:
    return 40 if meter_type == "Modbus" else 82 if meter_type == "Calculation" else 0


def demand_bacnet(meter: dict) -> str:
    return f"300|0|{meter['base'] + power_offset(meter['type'])}|85|-1"


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def make_box(meter, cx, cy, w, h, default_rating, is_incomer=False):
    return {
        "meter_id": meter["id"],
        "title":    TAG_PREFIX_RE.sub("", meter["tag"]),
        "ct":       "",
        "rating":   default_rating,
        "bacnet":   demand_bacnet(meter),
        "cx": round(cx, 1), "cy": round(cy, 1), "w": w, "h": h,
        "is_incomer": is_incomer,
    }


# ─── layout ──────────────────────────────────────────────────────────────────
def compute_pages(riser, kids, cfg, defaults, default_rating):
    """Group a riser's children by floor, split into page-chunks, and lay out
    each chunk. Returns a list of (page_key_suffix, ctx, svg)."""
    L = deep_merge(defaults["layout"], cfg.get("layout", {}))
    floors_per_page = cfg.get("floors_per_page", defaults.get("floors_per_page", 20))

    by_floor = defaultdict(list)
    skipped = []
    for m in kids:
        f = m.get("floor") or ""
        if f in FLOOR_RANK:
            by_floor[f].append(m)
        else:
            skipped.append(m)
    if skipped:
        print(f"    WARNING: {len(skipped)} children have unrecognised floor labels, skipped: "
              f"{[m['tag'] for m in skipped]}")
    for f in by_floor:
        by_floor[f].sort(key=lambda m: (m["position"] if m["position"] is not None else 0, m["id"]))

    floor_labels = sorted(by_floor.keys(), key=lambda f: FLOOR_RANK[f])  # bottom -> top
    if not floor_labels:
        return []

    # Balance chunk sizes across however many pages are needed, rather than
    # greedily filling floors_per_page and leaving a near-empty remainder
    # page (e.g. 21 floors / 20-per-page => 20+1, not a sensible 11+10).
    n_pages = math.ceil(len(floor_labels) / floors_per_page)
    chunk_size = math.ceil(len(floor_labels) / n_pages)
    chunks = [floor_labels[i:i + chunk_size] for i in range(0, len(floor_labels), chunk_size)]
    pages = []
    for i, chunk in enumerate(chunks):
        suffix = "" if len(chunks) == 1 else f"_p{i + 1}"
        ctx, svg = compute_page(riser, chunk, by_floor, L, default_rating,
                                 is_first=(i == 0), is_last=(i == len(chunks) - 1))
        pages.append((suffix, ctx, svg))

    # Wire each continuation arrow's label + link now that every page's key
    # is known (a page can't know its neighbour's filename while it's being
    # built in isolation).
    key = f"riser_{riser['id']}"
    for i, (suffix, ctx, svg) in enumerate(pages):
        if ctx["tie_bottom"]:
            prev_suffix = pages[i - 1][0]
            ctx["tie_bottom"]["href"] = f"{key}{prev_suffix}{GEN_SUFFIX}.htm"
            ctx["tie_bottom"]["label"] = "↓ lower floors"
        if ctx["tie_top"]:
            next_suffix = pages[i + 1][0]
            ctx["tie_top"]["href"] = f"{key}{next_suffix}{GEN_SUFFIX}.htm"
            ctx["tie_top"]["label"] = "↑ upper floors"
    return pages


def compute_page(riser, floor_labels, by_floor, L, default_rating, is_first, is_last):
    box_w, box_h = L["box"]["w"], L["box"]["h"]
    margin, gap = L["margin"], L["gap"]
    tap_offset, depth_step = L["tap_offset"], L["depth_step"]
    y_stagger = L.get("tap_stagger", 10)

    max_taps = max(len(by_floor[f]) for f in floor_labels)
    lane_pitch_target = L.get("lane_pitch_target", 14)
    floor_pitch = max(box_h + L["floor_gap"],
                       lane_pitch_target * (max_taps + 1) + 1.5 * box_h + L["floor_gap"])

    busbar_x = margin
    n_floors = len(floor_labels)
    top_y = margin + box_h / 2                      # topmost floor row's box center
    bottom_y = top_y + (n_floors - 1) * floor_pitch  # bottom-most floor row's box center

    boxes = []
    row_ys = {}
    # floor_labels is bottom -> top; row index 0 = bottom (nearest the incomer)
    for row, f in enumerate(reversed(floor_labels)):
        row_cy = bottom_y - row * floor_pitch
        row_ys[f] = row_cy
        taps = by_floor[f]
        for depth, m in enumerate(taps):  # depth 0 = nearest the busbar
            cx = busbar_x + tap_offset + depth * depth_step
            cy = row_cy + depth * y_stagger
            box = make_box(m, cx, cy, box_w, box_h, default_rating)
            box["row_cy"] = round(row_cy, 1)  # unstaggered anchor y, for lane grouping
            boxes.append(box)

    max_x = busbar_x + tap_offset + (max_taps - 1) * depth_step + box_w
    width = max_x + margin

    # incomer (only the bottom-most page — the riser meter itself, fed from
    # its LV switchboard) or a downward continuation arrow to the previous page
    incomer = None
    tie_bottom = None
    if is_first:
        inc_cy = bottom_y + L["incomer_gap"] + box_h / 2
        incomer = make_box(riser, busbar_x, inc_cy, box_w, box_h, default_rating, is_incomer=True)
        busbar_bottom_y = inc_cy - box_h / 2 - L.get("incomer_gap", 70) / 2
        height_bottom_extra = L["incomer_gap"] + box_h + margin
    else:
        arrow_len = L.get("tie_arrow_len", 70)
        base_y = bottom_y + L["incomer_gap"]
        tip_y = base_y + arrow_len
        tie_bottom = {"base_y": round(base_y, 1), "tip_y": round(tip_y, 1),
                      "arrow_head": L.get("tie_arrow_head", 26), "dir": "down",
                      "label_cx": round(busbar_x + 90, 1), "label_cy": round(tip_y, 1)}
        busbar_bottom_y = base_y
        height_bottom_extra = L["incomer_gap"] + arrow_len + margin

    tie_top = None
    if not is_last:
        arrow_len = L.get("tie_arrow_len", 70)
        base_y = top_y - L["floor_gap"] - 20
        tip_y = base_y - arrow_len
        tie_top = {"base_y": round(base_y, 1), "tip_y": round(tip_y, 1),
                   "arrow_head": L.get("tie_arrow_head", 26), "dir": "up",
                   "label_cx": round(busbar_x + 90, 1), "label_cy": round(tip_y, 1)}
        busbar_top_y = tip_y - 40
    else:
        busbar_top_y = top_y - box_h / 2 - L["floor_gap"]

    height = (bottom_y - busbar_top_y) + box_h / 2 + height_bottom_extra

    # shift everything down so busbar_top_y >= 0
    if busbar_top_y < margin:
        shift = margin - busbar_top_y
        for b in boxes:
            b["cy"] = round(b["cy"] + shift, 1)
            b["row_cy"] = round(b["row_cy"] + shift, 1)
        if incomer:
            incomer["cy"] = round(incomer["cy"] + shift, 1)
        if tie_bottom:
            tie_bottom["base_y"] = round(tie_bottom["base_y"] + shift, 1)
            tie_bottom["tip_y"] = round(tie_bottom["tip_y"] + shift, 1)
            tie_bottom["label_cy"] = round(tie_bottom["label_cy"] + shift, 1)
        if tie_top:
            tie_top["base_y"] = round(tie_top["base_y"] + shift, 1)
            tie_top["tip_y"] = round(tie_top["tip_y"] + shift, 1)
            tie_top["label_cy"] = round(tie_top["label_cy"] + shift, 1)
        busbar_top_y += shift
        busbar_bottom_y += shift
        height += shift

    svg = build_svg(L, width, height, busbar_x, busbar_top_y, busbar_bottom_y,
                     boxes, incomer, floor_pitch, tie_top, tie_bottom)

    core = None
    zones = Counter(m["zone"] for f in floor_labels for m in by_floor[f] if m["zone"] not in ("", "n/a"))
    if zones:
        core = zones.most_common(1)[0][0]

    title = TAG_PREFIX_RE.sub("", riser["tag"])
    heading = f"{title} ({core} core)" if core else title

    ctx = {
        "heading":       heading,
        "page_title":    heading,
        "container_class": "floor-container",
        "boxes":         boxes + ([incomer] if incomer else []),
        "tie_top":       tie_top,
        "tie_bottom":    tie_bottom,
    }
    return ctx, svg


def build_svg(L, width, height, busbar_x, busbar_top_y, busbar_bottom_y,
              boxes, incomer, floor_pitch, tie_top, tie_bottom):
    bc, bw = L["busbar"]["color"], L["busbar"]["width"]
    cc, cw = L["conn"]["color"], L["conn"]["width"]
    box_h = L["box"]["h"]
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
         f'viewBox="0 0 {width:.1f} {height:.1f}">']
    # busbar — vertical, spans the box-grid content bounds (not into a
    # continuation-arrow's reserved space, same reasoning as switchboards).
    p.append(f'<line x1="{busbar_x}" y1="{busbar_top_y:.1f}" x2="{busbar_x}" y2="{busbar_bottom_y:.1f}" '
             f'stroke="{bc}" stroke-width="{bw}" stroke-linecap="round"/>')
    # floor tap connectors: every box taps the busbar directly and
    # independently, mirroring build_switchboards.py's column lane-fan
    # rotated 90° — floor row = column, "depth from busbar" (x) = stack
    # depth, lane offset fans in y (along the busbar) instead of x.
    avail = max(L["box"]["w"] / 2, floor_pitch - box_h - L["floor_gap"])
    by_row = defaultdict(list)
    for b in boxes:
        by_row[b["row_cy"]].append(b)
    for row_cy, row_boxes in by_row.items():
        row_boxes.sort(key=lambda b: b["cx"])  # nearest busbar -> farthest
        if len(row_boxes) == 1:
            b = row_boxes[0]
            x1 = b["cx"] - b["w"] / 2
            p.append(f'<line x1="{x1:.1f}" y1="{b["cy"]}" x2="{busbar_x}" y2="{b["cy"]}" '
                     f'stroke="{cc}" stroke-width="{cw}"/>')
            continue
        pitch = (avail - box_h / 2) / (len(row_boxes) + 1)
        for depth, b in enumerate(row_boxes):  # depth 0 = nearest the busbar
            lane_y = row_cy - box_h / 2 - pitch * (depth + 1)
            edge_y = b["cy"] - box_h / 2
            p.append(f'<line x1="{b["cx"]}" y1="{edge_y:.1f}" x2="{b["cx"]}" y2="{lane_y:.1f}" '
                     f'stroke="{cc}" stroke-width="{cw}"/>')
            p.append(f'<line x1="{b["cx"]}" y1="{lane_y:.1f}" x2="{busbar_x}" y2="{lane_y:.1f}" '
                     f'stroke="{cc}" stroke-width="{cw}"/>')
    # incomer connector: busbar -> incomer top edge (bottom-most page only)
    if incomer:
        iy = incomer["cy"] - incomer["h"] / 2
        p.append(f'<line x1="{incomer["cx"]}" y1="{busbar_bottom_y:.1f}" x2="{incomer["cx"]}" y2="{iy:.1f}" '
                 f'stroke="{cc}" stroke-width="{cw}"/>')
    # continuation arrows — the vertical counterpart of a switchboard bus_tie:
    # busbar-colored shaft + filled triangle, pointing toward the next/
    # previous page in this riser's own floor run.
    for tie in (t for t in (tie_top, tie_bottom) if t):
        base_y, tip_y, head = tie["base_y"], tie["tip_y"], tie["arrow_head"]
        shaft_y = tip_y - head if tie["dir"] == "down" else tip_y + head
        p.append(f'<line x1="{busbar_x}" y1="{base_y}" x2="{busbar_x}" y2="{shaft_y:.1f}" '
                 f'stroke="{bc}" stroke-width="{bw}" stroke-linecap="round"/>')
        p.append(f'<polygon points="{busbar_x},{tip_y} {busbar_x - head / 2:.1f},{shaft_y:.1f} '
                 f'{busbar_x + head / 2:.1f},{shaft_y:.1f}" fill="{bc}"/>')
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

    cfg_all = yaml.safe_load((DATA_DIR / "risers.yaml").read_text(encoding="utf-8")) or {}
    defaults = cfg_all.get("defaults", {})
    overrides = cfg_all.get("overrides", {}) or {}

    meters = read_meters()
    by_id = {m["id"]: m for m in meters}
    children = defaultdict(list)
    for m in meters:
        if m["parent_id"] is not None:
            children[m["parent_id"]].append(m)

    risers = sorted((m for m in meters if m["function"] == "Riser-meter"), key=lambda m: m["id"])
    if not risers:
        print("No meters with function == 'Riser-meter' found — nothing to build.")
        return 0

    env = make_env()
    template = env.get_template("riser.html.j2")

    default_rating = defaults.get("default_rating", 60)
    written = []
    print("Building risers...")
    for riser in risers:
        key = f"riser_{riser['id']}"
        if only and only != key:
            continue
        cfg = overrides.get(riser["id"], {})
        kids = sorted(children.get(riser["id"], []), key=lambda m: m["id"])
        pages = compute_pages(riser, kids, cfg, defaults, default_rating)
        if not pages:
            print(f"  {key}: no floor-mapped children, skipped")
            continue
        for suffix, ctx, svg in pages:
            page_key = key + suffix
            for meta_key in ("heading", "page_title"):
                if isinstance(ctx.get(meta_key), str):
                    ctx[meta_key] = env.from_string(ctx[meta_key]).render()
            ctx["svg_path"] = f"img/{page_key}{GEN_SUFFIX}.svg"
            svg_path = IMG_DIR / f"{page_key}{GEN_SUFFIX}.svg"
            svg_path.write_text(svg, encoding="utf-8")
            html_path = SITE_DIR / f"{page_key}{GEN_SUFFIX}.htm"
            html_path.write_text(template.render(**ctx), encoding="utf-8")
            n_taps = len(ctx["boxes"]) - (1 if ctx["boxes"] and ctx["boxes"][-1]["is_incomer"] else 0)
            print(f"  wrote {svg_path.relative_to(SITE_DIR)} + {html_path.relative_to(SITE_DIR)}  ({n_taps} taps)")
            written += [svg_path, html_path]
    print(f"Done. {len(written)} file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
