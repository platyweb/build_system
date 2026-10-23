#!/usr/bin/env python3
r"""
Generate switchboard pages from the meters file + site/data/switchboards.yaml.

A board is defined by an incomer meter id; its "ways" are every meter whose
parent_id == incomer_id. Each board's page (<key>.htm) is its single-line
diagram: the incomer on top feeding the busbar, the ways below it, `columns`
to a busbar row. Every meter is one data-meter-card placeholder, which
meter-templates.js builds into a card from METER_REGISTRY (live demand,
a segmented gauge against the way's rating, its CT); the busbar and the
lines are CSS (switchboard-widget.css). Nothing is positioned by hand.

    boards:
      swb_lv01:
        incomer_id: 39                 # the board: this meter, and every meter it feeds
        heading:    "LV-01 Switchboard"
        incomer:    {rating: 1500, ct: "2000/5"}
        ways:       {41: {rating: 400, ct: "800/5"}}   # by meter id; default_rating otherwise
        columns:    5                  # ways to a busbar row (default 5)
        bus_tie:    {side: right, to: swb_lv02, label: "↔ LV-02", normally: open, meter: 45}

A bus tie is a coupler between two boards' busbars, declared on one of them
and drawn on both: a breaker on a dashed run (normally open, the default) or
a solid one (`normally: closed`) to a link to the other board, and the
coupler's meter if it has one. A board fed from another (its incomer is one
of the other's ways) says so beside its incomer, and that way's card links
to it; a way that is a riser links to the riser's page.

This is the `switchboards` module (build.py MODULES): list the boards in
pages.yaml (`pages: switchboards`), or run it on its own with

    python _build/build.py --modules switchboards            # all boards
    python _build/build.py --modules switchboards swb_lv01   # one board
"""
import re
from collections import defaultdict
from pathlib import Path

import yaml
import build_risers
import site_data  # the configured site: its paths (site_data.SITE_DIR, …) are read at call time

TAG_PREFIX_RE = re.compile(r"^LV\d+\s*-\s*")  # "LV03 - " etc. — redundant, the board itself says which LV
COLUMNS = 5              # ways to a busbar row, unless a board says
INCOMER_RATING = 1500    # an incomer's gauge full scale (kW), unless `incomer: {rating}` says
# Settings the SVG diagrams had, which the diagrams no longer use (--check notes them).
RETIRED = ("layout",)
OPPOSITE = {"left": "right", "right": "left"}


def card(meter: dict, cfg: dict, rating) -> dict:
    """A meter's card on the diagram: the meter_card macro's fields."""
    return {
        "meter_id": meter["id"],
        "label":    TAG_PREFIX_RE.sub("", meter["tag"]),
        "rating":   cfg.get("rating", rating),
        "ct":       cfg.get("ct", ""),
    }


def name(key: str, board: dict) -> str:
    """How a link names a board."""
    return str(board.get("heading") or key)


def bus_ties(boards: dict) -> dict[str, dict[str, dict]]:
    """Each board's couplers by side: the bus_tie it declares, and one
    mirrored from each board that ties to it without its tying back."""
    ties: dict[str, dict[str, dict]] = defaultdict(dict)
    for key, board in boards.items():
        tie = (board or {}).get("bus_tie")
        if not tie:
            continue
        if tie.get("side") not in OPPOSITE:
            raise SystemExit(f"{key}: bus_tie.side must be 'left' or 'right'")
        if tie.get("to") not in boards:
            raise SystemExit(f"{key}: bus_tie.to={tie.get('to')!r} is not a known board key")
        if tie.get("normally", "open") not in ("open", "closed"):
            raise SystemExit(f"{key}: bus_tie.normally must be 'open' or 'closed'")
        ties[key][tie["side"]] = tie
    for key, board in boards.items():
        tie = (board or {}).get("bus_tie")
        if not tie or ((boards[tie["to"]] or {}).get("bus_tie") or {}).get("to") == key:
            continue
        ties[tie["to"]].setdefault(OPPOSITE[tie["side"]], {
            "side": OPPOSITE[tie["side"]], "to": key, "normally": tie.get("normally", "open"),
            **({"meter": tie["meter"]} if "meter" in tie else {})})
    return ties


def compute_board(key, board, defaults, by_id, children, boards, ties, board_of, risers):
    """The page context of one board. `ties`: its couplers by side;
    `board_of`: each board's incomer → its key; `risers`: each riser with a
    page → its building. Links are site-root hrefs."""
    inc_id = board["incomer_id"]
    if inc_id not in by_id:
        raise SystemExit(f"{key}: incomer_id={inc_id} not in METER_REGISTRY")
    default_rating = board.get("default_rating", defaults.get("default_rating", 150))
    way_cfg = board.get("ways") or {}
    ways = [card(m, way_cfg.get(m["id"], {}), default_rating)
            for m in sorted(children.get(inc_id, []), key=lambda m: m["id"])]
    columns = max(1, min(len(ways), int(board.get("columns", defaults.get("columns", COLUMNS)))))
    for i, way in enumerate(ways):
        way["wraps"] = i > 0 and i % columns == 0
        way["link"] = None
        other = board_of.get(way["meter_id"])
        if other and other != key:
            way["link"] = {"label": f"→ {name(other, boards[other])}",
                           "href": site_data.site_href(boards[other].get("building"), f"{other}.htm")}
        elif way["meter_id"] in risers:
            way["link"] = {"label": "→ Riser",
                           "href": site_data.site_href(risers[way["meter_id"]], f"riser_{way['meter_id']}.htm")}

    inc_cfg = board.get("incomer") or {}
    incomer = card(by_id[inc_id], inc_cfg, INCOMER_RATING)
    feeder = board_of.get(by_id[inc_id]["parent_id"])
    fed_from = None
    if feeder and feeder != key:
        fed_from = {"label": f"Fed from {name(feeder, boards[feeder])}",
                    "href": site_data.site_href(boards[feeder].get("building"), f"{feeder}.htm")}

    couplers = []
    for side in ("left", "right"):
        tie = ties.get(side)
        if not tie:
            continue
        meter = tie.get("meter")
        if meter is not None and meter not in by_id:
            raise SystemExit(f"{key}: bus_tie.meter={meter} not in METER_REGISTRY")
        couplers.append({
            "side":  side,
            "open":  tie.get("normally", "open") == "open",
            "label": tie.get("label") or name(tie["to"], boards[tie["to"]]),
            "href":  site_data.site_href(boards[tie["to"]].get("building"), f"{tie['to']}.htm"),
            "meter": card(by_id[meter], {}, tie.get("rating", default_rating)) if meter is not None else None,
        })

    return {
        "heading":         board.get("heading", key),
        "page_title":      board.get("page_title", board.get("heading", key)),
        "container_class": "floor-container",
        "incomer":         incomer,
        "fed_from":        fed_from,
        "ways":            ways,
        "columns":         columns,
        "couplers":        couplers,
    }


def retired_settings() -> list[str]:
    """--check warnings: settings in switchboards.yaml the diagrams no longer use."""
    path = site_data.data_path("switchboards.yaml")
    cfg = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    where = [("defaults", cfg.get("defaults") or {})] + [(f"boards.{k}", b or {}) for k, b in (cfg.get("boards") or {}).items()]
    return [f"{path.name} {place}: `{name}` is no longer used (the diagram lays itself out); delete it"
            for place, entry in where for name in RETIRED if name in entry]


def run(env, only: str | None = None) -> list[Path]:
    """The `switchboards` module: one page per board in
    site/data/switchboards.yaml (`only`: a single board key)."""
    cfg = yaml.safe_load(site_data.data_path("switchboards.yaml").read_text(encoding="utf-8")) or {}
    defaults, boards = cfg.get("defaults") or {}, cfg.get("boards") or {}

    meters = site_data.read_meters()
    by_id = {m["id"]: m for m in meters}
    children = defaultdict(list)
    for m in meters:
        if m["parent_id"] is not None:
            children[m["parent_id"]].append(m)

    template = env.get_template("switchboard.html.j2")
    board_of = {(b or {}).get("incomer_id"): key for key, b in boards.items()}
    risers = build_risers.riser_buildings(meters, children)
    ties = bus_ties(boards)

    written = []
    for key, board in boards.items():
        if only and only != key:
            continue
        ctx = compute_board(key, board, defaults, by_id, children, boards, ties.get(key, {}), board_of, risers)
        # heading/page_title/labels in switchboards.yaml may reference
        # {{ building.* }} (kept as data so a rename only touches site.yaml).
        for meta_key in ("heading", "page_title"):
            if isinstance(ctx.get(meta_key), str):
                ctx[meta_key] = env.from_string(ctx[meta_key]).render()
        # On a campus a board with `building:` lives in that building's
        # folder: its links are written relative to the site root, then
        # rewritten for the page's folder.
        bkey = site_data.check_building(board.get("building"), f"switchboards.yaml '{key}'")
        out_dir, location_ctx = site_data.page_location(bkey)
        folder = site_data.page_folder(bkey)
        ctx.update(location_ctx)
        for link in ([ctx["fed_from"]] + [w.get("link") for w in ctx["ways"]] + ctx["couplers"]):
            if link:
                link["href"] = site_data.relative_url(link["href"], folder)
                link["label"] = env.from_string(link["label"]).render()
        html_path = out_dir / f"{key}.htm"
        html_path.write_text(site_data.render_page(template, ctx), encoding="utf-8", newline="\n")
        print(f"  wrote {html_path.relative_to(site_data.SITE_DIR)}  ({len(ctx['ways'])} ways)")
        written.append(html_path)
    return written
