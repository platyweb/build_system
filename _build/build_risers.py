#!/usr/bin/env python3
r"""
Generate riser pages from the meters file + site/data/risers.yaml.

A riser is any meter with function == "Riser-meter" in the site's meters
file (data/meters.yaml). Risers are found in the meters, not listed: like a
switchboard's ways (build_switchboards.py), a riser's floor tap-offs are
every meter whose parent_id equals the riser meter's own id.

A riser's page (riser_<id>.htm) is the switchboard diagram turned upright:
the busbar rises from the riser's own meter at the bottom past every floor
it feeds, top floor first (the floors.yaml roster, site_data.level_rank),
and each floor's row holds its taps. Every meter is one data-meter-card
placeholder, which meter-templates.js builds into a card from
METER_REGISTRY; the busbar and the lines are CSS (switchboard-widget.css).
The riser's meter links to the board whose incomer feeds it.

    defaults:  {default_rating: 60}       # a tap's gauge full scale (kW)
    overrides: {41: {nav_label: "North riser", default_rating: 100}}

This is the `risers` module (build.py MODULES): list the risers in
pages.yaml (`pages: risers`), or run it on its own with

    python _build/build.py --modules risers             # all risers
    python _build/build.py --modules risers riser_41    # one riser
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml
import site_data  # the configured site: its paths (site_data.SITE_DIR, …) are read at call time

TAG_PREFIX_RE = re.compile(r"^LV\d+\s*-\s*")
# Settings the SVG diagrams had, which the diagrams no longer use (--check notes them):
# a tall riser scrolls rather than splitting into pages.
RETIRED = ("layout", "floors_per_page")


def card(meter: dict, rating) -> dict:
    """A meter's card on the diagram: the meter_card macro's fields."""
    return {"meter_id": meter["id"], "label": TAG_PREFIX_RE.sub("", meter["tag"]), "rating": rating, "ct": ""}


def _config() -> dict:
    path = site_data.data_path("risers.yaml")
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def _children(meters: list[dict]) -> dict[int, list[dict]]:
    children = defaultdict(list)
    for m in meters:
        if m["parent_id"] is not None:
            children[m["parent_id"]].append(m)
    return children


def taps_by_floor(kids: list[dict], floor_rank: dict[str, int]) -> tuple[dict[str, list[dict]], list[dict]]:
    """A riser's tap-offs by floor, each floor's in card order; and those on
    no single floors.yaml level, which the page leaves out."""
    by_floor, skipped = defaultdict(list), []
    for m in kids:
        (by_floor[m["floor"]] if m.get("floor") in floor_rank else skipped).append(m)
    for taps in by_floor.values():
        taps.sort(key=lambda m: (m["position"] if m["position"] is not None else 0, m["id"]))
    return by_floor, skipped


def compute_page(riser, by_floor, levels, cfg, defaults):
    """The page context of one riser; `levels` are floors.yaml's by key."""
    rating = cfg.get("default_rating", defaults.get("default_rating", 60))
    floors = sorted(by_floor, key=lambda f: levels[f]["rank"], reverse=True)   # top → bottom
    zones = Counter(m["zone"] for f in floors for m in by_floor[f] if m["zone"] not in ("", "n/a"))
    core = zones.most_common(1)[0][0] if zones else None
    title = TAG_PREFIX_RE.sub("", riser["tag"])
    heading = (f"{title} ({core})" if "core" in core.lower() else f"{title} ({core} core)") if core else title
    return {
        "heading":         heading,
        "page_title":      heading,
        "container_class": "floor-container",
        "floors":          [{"label": levels[f]["label"], "taps": [card(m, rating) for m in by_floor[f]]}
                            for f in floors],
        "riser":           card(riser, cfg.get("rating", rating)),
        "fed_from":        None,
    }


def riser_buildings(meters: list[dict], children: dict[int, list[dict]]) -> dict[int, str | None]:
    """Each riser with a page (a tap on a level) → the building its page is in."""
    floor_rank = site_data.level_rank()
    level_building = {lv["key"]: lv["building"] for lv in site_data.read_levels()}
    return {m["id"]: level_building.get(m.get("floor") or "")
            for m in meters if m["function"] == "Riser-meter" and taps_by_floor(children.get(m["id"], []), floor_rank)[0]}


def retired_settings() -> list[str]:
    """--check warnings: settings in risers.yaml the diagrams no longer use."""
    cfg = _config()
    where = [("defaults", cfg.get("defaults") or {})] + [(f"overrides.{k}", o or {}) for k, o in (cfg.get("overrides") or {}).items()]
    return [f"{site_data.data_path('risers.yaml').name} {place}: `{name}` is no longer used (the diagram lays itself out); delete it"
            for place, entry in where for name in RETIRED if name in entry]


def sidebar_items() -> list[dict]:
    """The sidebar's `auto: risers` items: one per riser with taps, linking
    to its page and labelled like its heading (risers.yaml `overrides:
    <id>: {nav_label}` to rename one)."""
    overrides = _config().get("overrides") or {}
    meters = site_data.read_meters()
    children = _children(meters)
    floor_rank = site_data.level_rank()
    level_building = {lv["key"]: lv["building"] for lv in site_data.read_levels()}
    items = []
    for riser in sorted((m for m in meters if m["function"] == "Riser-meter"), key=lambda m: m["id"]):
        by_floor, _ = taps_by_floor(children.get(riser["id"], []), floor_rank)
        if not by_floor:
            continue
        key = f"riser_{riser['id']}"
        building = level_building.get(riser.get("floor") or "")
        items.append({
            "_key": key, "_building": building,
            "label": str((overrides.get(riser["id"]) or {}).get("nav_label") or TAG_PREFIX_RE.sub("", riser["tag"])),
            "href": site_data.site_href(building, f"{key}.htm"),
        })
    return items


def run(env, only: str | None = None) -> list[Path]:
    """The `risers` module: one page per riser meter (function ==
    "Riser-meter") in the meters file (`only`: a single riser key)."""
    cfg_all = _config()
    defaults = cfg_all.get("defaults") or {}
    overrides = cfg_all.get("overrides") or {}

    meters = site_data.read_meters()
    children = _children(meters)
    risers = sorted((m for m in meters if m["function"] == "Riser-meter"), key=lambda m: m["id"])
    if not risers:
        print(f"  (skip risers: no meters with function == 'Riser-meter' in {site_data.meters_file().name})")
        return []

    template = env.get_template("riser.html.j2")
    floor_rank = site_data.level_rank()
    levels = {lv["key"]: {**lv, "rank": floor_rank[lv["key"]]} for lv in site_data.read_levels()}
    # The board each riser hangs off: the one whose incomer is its parent.
    board_file = site_data.data_path("switchboards.yaml")
    boards = ((yaml.safe_load(board_file.read_text(encoding="utf-8")) or {}).get("boards") or {}) \
        if board_file.exists() else {}
    board_of = {(b or {}).get("incomer_id"): (key, b or {}) for key, b in boards.items()}

    written = []
    for riser in risers:
        key = f"riser_{riser['id']}"
        if only and only != key:
            continue
        by_floor, skipped = taps_by_floor(sorted(children.get(riser["id"], []), key=lambda m: m["id"]), floor_rank)
        if skipped:
            print(f"    WARNING: {len(skipped)} children have no single floors.yaml level as their floor, skipped: "
                  f"{[m['tag'] for m in skipped]}")
        if not by_floor:
            print(f"  {key}: no floor-mapped children, skipped")
            continue
        ctx = compute_page(riser, by_floor, levels, overrides.get(riser["id"]) or {}, defaults)
        # On a campus a riser's page goes to the folder of the building its
        # own meter's floor belongs to.
        building = levels.get(riser.get("floor") or "", {}).get("building")
        out_dir, location_ctx = site_data.page_location(building)
        ctx.update(location_ctx)
        for meta_key in ("heading", "page_title"):
            if isinstance(ctx.get(meta_key), str):
                ctx[meta_key] = env.from_string(ctx[meta_key]).render()
        if riser["parent_id"] in board_of:
            board_key, board = board_of[riser["parent_id"]]
            ctx["fed_from"] = {
                "label": env.from_string(str(board.get("nav_label") or board.get("heading") or board_key)).render(),
                "href": site_data.relative_url(site_data.site_href(board.get("building"), f"{board_key}.htm"),
                                               site_data.page_folder(building)),
            }
        html_path = out_dir / f"{key}.htm"
        html_path.write_text(site_data.render_page(template, ctx), encoding="utf-8", newline="\n")
        n_taps = sum(len(f["taps"]) for f in ctx["floors"])
        print(f"  wrote {html_path.relative_to(site_data.SITE_DIR)}  ({n_taps} taps)")
        written.append(html_path)
    return written
