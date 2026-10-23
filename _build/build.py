#!/usr/bin/env python
"""
Generate static .htm pages from a site directory (site/data/*.yaml +
site/pages/) through the engine templates (_templates/*.j2, overridable per
site from site/templates/).

Usage:
    python _build/build.py                 # full build: restage project/, build every page
    python _build/build.py floor_ground    # rebuild a single page by key
    python _build/build.py --check         # validate the site data + a trial build; writes nothing to project/
    python _build/build.py --site DIR --out DIR   # build another site / elsewhere

A full build first stages the output root from scratch (see stage_output):
the engine's runtime skeleton (_assets/) plus the site's own assets
(site/assets/), with METER_REGISTRY regenerated from site/data/meters.csv.
Generated blocks are only ever written into that staged copy.

Floor layout is derived from site/data/meters.csv (→ METER_REGISTRY): meters
carrying floor / column / zone / position / function / utility fields are
grouped into floor-cards by zone, ordered by position within each column.
site/data/floors.yaml is the level roster (physical order, labels) plus any
per-floor overrides; summary cards come from site.yaml `summary_roles:` +
data/points.yaml `floors:`, report cards from data/reports.yaml. README.md
documents every site file.

A meter that belongs on more than one floor page (e.g. a riser meter shared
between two floors) carries a "/"-separated floor list, e.g. floor:
"3rd/4th" — it renders on every floor named, with the same column/zone/
position/function/utility on each (see read_meters()'s "floors" tuple).

`utility` doubles as a CSS class hint (meter-<utility>) and may carry a
"-virtual" suffix for calculated meters; base_utility() strips that back off
wherever the code compares utilities rather than rendering them.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context

import build_risers
import build_switchboards
import components
import jsblocks
import linkcheck
import site_data
# The readers and settings the builders use. The configured paths and
# settings (site_data.SITE_DIR, site_data.FLOOR_PAGE, …) are read through the
# module, since configure() sets them after import.
from site_data import (
    DATA_FILES, DEFAULT_OUT_ROOT, DEFAULT_SITE_ROOT, FLOOR_SUMMARY_CARDS, LEGACY_DATA_FILES,
    MAX_METER_COLUMNS, ROOT, TENANTS_KEY, UTILITY_KINDS, bacnet_address, base_utility,
    check_building, configure, data_path, default_floorplan_image, demand_address,
    floor_report_title, level_rank, meters_file, page_folder, page_location, point_source,
    read_bms_bindings, read_building, _read_data, read_home, read_incomers, read_levels,
    read_meter_rows, read_meters, read_points, read_report_urls, read_reports, read_tenants,
    _read_yaml, _rel, relative_url, render_page, report_cards, reports_for, reports_to_cards,
    site_href, sort_floors,
)


def __getattr__(name: str):
    """build.<name> for anything in site_data, e.g. build.SITE_DIR or
    build.read_meters, so code and tests written against build keep working.
    Set a value on site_data: build.SITE_DIR = … would only hide it."""
    try:
        return getattr(site_data, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


TEMPLATES_DIR = ROOT / "_templates"   # engine templates
ASSETS_DIR = ROOT / "_assets"         # engine runtime skeleton (project JS/CSS, vendor libs)
COMPONENTS_DIR = ROOT / "_components" # engine component catalog (see components.py)

# Written into the output root by stage_output(). A full build only ever
# wipes an output root that carries it, so pointing --out at a directory
# this build didn't create (a hand-maintained deploy copy, say) can't
# destroy it.
OUTPUT_MARKER = ".build-output"


# ─── Output root ─────────────────────────────────────────────────────────────
def stage_output() -> None:
    """Recreate the output root from scratch for a full build.

    Wipes OUT_ROOT (only if a previous build created it — see
    OUTPUT_MARKER), copies the engine skeleton (_assets/) into SITE_DIR and
    overlays the site's own assets (site/assets/) on top. The builders then
    write pages into it and inject generated blocks into its JS — _assets/
    itself is never modified.
    """
    if site_data.OUT_ROOT.exists():
        if not (site_data.OUT_ROOT / OUTPUT_MARKER).exists():
            raise SystemExit(
                f"{site_data.OUT_ROOT} exists but has no {OUTPUT_MARKER} marker, so this build didn't create it — "
                "refusing to wipe it. Move it aside or pass a different --out."
            )
        shutil.rmtree(site_data.OUT_ROOT)
    site_data.OUT_ROOT.mkdir(parents=True)
    (site_data.OUT_ROOT / OUTPUT_MARKER).write_text(
        "Created by _build/build.py. A full build deletes and recreates this whole directory.\n",
        encoding="utf-8", newline="\n",
    )
    shutil.copytree(ASSETS_DIR, site_data.SITE_DIR)
    site_assets = site_data.SITE_ROOT / "assets"
    if site_assets.exists():
        shutil.copytree(site_assets, site_data.SITE_DIR, dirs_exist_ok=True)
    print(f"  staged {site_data.SITE_DIR.relative_to(site_data.OUT_ROOT)}/ from _assets/"
          + (" + site assets" if site_assets.exists() else ""))


def write_js_blocks() -> None:
    """Write the site's data into the staged runtime JS (see jsblocks.py):
    METER_REGISTRY from the meters file (meters_file), POINTS from data/points.yaml,
    BACNET_CONFIG from site.yaml `bacnet:`, ReportUrls from
    data/reports.yaml `urls:` and REPORT_CARDS from its placements
    (report_cards). SIDEBAR_HTML is written by build_sidebar(),
    which owns that rendering. live-points.js's OVERRIDE_FILE block — the
    Optergy display that point overrides post to — is site.yaml
    `optergy_override_display` ("" if unset)."""
    meters = read_meter_rows()
    jsblocks.inject(site_data.METERS_JS, jsblocks.METER_REGISTRY, jsblocks.render_meter_registry(meters))
    jsblocks.inject(site_data.METERS_JS, jsblocks.POINTS, jsblocks.render_points(read_points()))
    jsblocks.inject(site_data.METERS_JS, jsblocks.BACNET_CONFIG, jsblocks.render_bacnet_config(site_data.BACNET))
    jsblocks.inject(site_data.REPORTS_JS, jsblocks.REPORT_URLS,
                    jsblocks.render_report_urls(_read_data("reports.yaml", "urls", {})))
    jsblocks.inject(site_data.REPORTS_JS, jsblocks.REPORT_CARDS, jsblocks.render_report_cards(report_cards()[0]))
    override_display = read_building().get("optergy_override_display")
    jsblocks.inject(site_data.LIVE_POINTS_JS, jsblocks.OVERRIDE_FILE,
                    jsblocks.render_override_file(str(override_display) if override_display else ""))


def derive_summary_cards(
    roles: tuple[str, ...],
    floor_key: str,
    bindings: dict[tuple[str, str], dict],
    leading: list[dict] | None = None,
) -> list[dict]:
    """Compose a summary_cards list for a tab from the role catalog + bindings.

    Each role emits one card. If a (role, floor) binding exists in points.yaml `floors:`,
    the card is live (id + bacnet + format). Otherwise a static "N/A" placeholder
    is emitted so the layout stays stable across floors.
    """
    cards: list[dict] = list(leading) if leading else []
    for role in roles:
        meta = site_data.SUMMARY_ROLES[role]
        binding = bindings.get((role, floor_key))
        if binding:
            cards.append(
                {
                    "title": meta["title"],
                    "id": binding["id"],
                    "bacnet": binding["bacnet"],
                    "format": meta["format"],
                }
            )
        else:
            cards.append({"title": meta["title"], "value": "N/A"})
    return cards


# ─── Floor Summary section (e.g. Total Electricity / Tenants / Landlords) ────
# These are floor-level aggregate/calculated meters, not part of the riser
# grid — identified in meters.csv by `function` (with `column: null`, so
# `derive_layout` below skips them) rather than by position. Which cards a
# floor page shows, and the function each binds to, is site.yaml
# floor_page.summary_cards. At most one meter per (floor, function) is
# expected; until a floor has one, its card renders a static "N/A"
# placeholder (see `floor_summary_card` in macros.j2).
def find_floor_summary_meter(
    meters: list[dict], floor_key: str, function: str, registry_names: list[str] | None = None
) -> dict | None:
    """The METER_REGISTRY row for (floor_key, function), or None if absent.

    Each of these three cards is single-valued per floor by design. Main-page
    lookups (registry_names=None) match against every row for (floor,
    function), same as always.

    Tenant-page lookups (registry_names given) only ever use a row with
    `tenant_display` set and tagged to this tenant (e.g. a "<Tenant> Level
    NN Electricity" override meter) — the generic/landlord row for the same
    role (the building-wide "Floor Total Electricity" calc meter) is never
    used as a fallback there. No matching override means
    the card renders "N/A" on that tenant's page rather than silently
    reusing the shared row.
    """
    matches = [m for m in meters if floor_key in m["floors"] and m["function"] == function]
    if registry_names is not None:
        matches = [
            m for m in matches
            if m["tenant_display"] and any(n in m["tenants"] for n in registry_names)
        ]
    if len(matches) > 1:
        raise SystemExit(
            f"floor={floor_key!r}: {len(matches)} meters tagged function={function!r} "
            f"in METER_REGISTRY — expected at most one (ids: {[m['id'] for m in matches]})"
        )
    return matches[0] if matches else None


def derive_floor_summary_cards(
    meters: list[dict], floor_key: str, registry_names: list[str] | None = None
) -> dict[str, dict]:
    """{'total_card': {...}, 'tenants_card': {...}, 'landlords_card': {...}}
    for the floor_summary_card macro — live (meter_id set) if METER_REGISTRY
    has a matching row, otherwise a static-N/A card (title/wrapper_class only).
    `registry_names` (tenant pages only) restricts matches to this tenant's
    own tenant_display'd override row — see find_floor_summary_meter.
    """
    cards: dict[str, dict] = {}
    for key, function in site_data.FLOOR_PAGE["summary_cards"].items():
        card = {"title": function, **FLOOR_SUMMARY_CARDS[key]}
        meter = find_floor_summary_meter(meters, floor_key, function, registry_names)
        if meter:
            card["meter_id"] = meter["id"]
        cards[f"{key}_card"] = card
    return cards


def derive_zone_location(utilities: set[str]) -> str:
    """The card subtitle below the zone name (see DEFAULT_ZONE_SUBTITLES)."""
    codes = [code for code in site_data.UTILITIES if code in utilities]  # catalog order
    kinds = "+".join(k for k in UTILITY_KINDS if any(site_data.UTILITIES[c]["kind"] == k for c in codes))
    return site_data.FLOOR_PAGE["zone_subtitles"].get(kinds) or " & ".join(site_data.UTILITIES[c]["label"] for c in codes)


def derive_layout(
    meters: list[dict],
    floor_key: str,
    floorplan_image: str,
    floorplan_after_column: int = 0,
) -> list[dict]:
    """
    Build the floor's layout list from meters pinned to that floor.

    Meters are grouped by (column, zone) into floor-cards. Cards within a
    column are ordered by the minimum `position` of their meters. The
    floorplan image is inserted after column `floorplan_after_column`
    (default 0 — i.e. between columns 0 and 1).

    Meters with no pinned `column` (e.g. the floor-level aggregate meters
    looked up by `find_floor_summary_meter`) are not part of this grid and
    are excluded — a bare `None` column would also break `sorted(grouped)`
    below by mixing `None` and `int` keys.
    """
    on_floor = [m for m in meters if floor_key in m["floors"] and m["column"] is not None]
    if not on_floor:
        # No registry meters on this floor — caller falls back to YAML layout.
        return []

    # column -> zone -> [meter rows in that zone]
    grouped: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for m in on_floor:
        grouped[m["column"]][m["zone"]].append(m)

    layout: list[dict] = []
    for col_idx in sorted(grouped):
        zones = grouped[col_idx]
        # Order zones by the earliest position they contain; meters inside
        # each zone by position too.
        ordered_zones = sorted(
            zones.items(), key=lambda kv: min(m["position"] for m in kv[1])
        )
        cards = []
        for zone_name, zone_meters in ordered_zones:
            zone_meters.sort(key=lambda m: m["position"])
            # Base codes, not the raw field: a card of virtual LTHW meters
            # still gets the "Heat Energy" subtitle.
            utilities = {base_utility(m["utility"]) for m in zone_meters if m["utility"]}
            cards.append(
                {
                    "title": zone_name,
                    "location": derive_zone_location(utilities),
                    "meters": [
                        {
                            "id": m["id"],
                            "label": m["function"] or m["tag"],
                            "utility": m["utility"] or None,
                        }
                        for m in zone_meters
                    ],
                }
            )
        layout.append({"type": "cards", "cards": cards})

    # Slot the floorplan into the layout
    insert_at = min(floorplan_after_column + 1, len(layout))
    layout.insert(insert_at, {"type": "floorplan", "image": floorplan_image})
    return layout


def level_layout(level: dict) -> dict:
    """A level's FLOOR_LAYOUT settings: site.yaml floor_page's, with the
    level's own on top."""
    return site_data.FLOOR_PAGE["layout"] | level["layout"]


def floor_layout(level: dict, layout: list[dict]) -> dict:
    """The floorplan tab's layout fields for a page of `level` whose card
    columns are `layout` (derive_layout's): floorplan, summary_layout and
    columns, with meter_columns: auto resolved to the columns its cards use."""
    settings = level_layout(level)
    columns = settings["meter_columns"]
    if columns == "auto":
        used = sum(col["type"] == "cards" for col in layout)
        columns = min(max(used, 1), MAX_METER_COLUMNS)
    return {"floorplan": settings["floorplan"], "summary_layout": settings["summary_layout"], "columns": columns}


# ─── Jinja env / build ───────────────────────────────────────────────────────
def make_env() -> Environment:
    env = Environment(
        # Site overrides first: site/templates/<name> replaces the engine's
        # _templates/<name> (e.g. a bespoke incomer_electricity.html.j2).
        loader=FileSystemLoader([str(site_data.SITE_ROOT / "templates"), str(TEMPLATES_DIR)]),
        # A missing field is an error, not a silently blank page fragment.
        # Genuinely optional fields are guarded in the templates
        # (`is defined` / `|default` / `.get()`).
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    # Site/building facts available to every template as `building`.
    env.globals["building"] = read_building()
    # floor_page config with defaults (read_page_config) — riser card links,
    # the centre zone and zone-title suffixes in floor/tenant-floor pages.
    env.globals["floor_page"] = site_data.FLOOR_PAGE
    # The point-address rule, for templates that build data-bacnet
    # attributes themselves (meter_node in partials/macros.j2).
    env.globals["bacnet_address"] = bacnet_address
    env.globals["demand_address"] = demand_address
    # Extras (data/extras.yaml): components placed into the engine pages'
    # slots — slot("<name>") in floor/incomer/home.html.j2.
    problems: list[str] = []
    catalog = read_component_catalog()
    placements = components.resolve(read_extras(), catalog, extras_pages(), problems, [])
    if problems:
        raise SystemExit("data/extras.yaml:\n" + "\n".join(f"  - {p}" for p in problems))
    RENDERED_SLOTS.clear()
    env.globals["slot"] = components.slot_renderer(env, catalog, placements, RENDERED_SLOTS)
    env.globals["fragment"] = render_fragment
    return env


# ─── Extras ──────────────────────────────────────────────────────────────────
# A site adds components (an image, an HTML fragment, …) to engine pages by
# placing them in slots — data/extras.yaml, checked against each component's
# declared options. See components.py and README "Extras".

# (page key, slot) for every slot rendered by this process's builds, so
# --check can report placements that never appeared (a module that's off, or
# a site template override without the slot).
RENDERED_SLOTS: set[tuple[str, str]] = set()


def read_component_catalog() -> dict[str, dict]:
    """The engine's components, with the site's own (site/components/)
    replacing any of the same name."""
    return components.load_catalog(COMPONENTS_DIR, site_data.SITE_ROOT / "components")


def read_extras() -> list[dict]:
    return _read_data("extras.yaml", "extras", [])


def extras_pages() -> dict[str, str]:
    """{page key: page kind} for every page an extra can name: the floor
    pages, the incomer pages and home."""
    pages = {lv["page_key"]: "floor" for lv in read_levels() if lv["page"]}
    pages |= {str(key): "incomer" for key in (read_incomers() or {})}
    pages["home"] = "home"
    return pages


@pass_context
def render_fragment(ctx, name: str) -> str:
    """site/pages/<name>, rendered like a frozen page's fragment ({{ path_prefix }},
    {{ building.* }}) — the `html` component's body."""
    path = site_data.SITE_ROOT / "pages" / str(name)
    if not path.is_file():
        raise SystemExit(f"extras: fragment {_rel(path)} not found")
    return ctx.environment.from_string(path.read_text(encoding="utf-8")).render(
        path_prefix=ctx.get("path_prefix") or "").strip("\n")


def build_floors(env: Environment, only: str | None = None) -> list[Path]:
    floors_file = data_path("floors.yaml")
    if not floors_file.exists():
        print(f"  (skip floors: {floors_file} not found)")
        return []

    meters = read_meters()
    # Meters can opt out of the main floor pages via `main_display: no` in
    # the registry (e.g. a meter being moved to tenant-only display) without
    # touching their placement fields — those stay shared with the tenant
    # builder's own, separately-filtered list (build_tenants' `this_floor`).
    main_meters = [m for m in meters if m["main_display"]]
    bindings = read_bms_bindings()
    reports = read_reports()
    building = env.globals.get("building", {})
    ems_name = building.get("ems_name", "EMS")
    template = env.get_template("floor.html.j2")
    written: list[Path] = []

    for level in read_levels():
        key, floor_key = level["page_key"], level["key"]
        if not level["page"] or (only and only != key):
            continue
        ctx = dict(level["data"])
        out_dir, location_ctx = page_location(level["building"])
        folder = page_folder(level["building"])
        for k, v in location_ctx.items():
            ctx.setdefault(k, v)

        ctx.setdefault("container_class", "floor-container")
        ctx["page_kind"], ctx["page_key"] = "floor", key
        ctx["heading"] = level["heading"]
        ctx.setdefault("page_title", f"{ctx['heading']} · {ems_name}")
        ctx.setdefault("tabs", [{"id": "floorplan", "label": site_data.FLOOR_PAGE["summary_label"]}]
                       + [{"id": t["id"], "label": t["label"]} for t in site_data.FLOOR_PAGE["tabs"]])

        # Floorplan tab: derive layout + summary_cards unless YAML supplies them.
        fp_tab = dict(ctx.get("floorplan_tab") or {})
        if "layout" not in fp_tab:
            image = relative_url(fp_tab.get("floorplan_image") or default_floorplan_image(floor_key), folder)
            after_col = fp_tab.get("floorplan_after_column", 0)
            fp_tab.setdefault("image", image)
            fp_tab["layout"] = derive_layout(main_meters, floor_key, image, after_col)
            if not fp_tab["layout"]:
                raise SystemExit(
                    f"{key}: no meters pinned to floor={floor_key!r} in {meters_file().name} "
                    f"and no `layout:` in YAML — cannot render."
                )
        if "image" in fp_tab:
            fp_tab["image"] = relative_url(fp_tab["image"], folder)
        for card_key, card in derive_floor_summary_cards(main_meters, floor_key).items():
            fp_tab.setdefault(card_key, card)
        fp_tab.update(floor_layout(level, fp_tab["layout"]))
        ctx["floorplan_tab"] = fp_tab

        # Report tabs (floor_page.tabs): each tab's summary cards from its
        # roles, then the floor's report placements for its slot, titled by
        # position (floor_page.report_titles, e.g. Demand then Consumption).
        # A floor without data for a slot gets "N/A" cards and no reports,
        # same as any other not-yet-wired role.
        report_tabs = []
        for tab in site_data.FLOOR_PAGE["tabs"]:
            cards = reports_to_cards(reports_for(reports, page="floor", floor=floor_key, slot=tab["slot"]))
            for i, card in enumerate(cards):
                if (title := floor_report_title(i)) is not None:
                    card.setdefault("title", title)
            report_tabs.append({
                "id":            tab["id"],
                "label":         tab["label"],
                "summary_cards": derive_summary_cards(tab["roles"], floor_key, bindings),
                "reports":       cards,
            })
        ctx["report_tabs"] = report_tabs

        html = render_page(template, ctx)
        out_path = out_dir / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")

    return written


def build_incomers(env: Environment, only: str | None = None) -> list[Path]:
    """Render incomer pages from points.yaml `incomers:`. The engine's
    incomer.html.j2 supports the simple form (summary cards + reports) and
    the rich form (+ stat_grids + headed report). An entry may name a
    different template with `template:` — e.g. a site override in
    site/templates/ for a bespoke layout."""
    incomers = read_incomers()
    if incomers is None:
        print("  (skip incomers: no points.yaml `incomers:` or incomers.yaml)")
        return []

    where = point_source("incomers")
    reports = read_reports()
    building = env.globals.get("building", {})
    ems_name = building.get("ems_name", "EMS")
    written: list[Path] = []

    for key, raw in incomers.items():
        if only and only != key:
            continue
        ctx = dict(raw or {})
        # Placement/menu fields, not page data — and `building` would shadow
        # the template's `building` global.
        out_dir, location_ctx = page_location(check_building(ctx.pop("building", None), f"{where} '{key}'"))
        ctx.pop("nav_label", None)
        for k, v in location_ctx.items():
            ctx.setdefault(k, v)
        ctx["page_kind"], ctx["page_key"] = "incomer", key
        ctx.setdefault("page_title", f"{ctx.get('heading', '')} · {ems_name}")

        if "reports" not in ctx:
            incomer_slug = key.removeprefix("incomer_")
            derived = reports_for(reports, page="incomer", incomer=incomer_slug, slot="main")
            ctx["reports"] = reports_to_cards(derived)

        tmpl_name = ctx.pop("template", "incomer.html.j2")
        html = render_page(env.get_template(tmpl_name), ctx)
        out_path = out_dir / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")

    return written


# The meters hierarchy page's texts for a site without meters_hierarchy.yaml.
HIERARCHY_DEFAULTS = {
    "page_title": "Meters Hierarchy",
    "heading": "Meters Hierarchy",
    "subtitle": "Click on meters to expand/collapse child connections",
    "search_placeholder": "Search for a meter...",
}


def build_meters_hierarchy(env: Environment, only: str | None = None) -> list[Path]:
    """Render meters_hierarchy.htm by walking the parent_id tree in
    METER_REGISTRY from one or more configurable roots — e.g. one per
    utility (electricity / CHW / LTHW), each with its own top-level meter
    that carries no parent_id of its own. meters_hierarchy.yaml is optional:
    without it the page takes HIERARCHY_DEFAULTS, and its roots are the
    meters marked `parent: 0`, and those with no parent that feed another."""
    if only and only != "meters_hierarchy":
        return []
    data_file = data_path("meters_hierarchy.yaml")
    ctx = (yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}) if data_file.exists() else None

    meters = read_meters()
    by_id: dict[int, dict] = {m["id"]: m for m in meters}
    children_map: dict[int, list[dict]] = defaultdict(list)
    for m in meters:
        if m["parent_id"] is not None:
            children_map[m["parent_id"]].append(m)
    # Children ordered by id within each parent (matches committed page).
    for parent_id in children_map:
        children_map[parent_id].sort(key=lambda x: x["id"])

    # root_meter_ids (a list) supports several independent trees — e.g. one
    # root per utility. root_meter_id (singular, one id) is kept working for
    # a single-tree page.
    if ctx is None:
        ctx = dict(HIERARCHY_DEFAULTS, root_meter_ids=sorted(
            m["id"] for m in meters if m["parent_id"] == 0 or (m["parent_id"] is None and m["id"] in children_map)))
    root_ids = ctx.get("root_meter_ids")
    if root_ids is None:
        root_ids = [ctx.get("root_meter_id", 97)]
    missing = [r for r in root_ids if r not in by_id]
    if missing:
        raise SystemExit(f"meters_hierarchy: root_meter_id(s) {missing} not in METER_REGISTRY")
    ctx["root_meters"] = [by_id[r] for r in root_ids]
    ctx["children_map"] = dict(children_map)

    template = env.get_template("meters_hierarchy.html.j2")
    html = render_page(template, ctx)
    out_path = site_data.SITE_DIR / "meters_hierarchy.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return [out_path]


# ─── Tenants ─────────────────────────────────────────────────────────────────
# Each tenant page lives at project/tenants/<tenant-slug>/<page>.htm — a
# sibling of SITE_DIR (project/<site-slug>/), not nested inside it. Asset
# paths and the sidebar script resolve via `path_prefix` ("../../<site-slug>//"),
# i.e. up two levels (tenants/<tenant-slug>/ → tenants/ → project/) then into
# the site directory (TENANT_PATH_PREFIX, set by configure()). Floor
# placement and meter assignment derive from METER_REGISTRY: meters whose
# `tenant` field contains the tenant slug AND whose `floor` matches the page.

def build_tenants(env: Environment, only: str | None = None) -> list[Path]:
    tenants = read_tenants()
    if not tenants:
        print(f"  (skip tenants: no tenants.yaml `{TENANTS_KEY}:`)")
        return []

    meters = read_meters()
    reports = read_reports()
    bindings = read_bms_bindings()
    levels = {lv["key"]: lv for lv in read_levels()}
    rank = level_rank()
    floor_template = env.get_template("tenant_floor.html.j2")
    index_template = env.get_template("tenant_index.html.j2")
    sidebar_template = env.get_template("tenant_sidebar.js.j2")
    written: list[Path] = []

    for tenant in tenants:
        slug, display_name, data = tenant["slug"], tenant["name"], tenant["data"]
        if only and only != f"tenant_{slug}":
            continue
        tenant_dir = site_data.TENANTS_DIR / slug
        tenant_dir.mkdir(parents=True, exist_ok=True)

        # A meter is the tenant's when meters.csv's `tenant` column carries
        # one of its short names (the catalog key; a legacy tenants.yaml's
        # registry_tenant, which may list several spellings).
        registry_names = tenant["short_names"]

        # Floors this tenant occupies (derived from registry), plus any
        # `extra_floors` the tenant YAML adds by hand (e.g. a Basement level
        # with no METER_REGISTRY rows yet — same "N/A" fallback as any other
        # not-yet-wired floor), minus any `exclude_floors` — a floor a
        # registry row tags this tenant onto (e.g. a calc meter with no
        # tenant_display yet) that shouldn't get its own page until it's
        # actually wired up. Ordered top floor first, going down — the
        # floors.yaml roster order reversed, matching the main sidebar's
        # floor order (_auto_floors).
        tenant_meters = [m for m in meters if any(n in m["tenants"] for n in registry_names)]
        floor_keys = {f for m in tenant_meters for f in m["floors"]} | {str(f) for f in data.get("extra_floors") or []}
        floor_keys -= {str(f) for f in data.get("exclude_floors") or []}
        floors_occupied = sort_floors(floor_keys, rank, tenant["where"], top_first=True)
        if not floors_occupied:
            print(f"  WARNING: tenant {slug!r} has no meters in METER_REGISTRY — skipping")
            continue

        has_index = "index" in data
        floors_data = data.get("floors") or {}

        # ── tenant index.htm ──
        if has_index:
            idx = data["index"]
            idx_reports = idx.get("reports")
            if idx_reports is None:
                idx_reports = reports_to_cards(reports_for(
                    reports, page="tenant_index", tenant=slug, slot="main"
                ))
            ctx = {
                "page_title":    idx.get("page_title", f"{display_name} - Summary"),
                "heading":       idx.get("title", f"{display_name} - Floor Summary"),
                "container_class": "floor-container",
                "tenant_name":   display_name,
                "floors_occupied": ", ".join(levels[f]["label"] for f in floors_occupied),
                "reports":       idx_reports,
                "path_prefix":   site_data.TENANT_PATH_PREFIX,
                "sidebar_src":   "sidebar-template.js",
            }
            html = render_page(index_template, ctx)
            out_path = tenant_dir / "index.htm"
            out_path.write_text(html, encoding="utf-8", newline="\n")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(site_data.OUT_ROOT)}")

        # ── tenant floor pages ──
        for floor_key in floors_occupied:
            floor_data = dict(floors_data.get(floor_key) or {})
            # Filter meters for this tenant+floor and derive layout via existing engine.
            # `tenant_display` (CSV column) is the explicit gate — a meter
            # never appears on any tenant page unless it's marked "yes",
            # regardless of tenant tag. Meters that pass the gate are still
            # scoped to the tenant's own meters plus untagged landlord/
            # common-area meters (e.g. the North mechanical/LTHW/CHW column);
            # meters tagged to a *different* tenant (shared floors like
            # ground, split between two retail units) are excluded even if
            # tenant_display is yes.
            this_floor = [
                m for m in meters
                if floor_key in m["floors"]
                and m["tenant_display"]
                and (not m["tenants"] or any(n in m["tenants"] for n in registry_names))
            ]

            # Default header_link "#" on tenant cards (no riser_overview hop)
            for m in this_floor:
                m["header_link"] = "#"  # will be picked up by derive_layout's cards

            image = floor_data.get("floorplan_image") or (site_data.TENANT_PATH_PREFIX + default_floorplan_image(floor_key).lstrip("/"))
            after_col = floor_data.get("floorplan_after_column", 0)
            layout = derive_layout(this_floor, floor_key, image, after_col)
            # Override header_link on every card to "#"
            for col in layout:
                if col.get("type") == "cards":
                    for card in col["cards"]:
                        card["header_link"] = "#"

            # Floorplan tab: same shape as build_floors() — Floor Summary
            # (Total/Tenants/Landlords Electricity) cards + image, then the
            # riser grid. `registry_names` restricts each card to this
            # tenant's own tenant_display'd override meter (e.g. a
            # "<Tenant> Level NN Electricity" meter) rather than falling back to
            # the shared generic row — see find_floor_summary_meter. A role
            # with no override for this tenant renders "N/A".
            floorplan_tab = {"layout": layout, "image": image, **floor_layout(levels[floor_key], layout)}
            for card_key, card in derive_floor_summary_cards(meters, floor_key, registry_names).items():
                floorplan_tab[card_key] = card

            # Report tabs: tenant_page.tabs (a subset of floor_page.tabs) — a
            # tenant without registry/YAML data for a slot just gets an empty
            # reports list, same as any not-yet-wired floor. A card shows the
            # same title as on the floor page (REPORT_CARDS, report_cards).
            tabs = [{"id": "floorplan", "label": floor_data.get("floorplan_tab_label", site_data.TENANT_PAGE["summary_label"])}]
            report_tabs = []
            for tab in site_data.TENANT_PAGE["tabs"]:
                tabs.append({"id": tab["id"], "label": tab["label"]})
                tab_reports = floor_data.get(f"{tab['slot']}_reports")
                if tab_reports is None:
                    # No report placements are ever tagged page="tenant_floor"
                    # today (that'd mean a separate, tenant-scoped report library
                    # item per floor/slot, which doesn't exist) — fall back to
                    # the same floor's own page="floor" rows, so a tenant's
                    # report tab shows the identical report the main floor page
                    # does, with no duplicate registry entries required.
                    rows = reports_for(reports, page="tenant_floor", tenant=slug, floor=floor_key, slot=tab["slot"])
                    if not rows:
                        rows = reports_for(reports, page="floor", floor=floor_key, slot=tab["slot"])
                    tab_reports = reports_to_cards(rows)
                report_tabs.append({
                    "id":            tab["id"],
                    "label":         tab["label"],
                    "summary_cards": derive_summary_cards(tab["roles"], floor_key, bindings),
                    "reports":       tab_reports,
                })

            ctx = {
                "page_title":      floor_data.get("page_title", f"{display_name} - Floor Overview"),
                "heading":         floor_data.get("heading", f"{levels[floor_key]['label']} Overview"),
                "container_class": "floor-container",
                "tabs":            tabs,
                "floorplan_tab":   floorplan_tab,
                "path_prefix":     site_data.TENANT_PATH_PREFIX,
                "sidebar_src":     "sidebar-template.js",
                "report_tabs":     report_tabs,
            }

            html = render_page(floor_template, ctx)
            out_path = tenant_dir / f"floor_{floor_key}.htm"
            out_path.write_text(html, encoding="utf-8", newline="\n")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(site_data.OUT_ROOT)}")

        # ── tenant sidebar-template.js ──
        floor_links = [
            {"href": f"floor_{f}.htm", "label": levels[f]["label"]}
            for f in floors_occupied
        ]
        sidebar_ctx = {
            "tenant_name":  display_name,
            "path_prefix":  site_data.TENANT_PATH_PREFIX,
            "has_index":    has_index,
            "floor_links":  floor_links,
            "docs_href":    tenant["docs"],
        }
        sidebar_js = render_page(sidebar_template, sidebar_ctx)
        out_path = tenant_dir / "sidebar-template.js"
        out_path.write_text(sidebar_js, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(site_data.OUT_ROOT)}")

    return written


def build_schematics(env: Environment, only: str | None = None) -> list[Path]:
    """Render riser_*.htm + tariff_*.htm from site/data/schematics.yaml.

    Each page is an SVG background + a list of positioned overlay widgets.
    """
    data_file = data_path("schematics.yaml")
    if not data_file.exists():
        print(f"  (skip schematics: {data_file} not found)")
        return []
    pages = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}
    building = env.globals.get("building", {})
    template = env.get_template("schematic.html.j2")
    written: list[Path] = []

    for key, raw in pages.items():
        if only and only != key:
            continue
        ctx = dict(raw or {})
        ctx.setdefault("page_title", f"{building.get('name', '')} - Dashboard")
        ctx.setdefault("container_class", "floor-container")

        html = render_page(template, ctx)
        out_path = site_data.SITE_DIR / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return written


# ─── Sidebar ─────────────────────────────────────────────────────────────────
# The main sidebar (js/project/2.0/sidebar-template.js, SIDEBAR_JS) is
# generated from site/data/sidebar.yaml. Only the SIDEBAR_HTML constant
# between the BEGIN/END markers is touched; the runtime behaviour code below
# is hand-maintained.


# Auto-list expansion: maps `auto: <type>` to the function that produces
# the list of items the parent's children should be expanded with.
def _auto_floors() -> list[dict]:
    """Floor menu-items for every level with a page, top floor first."""
    return [
        {"_key": lv["key"], "_building": lv["building"], "label": lv["nav_label"],
         "href": site_href(lv["building"], f"{lv['page_key']}.htm")}
        for lv in reversed(read_levels())
        if lv["page"]
    ]


def _auto_incomers() -> list[dict]:
    data = read_incomers() or {}
    items: list[dict] = []
    for page_key, entry in data.items():
        entry = entry or {}
        slug = page_key.removeprefix("incomer_")
        building = entry.get("building")
        items.append({
            "_key":      slug,
            "_building": building,
            # nav_label if given; else incomer_<code> is labelled by its
            # utility, and any other key by name.
            "label":     entry.get("nav_label") or (site_data.UTILITIES[slug]["label"] if slug in site_data.UTILITIES else slug.capitalize()),
            "href":      site_href(building, f"{page_key}.htm"),
        })
    return items


def _auto_switchboards() -> list[dict]:
    """Switchboard sub-items: 'LV-01', 'LV-02', etc. Driven by switchboards.yaml."""
    sb_file = data_path("switchboards.yaml")
    if not sb_file.exists():
        return []
    cfg = yaml.safe_load(sb_file.read_text(encoding="utf-8")) or {}
    boards = cfg.get("boards") or {}
    items: list[dict] = []
    for key, board in boards.items():
        # nav_label if given; else swb_lv01 → "LV-01"
        suffix = key.removeprefix("swb_")
        if (board or {}).get("nav_label"):
            label = str(board["nav_label"])
        elif suffix.lower().startswith("lv") and suffix[2:].isdigit():
            label = f"LV-{int(suffix[2:]):02d}"
        else:
            label = suffix.upper()
        building = (board or {}).get("building")
        items.append({"_key": key, "_building": building, "label": label, "href": site_href(building, f"{key}.htm")})
    return items


def _auto_risers() -> list[dict]:
    """Riser sub-items: one per riser meter, linking to its first page."""
    return build_risers.sidebar_items()


def _auto_buildings(auto_lists: dict, icon: str | None) -> list[dict]:
    """One sub-menu per site.yaml building: its floors (top first), then its
    incomers and switchboards."""
    items: list[dict] = []
    for b in site_data.BUILDINGS:
        children = [_public(it) for name in ("floors", "incomers", "switchboards")
                    for it in auto_lists[name] if it.get("_building") == b["key"]]
        item = {"_key": b["key"], "label": b["name"], "children": children}
        if icon:
            item["icon"] = icon
        items.append(item)
    return items


def _public(item: dict) -> dict:
    """An auto-list item without its internal `_key` / `_building` fields."""
    return {k: v for k, v in item.items() if not k.startswith("_")}


def _auto_tenants(meters: list[dict]) -> list[dict]:
    """Tenant menu-items in catalog order; href varies by whether the
    tenant has an index page or only a single floor view."""
    rank = level_rank()
    items: list[dict] = []
    for tenant in read_tenants():
        slug, display_name, data = tenant["slug"], tenant["name"], tenant["data"]
        # Match meters.csv's `tenant` column on the short names, the same
        # way build_tenants() does.
        tenant_meters = [m for m in meters if any(n in m["tenants"] for n in tenant["short_names"])]
        floors_occupied = sort_floors({f for m in tenant_meters for f in m["floors"]}, rank, tenant["where"])
        if "index" in data:
            href = f"/docs/tenants/{slug}/index.htm"
        elif floors_occupied:
            href = f"/docs/tenants/{slug}/floor_{floors_occupied[0]}.htm"
        else:
            href = f"/docs/tenants/{slug}/index.htm"
        items.append({
            "_key":   slug,
            "label":  display_name, "href": href,
            "target": "_blank", "rel": "noopener noreferrer",
        })
    return items


def _apply_only_filter(items: list[dict], only: list[str] | None) -> list[dict]:
    """Reorder + filter `items` by `only` (list of `_key` values).
    Items missing from `only` are dropped; order follows `only`."""
    if not only:
        return [_public(it) for it in items]
    by_key = {it.get("_key"): it for it in items}
    out: list[dict] = []
    for key in only:
        it = by_key.get(key)
        if it is None:
            continue
        out.append(_public(it))
    return out


def _apply_groups(items: list[dict], groups: list[dict]) -> list[dict]:
    """Bucket a flat auto-list into labelled range sub-menus.

    Each group is `{label, from, to}` where from/to are `_key` values
    (inclusive) marking the two ends of a contiguous slice of `items` in
    its existing order — the sidebar-nav equivalent of "Floors 37th-47th".
    A group whose from/to key isn't present in `items` (e.g. a basement
    floor this site doesn't define) is dropped rather than producing a
    dead link. Sites that just want every item listed flat simply omit
    `groups` — this is opt-in per auto-list, not a global mode.
    """
    by_key_index = {it.get("_key"): i for i, it in enumerate(items)}
    out: list[dict] = []
    for g in groups:
        i_from, i_to = by_key_index.get(str(g.get("from"))), by_key_index.get(str(g.get("to")))
        if i_from is None or i_to is None:
            continue
        lo, hi = sorted((i_from, i_to))
        members = [_public(it) for it in items[lo:hi + 1]]
        if members:
            out.append({"label": g["label"], "children": members})
    return out


def _expand_auto(children: list[dict], auto_lists: dict) -> list[dict]:
    """Walk a children list and replace {auto: <type>} markers with the
    corresponding expanded item list. Supports `building: <key>` to keep
    one building's items, `only: [<key>, ...]` to filter + reorder the auto
    list, or `groups: [{label, from, to}, ...]` to bucket it into range
    sub-menus instead (see _apply_groups). `auto: buildings` expands to one
    sub-menu per building (see _auto_buildings; `icon:` applies to each)."""
    out: list[dict] = []
    for child in children:
        auto = child.get("auto")
        if auto == "buildings":
            out.extend(_public(it) for it in _auto_buildings(auto_lists, child.get("icon")))
            continue
        if auto:
            base = auto_lists.get(auto, [])
            if "building" in child:
                b = check_building(child["building"], f"sidebar.yaml `auto: {auto}`")
                base = [it for it in base if it.get("_building") == b]
            if child.get("groups"):
                out.extend(_apply_groups(base, child["groups"]))
            else:
                out.extend(_apply_only_filter(base, child.get("only")))
            continue
        if child.get("children"):
            child = dict(child)
            child["children"] = _expand_auto(child["children"], auto_lists)
        out.append(child)
    return out


# The sidebar runtime, loaded by sidebar-template.js from a page-relative URL
# (its SIDEBAR_RUNTIME block); a building folder's copy points it up a level.
SIDEBAR_RUNTIME = "js/project/2.0/sidebar.js"


# ─── Pages: what a site builds, and its menu ─────────────────────────────────
# data/pages.yaml in its menu shape lists every page the site builds, laid
# out as the sidebar menu it generates:
#   sections: [{header, items}], top_items, bottom_items — the menu's items;
#   unlisted: [ … ] — page entries built but not in the menu;
#   brand, footer — the menu's header and footer (default: site.yaml's).
# An item is a sub-menu {label, icon?, children}, an outside link {label,
# href, icon?, target?, rel?, class?}, {kind: theme_toggle}, or a page entry:
#   {pages: <family>, only?, groups?, building?} — a family's pages, listed
#       in place; with a `label:` (and `icon:`) they become its sub-menu;
#   {label, page: <key>} — one page: a generated one (home, meters_hierarchy,
#       a schematic, a floor, incomer or board page, …) or one of the site's
#       own, rendered from site/templates/<key>.html.j2, else from
#       site/pages/<key>.*.html fragments, else as an empty page (the header
#       and scripts). An own page may set OWN_PAGE_FIELDS.
# The modules to run come from these entries, so such a site has no
# sidebar.yaml and no site.yaml `modules:`. An older site's pages.yaml is a
# `pages:` list of frozen pages, beside both.
MENU_KEYS = ("brand", "footer", "top_items", "sections", "bottom_items", "unlisted")
# A family → the modules that build its pages.
PAGE_FAMILIES = {
    "floors": ("floors",), "incomers": ("incomers",), "switchboards": ("switchboards",),
    "risers": ("risers",), "tenants": ("tenants",), "buildings": ("floors", "incomers", "switchboards"),
}
# Modules that build one page, <key>.htm, named by the module.
SINGLE_PAGES = ("home", "meters_hierarchy", "building_performance", "energy_flow", "dials")
OWN_PAGE_FIELDS = ("out", "page_title", "heading", "container_class", "container_style",
                   "layout_mode", "no_optergy", "building")
LINK_FIELDS = ("label", "icon", "target", "rel", "class")


def read_menu() -> dict | None:
    """data/pages.yaml in its menu shape, checked: {cfg: the sidebar's items
    as sidebar.yaml writes them, modules: [the modules its entries need],
    own: [the site's own pages, {key, out, heading, …}]}. None for a site
    without one — an older site, with sidebar.yaml and site.yaml `modules:`."""
    path = data_path("pages.yaml")
    data = _read_yaml(path)
    if not isinstance(data, dict) or "pages" in data or not data.keys() & set(MENU_KEYS):
        if isinstance(data, dict) and "pages" in data and data.keys() & set(MENU_KEYS):
            raise SystemExit(f"{_rel(path)}: a `pages:` list (frozen pages) or the menu ({', '.join(MENU_KEYS)}), "
                             "not both — list each frozen page in the menu as `page: <key>`")
        return None
    where = _rel(path)
    unknown = sorted(data.keys() - set(MENU_KEYS))
    if unknown:
        raise SystemExit(f"{where}: unknown key(s) {unknown} — the menu has {', '.join(MENU_KEYS)}")
    if data_path("sidebar.yaml").exists():
        raise SystemExit(f"{where} is the menu, so {_rel(data_path('sidebar.yaml'))} isn't read — delete it")
    if "modules" in read_building():
        raise SystemExit(f"{_rel(site_data.BUILDING_FILE)}: `modules:` — {where} decides what's built now; delete `modules:`")

    found: dict = {"modules": {"sidebar"}, "own": {}}
    known = _generated_page_keys()
    cfg = {k: data[k] for k in ("brand", "footer") if k in data}
    for key in ("top_items", "bottom_items"):
        cfg[key] = [_menu_item(it, f"{where} {key}", found, known) for it in data.get(key) or []]
    cfg["sections"] = [
        {**{k: v for k, v in sec.items() if k != "items"},
         "items": [_menu_item(it, f"{where} {sec.get('header', '')}", found, known) for it in sec.get("items") or []]}
        for sec in data.get("sections") or []]
    for entry in data.get("unlisted") or []:
        if not isinstance(entry, dict) or not entry.keys() & {"page", "pages"}:
            raise SystemExit(f"{where} unlisted: {entry!r} — each entry is {{page: <key>}} or {{pages: <family>}}")
        _menu_item(entry, f"{where} unlisted", found, known)
    if found["own"]:
        found["modules"].add("pages")
    return {"cfg": cfg, "modules": [m for m in MODULES if m in found["modules"]], "own": list(found["own"].values())}


def _generated_page_keys() -> dict[str, tuple[str, str | None]]:
    """{page key: (module, building)} for the pages a `page:` entry can name
    that a module generates."""
    keys = {key: (key, None) for key in SINGLE_PAGES}
    keys |= {str(k): ("schematics", None) for k in (_read_yaml(data_path("schematics.yaml")) or {})}
    keys |= {lv["page_key"]: ("floors", lv["building"]) for lv in read_levels() if lv["page"]}
    keys |= {str(k): ("incomers", (e or {}).get("building")) for k, e in (read_incomers() or {}).items()}
    keys |= {str(k): ("switchboards", (b or {}).get("building"))
             for k, b in ((_read_yaml(data_path("switchboards.yaml")) or {}).get("boards") or {}).items()}
    return keys


def _menu_item(item, where: str, found: dict, known: dict) -> dict:
    """One menu item as a sidebar.yaml item, noting in `found` the modules
    and own pages it needs."""
    if not isinstance(item, dict):
        raise SystemExit(f"{where}: {item!r} isn't a menu item")
    if "auto" in item:
        raise SystemExit(f"{where}: `auto: {item['auto']}` — in pages.yaml a family is `pages: {item['auto']}`, "
                         "which builds its pages too")
    if "pages" in item:
        family = item["pages"]
        if family not in PAGE_FAMILIES:
            raise SystemExit(f"{where}: `pages: {family}` isn't a page family ({', '.join(PAGE_FAMILIES)})")
        found["modules"].update(PAGE_FAMILIES[family])
        auto = {"auto": family, **{k: item[k] for k in ("only", "groups", "building") if k in item}}
        if "label" in item:
            return {**{k: item[k] for k in ("label", "icon") if k in item}, "children": [auto]}
        return {**auto, **({"icon": item["icon"]} if "icon" in item else {})}
    if "page" in item:
        key = str(item["page"])
        fields = {k: item[k] for k in OWN_PAGE_FIELDS if k in item}
        if key in known:
            module, building = known[key]
            if fields:
                raise SystemExit(f"{where}: page '{key}' is built by the {module} module, which sets its "
                                 f"{', '.join(fields)} — only the site's own pages take them here")
            found["modules"].add(module)
            href = site_href(building, f"{key}.htm")
        else:
            page = {"key": key, "out": f"{key}.htm", "heading": item.get("label", key), **fields}
            if key in found["own"] and any(found["own"][key].get(k) != v for k, v in fields.items()):
                raise SystemExit(f"{where}: page '{key}' is listed twice with different fields — set them once")
            found["own"].setdefault(key, page)
            href = site_href(check_building(page.get("building"), f"{where} page '{key}'"), page["out"])
        return {**{k: item[k] for k in LINK_FIELDS if k in item}, "href": href}
    if "children" in item:
        sub = f"{where} › {item.get('label', '')}"
        return {**{k: v for k, v in item.items() if k != "children"},
                "children": [_menu_item(c, sub, found, known) for c in item["children"] or []]}
    return dict(item)


def sidebar_cfg() -> dict | None:
    """The sidebar's items, as sidebar.yaml writes them: from the menu in
    pages.yaml, else sidebar.yaml (None: neither)."""
    menu = read_menu()
    if menu:
        return menu["cfg"]
    path = data_path("sidebar.yaml")
    return (_read_yaml(path) or {}) if path.exists() else None


def own_pages() -> list[dict]:
    """The site's own pages, {key, out, heading, …}: the menu's own-page
    entries, or an older site's frozen `pages:` list."""
    menu = read_menu()
    if menu:
        return menu["own"]
    return (_read_yaml(data_path("pages.yaml")) or {}).get("pages") or []


def build_sidebar(env: Environment, only: str | None = None) -> list[Path]:
    if only and only != "sidebar":
        return []
    cfg = sidebar_cfg()
    if cfg is None:
        print(f"  (skip sidebar: neither a menu in {_rel(data_path('pages.yaml'))} nor {_rel(data_path('sidebar.yaml'))})")
        return []
    if not site_data.SIDEBAR_JS.exists():
        print(f"  (skip sidebar: {site_data.SIDEBAR_JS} not found)")
        return []

    cfg = copy.deepcopy(cfg)
    meters = read_meters()

    # Brand + footer are site facts: take them from site.yaml unless the
    # sidebar YAML supplies an explicit override.
    building = read_building()
    if "brand" not in cfg and building.get("brand"):
        cfg["brand"] = building["brand"]
    if "footer" not in cfg and building.get("footer"):
        cfg["footer"] = building["footer"]

    auto_lists = {
        "floors":       _auto_floors(),
        "incomers":     _auto_incomers(),
        "switchboards": _auto_switchboards(),
        "risers":       _auto_risers(),
        "tenants":      _auto_tenants(meters),
    }

    # Expand auto: markers inside top/sections/bottom item lists
    cfg["top_items"] = _expand_auto(cfg.get("top_items") or [], auto_lists)
    cfg["bottom_items"] = _expand_auto(cfg.get("bottom_items") or [], auto_lists)
    for section in cfg.get("sections", []):
        section["items"] = _expand_auto(section.get("items", []), auto_lists)

    template = env.get_template("sidebar.js.j2")
    jsblocks.inject(site_data.SIDEBAR_JS, jsblocks.SIDEBAR_RUNTIME, jsblocks.render_sidebar_runtime(SIDEBAR_RUNTIME))
    jsblocks.inject(site_data.SIDEBAR_JS, jsblocks.SIDEBAR_HTML, render_page(template, {**cfg, "rel": lambda url: url}))
    print(f"  wrote {site_data.SIDEBAR_JS.relative_to(site_data.SITE_DIR)}")
    written = [site_data.SIDEBAR_JS]

    # Campus: each building folder's pages load <folder>/sidebar-template.js
    # (page_location's sidebar_src) — the same file with every link and the
    # runtime's own sidebar.js URL rewritten for that folder.
    if site_data.CAMPUS:
        root_js = site_data.SIDEBAR_JS.read_text(encoding="utf-8")
        for b in site_data.BUILDINGS:
            folder = b["key"]
            out = site_data.SITE_DIR / folder / "sidebar-template.js"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(root_js, encoding="utf-8", newline="\n")
            jsblocks.inject(out, jsblocks.SIDEBAR_RUNTIME,
                            jsblocks.render_sidebar_runtime(relative_url(SIDEBAR_RUNTIME, folder)))
            jsblocks.inject(out, jsblocks.SIDEBAR_HTML,
                            render_page(template, {**cfg, "rel": lambda url, f=folder: relative_url(url, f)}))
            print(f"  wrote {out.relative_to(site_data.SITE_DIR)}")
            written.append(out)
    return written


def build_home(env: Environment, only: str | None = None) -> list[Path]:
    """Render the home landing page from points.yaml `home:` (singleton)."""
    if only and only != "home":
        return []
    home = read_home()
    if home is None:
        print("  (skip home: no points.yaml `home:` or home.yaml)")
        return []

    ctx = dict(home)
    building = env.globals.get("building", {})
    ctx.setdefault("page_title", f"{building.get('name', '')} - Dashboard")
    ctx.setdefault("container_class", "floor-container")
    ctx["page_kind"], ctx["page_key"] = "home", "home"

    reports = read_reports()
    if "top_reports" not in ctx:
        ctx["top_reports"] = reports_to_cards(reports_for(reports, page="home", slot="top"))
    if "reports" not in ctx:
        ctx["reports"] = reports_to_cards(reports_for(reports, page="home", slot="main"))

    template = env.get_template("home.html.j2")
    html = render_page(template, ctx)
    out_path = site_data.SITE_DIR / "home.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return [out_path]


def build_energy_flow(env: Environment, only: str | None = None) -> list[Path]:
    """Render the LIVE electrical-demand Sankey from site/data/energy_flow.yaml.

    Every flow is driven by live Optergy meter demand. A flow's value is the
    SUM of its `meters` (METER_REGISTRY ids); aggregate flows are built as the
    union of their children's meters so the diagram conserves. The build:

      • derives each Floor→end-use meter set from the registry by
        (floor, function);
      • rolls those up into Tenants→Floor, Electricity→Tenants, and the
        landlord_flows up into Electricity→Landlord (all unions);
      • emits `sankey_data.links` each carrying `meters: [...]`, and
        `live_meters` — the de-duplicated meter list the template renders as
        one hidden data-meter-id element apiece. energy-sankey.js polls each
        unique meter once and sums it into every flow that references it."""
    if only and only != "energy_flow":
        return []
    data_file = data_path("energy_flow.yaml")
    if not data_file.exists():
        print(f"  (skip energy_flow: {data_file} not found)")
        return []

    ctx = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}
    ctx.setdefault("page_title", "Live Electrical Demand - Energy Flow")
    ctx.setdefault("container_class", "floor-container")
    ctx.setdefault("unit", "kW")
    meter_field = ctx.get("meter_field", "demand")

    meters = read_meters()

    def floor_use_meters(floor_key: str, function: str) -> list[int]:
        """Registry ids for a floor's electricity meters of a given function."""
        return sorted(
            m["id"] for m in meters
            if floor_key in m["floors"] and m["function"] == function
            and base_utility(m["utility"]) == "electricity"
        )

    links: list[dict] = []

    # ── Tenant side: floors → end uses, rolled up into Tenants → Electricity ──
    all_tenant_meters: list[int] = []
    # `floors:` entries are {key, node}: the level key and the name of the
    # diagram node its flows hang off (one of `nodes:`).
    for fl in ctx.get("floors") or []:
        floor_key, node = str(fl["key"]), fl["node"]
        floor_meters: list[int] = []
        for eu in ctx.get("floor_end_uses") or []:
            use_meters = floor_use_meters(floor_key, eu["function"])
            if not use_meters:
                continue
            links.append({"source": node, "target": eu["target"],
                          "value": eu.get("value", 0), "meters": use_meters})
            floor_meters += use_meters
        if floor_meters:
            links.append({"source": "Tenants", "target": node,
                          "value": sum(eu.get("value", 0) for eu in ctx["floor_end_uses"]),
                          "meters": sorted(floor_meters)})
            all_tenant_meters += floor_meters
    if all_tenant_meters:
        links.append({"source": "Electricity", "target": "Tenants",
                      "value": 0, "meters": sorted(set(all_tenant_meters))})

    # ── Landlord electrical: plant flows, rolled up into Electricity → Landlord ──
    all_landlord_meters: list[int] = []
    landlord_elec_total = 0
    for lf in ctx.get("landlord_flows") or []:
        lm = list(lf.get("meters") or [])
        links.append({"source": "Landlord", "target": lf["target"],
                      "value": lf.get("value", 0), "meters": sorted(lm)})
        all_landlord_meters += lm
        landlord_elec_total += lf.get("value", 0)
    if all_landlord_meters:
        # Explicit value (NOT 0): Landlord has two parents now (Electricity +
        # Gas), so the generic "sum all children" fill would over-count it.
        links.append({"source": "Electricity", "target": "Landlord",
                      "value": landlord_elec_total, "meters": sorted(set(all_landlord_meters))})

    # ── Gas / heating (LPHW): Gas → Landlord → Boilers → heat loads ──
    # Gas is a landlord utility, so it feeds the Landlord node (alongside
    # electricity); the landlord runs the boilers, which produce LPHW heat for
    # the loads in heat_flows. Gas→Landlord and Landlord→Boilers both carry the
    # gas reading (gas passes through to the boilers); the Boilers→loads gap vs
    # that input is the boiler conversion loss (a correct node imbalance).
    #
    # The gas source can be EITHER a registry meter (`gas.meter_id`, resolved by
    # meter-templates.js) OR a raw/calculated BACnet point (`gas.bacnet` +
    # `gas.format`), bound directly by live-points.js. Raw points use a string
    # token ("gas") in the flow's meter list; registry meters use their id.
    meter_fields: dict[int, str] = {}
    live_points: list[dict] = []
    gas = ctx.get("gas") or {}
    heat_flows = ctx.get("heat_flows") or []
    if heat_flows and (gas.get("bacnet") or gas.get("meter_id") is not None):
        if gas.get("bacnet"):
            gas_token = "gas"
            live_points.append({
                "key": gas_token,
                "bacnet": gas["bacnet"],
                "format": gas.get("format", "power"),
                "refresh": gas.get("refresh", ctx.get("refresh", 10)),
            })
        else:
            gas_token = gas["meter_id"]
            meter_fields[gas_token] = gas.get("meter_field", meter_field)
        heat_total = sum(hf.get("value", 0) for hf in heat_flows)
        for hf in heat_flows:
            links.append({"source": "Boilers", "target": hf["target"],
                          "value": hf.get("value", 0), "meters": sorted(hf.get("meters") or [])})
        # Gas → Landlord → Boilers (both carry the single gas reading).
        links.append({"source": "Landlord", "target": "Boilers", "value": heat_total, "meters": [gas_token]})
        links.append({"source": "Gas", "target": "Landlord", "value": heat_total, "meters": [gas_token]})

    # Aggregate-flow initial widths: sum of children's initial values.
    for l in links:
        if l["value"] == 0:
            l["value"] = sum(
                c["value"] for c in links
                if c["source"] == l["target"]
            ) or len(l["meters"])

    # De-duplicate registry meters (integer tokens only) → one hidden live
    # element apiece (gas keeps its own field; others use page-wide meter_field).
    # String tokens (raw BACnet points) are emitted via live_points instead.
    unique_ids = sorted({mid for l in links for mid in l["meters"] if isinstance(mid, int)})
    ctx["live_meters"] = [
        {"meter_id": mid, "meter_field": meter_fields.get(mid, meter_field),
         "refresh": ctx.get("refresh", 10)}
        for mid in unique_ids
    ]
    ctx["live_points"] = live_points

    ctx["sankey_data"] = {
        "nodes": ctx.get("nodes") or [],
        "links": links,
        "unit": ctx["unit"],
    }

    template = env.get_template("energy_flow.html.j2")
    html = render_page(template, ctx)
    out_path = site_data.SITE_DIR / "energy_flow.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return [out_path]


def build_dials(env: Environment, only: str | None = None) -> list[Path]:
    """Render the live KPI dials page from site/data/dials.yaml (singleton).

    Each `dials` entry is a segmented gauge bound to a live BACnet point,
    rendered by the live_dial macro + js/project/2.0/energy-dials.js."""
    if only and only != "dials":
        return []
    data_file = data_path("dials.yaml")
    if not data_file.exists():
        print(f"  (skip dials: {data_file} not found)")
        return []

    ctx = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}
    ctx.setdefault("page_title", "Live KPI Dials")
    ctx.setdefault("heading", "Live KPI Dials")
    ctx.setdefault("container_class", "floor-container")

    template = env.get_template("dials.html.j2")
    html = render_page(template, ctx)
    out_path = site_data.SITE_DIR / "dials.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return [out_path]


def build_pages(env: Environment, only: str | None = None) -> list[Path]:
    """Render the site's own pages (site/data/pages.yaml) through the base shell.

    These are pages not driven by a data registry (landlord services,
    documents, a report viewer, …): a menu's `page:` entries no module
    builds, or an older site's frozen `pages:` list. A menu page with a
    site/templates/<key>.html.j2 renders from it; otherwise the body and any
    head/script extras are raw HTML fragments in site/pages/<key>.{body,
    styles,extra_scripts,tail_scripts}.html, and a page without them is the
    shell alone (header, menu, scripts). pages.yaml carries only per-page
    metadata.
    """
    pages_file = data_path("pages.yaml")
    if not pages_file.exists():
        print(f"  (skip pages: {pages_file} not found)")
        return []

    menu = read_menu()
    pages_dir = site_data.SITE_ROOT / "pages"
    shell = env.get_template("page.html.j2")
    written: list[Path] = []
    for page in own_pages():
        key = page["key"]
        if only and only != key:
            continue
        # A menu's own page renders through its own site template if it has
        # one; anything else through the shell, its body from fragments (an
        # empty page without them).
        template = (env.get_template(f"{key}.html.j2")
                    if menu and (site_data.SITE_ROOT / "templates" / f"{key}.html.j2").exists() else shell)
        ctx = dict(page)
        if menu:
            ems = read_building().get("ems_name")
            ctx.setdefault("page_title", f"{ctx['heading']} · {ems}" if ems else ctx["heading"])
        # `building` places the page (and would shadow the `building` global).
        out_dir, location_ctx = page_location(check_building(ctx.pop("building", None), f"pages.yaml '{key}'"))
        for k, v in location_ctx.items():
            ctx.setdefault(k, v)
        path_prefix = location_ctx.get("path_prefix", "")

        def frag(suffix: str, _key: str = key) -> str:
            path = pages_dir / f"{_key}.{suffix}.html"
            if not path.exists():
                return ""
            # Rendered through the shared env so fragments can reference
            # {{ building.* }} (e.g. the homepage welcome banner) instead of
            # hardcoding site facts — and {{ path_prefix }} ("" at the site
            # root, "../" in a campus building's folder) for asset/page URLs.
            return env.from_string(path.read_text(encoding="utf-8")).render(path_prefix=path_prefix)

        ctx["body"] = frag("body")
        ctx["extra_styles_html"] = frag("styles")
        ctx["extra_scripts_html"] = frag("extra_scripts")
        ctx["tail_scripts_html"] = frag("tail_scripts")
        # heading/page_title in pages.yaml may themselves reference
        # {{ building.* }} (kept as data so a rename only touches site.yaml).
        for meta_key in ("heading", "page_title"):
            if isinstance(ctx.get(meta_key), str):
                ctx[meta_key] = env.from_string(ctx[meta_key]).render()

        out_path = out_dir / page["out"]
        out_path.write_text(render_page(template, ctx), encoding="utf-8", newline="\n")
        print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
        written.append(out_path)
    return written


def build_building_performance(env: Environment, only: str | None = None) -> list[Path]:
    """Render building_performance.htm — NABERS base-building page.

    Fully data-driven: building facts from site.yaml (via the `building`
    global), live values via named POINTS (data-point in the template), and the
    report cards from reports.yaml placements (page=building_performance, slots
    pie/right)."""
    if only and only != "building_performance":
        return []

    reports = read_reports()
    building = env.globals.get("building", {})
    ctx = {
        "page_title": f"Base Building Performance · {building.get('ems_name', 'EMS')}",
        "heading": "Base Building Performance",
        "pie_reports": reports_to_cards(
            reports_for(reports, page="building_performance", slot="pie")
        ),
        "right_reports": reports_to_cards(
            reports_for(reports, page="building_performance", slot="right")
        ),
    }

    template = env.get_template("building_performance.html.j2")
    out_path = site_data.SITE_DIR / "building_performance.htm"
    out_path.write_text(render_page(template, ctx), encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(site_data.SITE_DIR)}")
    return [out_path]


def _building_page_files(building: str) -> set[str]:
    """The filenames the build writes into a campus building's folder (its
    floor, incomer, switchboard and pages.yaml pages, and its sidebar)."""
    files = {f"{lv['page_key']}.htm" for lv in read_levels() if lv["page"] and lv["building"] == building}
    files |= {f"{key}.htm" for key, e in (read_incomers() or {}).items()
              if (e or {}).get("building") == building}
    files |= {f"{key}.htm" for key, b in ((_read_yaml(data_path("switchboards.yaml")) or {}).get("boards") or {}).items()
              if (b or {}).get("building") == building}
    files |= {pg["out"] for pg in own_pages() if pg.get("building") == building}
    return files | {"sidebar-template.js"}


def _floor_group_keys(items: list[dict]):
    """The from/to keys of every `groups:` entry under an `auto: floors`
    sidebar item, at any depth."""
    for item in items:
        if item.get("auto") == "floors":
            for g in item.get("groups") or []:
                yield g.get("from")
                yield g.get("to")
        yield from _floor_group_keys(item.get("children") or [])


def _check_cores(levels: list[dict], tenants: list[dict], meters: list[dict],
                 problems: list[str], warnings: list[str]) -> None:
    """floors.yaml `cores:` against the tenant catalog and the meters'
    tenant tags. Skipped for a site that assigns no cores."""
    if not any(lv["cores"] for lv in levels):
        return
    owner = {name: t for t in tenants for name in t["short_names"]}
    cores: dict[str, dict[str, dict]] = {}   # level key → {core: tenant}
    for lv in levels:
        cores[lv["key"]] = {}
        for core, short in lv["cores"].items():
            if short in owner:
                cores[lv["key"]][core] = owner[short]
            else:
                problems.append(f"floors.yaml '{lv['page_key']}': core '{core}' is '{short}', which isn't in "
                                f"`{TENANTS_KEY}:` (short names: {', '.join(owner) or 'none'})")

    # A meter tagged to a tenant belongs in a core that tenant holds: the
    # core its zone names, or, for a meter outside the cores (a floor total),
    # any core on its floor. Tags that aren't a catalog tenant (landlord
    # areas) are left alone, as the tenant pages leave them.
    stray: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    source = meters_file().name
    for m in meters:
        for floor in m["floors"]:
            held = cores.get(floor, {})
            for name in m["tenants"]:
                if name not in owner:
                    continue
                slug = owner[name]["slug"]
                if m["zone"] in held:
                    if held[m["zone"]]["slug"] != slug:
                        stray[(floor, name, m["zone"])].append(m["id"])
                elif slug not in {t["slug"] for t in held.values()}:
                    stray[(floor, name, "")].append(m["id"])
    for (floor, name, core), ids in stray.items():
        listed = f"{ids[:8]}{' …' if len(ids) > 8 else ''}"
        if core:
            holder = cores[floor][core]["short_names"][0]
            warnings.append(f"{source}: meter(s) {listed} on '{floor}' are tagged '{name}' but sit in "
                            f"core '{core}', which floors.yaml gives to '{holder}'")
        else:
            warnings.append(f"{source}: meter(s) {listed} tag '{name}' on '{floor}', but floors.yaml "
                            "gives them no core there")

    holders = {t["slug"] for held in cores.values() for t in held.values()}
    for tenant in tenants:
        if tenant["slug"] not in holders:
            warnings.append(f"{tenant['where']}: holds no core on any floor (floors.yaml `cores:`)")


def validate(modules: list[str] | None = None) -> int:
    """Cross-check the input data and report problems. Returns count of errors.

    Catches the failures that turn "data in → displays out" from a promise into
    a guarantee: dangling report image-refs, unknown named points, meter/point
    ids referenced by a page that don't exist, and floors that can't render.
    Once the data checks pass, builds `modules` (default: site.yaml's) into a
    throwaway output root and checks what that renders (check_build).
    """
    problems: list[str] = []

    meters = read_meters()
    meter_ids = {m["id"] for m in meters}
    points = read_points()
    report_urls = read_report_urls()
    reports = read_reports()

    # 1. Every report placement's image_ref must have a URL in reports.yaml `urls:`.
    for r in reports:
        ref = r.get("image_ref")
        if ref and ref not in report_urls:
            problems.append(f"reports.yaml placements: image_ref '{ref}' has no entry in `urls:`")

    # 2. POINTS must each carry a bacnet address.
    for name, pt in points.items():
        if not pt.get("bacnet"):
            problems.append(f"POINTS: '{name}' has no bacnet address")

    # 3. data-point / data-meter-id on the pages the site renders must
    # resolve — checked on the built output (check_build), so an engine
    # template the site overrides or never renders isn't held to its data.

    # Site overrides silently replace engine templates of the same name
    # (make_env's loader order) — list them so that's never a surprise.
    site_templates = site_data.SITE_ROOT / "templates"
    overrides = sorted(
        p.relative_to(site_templates).as_posix()
        for p in site_templates.rglob("*.j2")
        if (TEMPLATES_DIR / p.relative_to(site_templates)).exists()
    )
    if overrides:
        print(f"Site template overrides (replace the engine's copy): {', '.join(overrides)}")
    site_components = sorted(c for c in read_component_catalog() if (COMPONENTS_DIR / c).is_dir()
                             and (site_data.SITE_ROOT / "components" / c).is_dir())
    if site_components:
        print(f"Site components replacing the engine's: {', '.join(site_components)}")

    # 4. Every level with a page must be renderable (registry meters or layout).
    levels = read_levels()
    level_keys = {lv["key"] for lv in levels}
    for lv in levels:
        if not lv["page"]:
            continue
        has_meters = any(lv["key"] in m["floors"] for m in meters)
        has_layout = bool((lv["data"].get("floorplan_tab") or {}).get("layout"))
        if not has_meters and not has_layout:
            problems.append(f"floors.yaml: '{lv['page_key']}' has no registry meters and no explicit layout")

    # 5. Every floor named anywhere must be a level in floors.yaml — a typo
    # would otherwise silently drop a meter, binding or report from its page,
    # and a floor with no level has no position to sort by. A level needn't
    # have a page (`page: false` — plant basements, a roof).
    def unknown_floors(source: str, names) -> None:
        for name in sorted({str(n) for n in names} - level_keys):
            problems.append(f"{source}: floor '{name}' isn't a level in floors.yaml (typo? or add it, "
                            "page: false if it has no page)")

    for floor in sorted({f for m in meters for f in m["floors"]} - level_keys):
        ids = [m["id"] for m in meters if floor in m["floors"]]
        problems.append(f"{meters_file().name}: floor '{floor}' (meter ids {ids[:8]}{' …' if len(ids) > 8 else ''}) "
                        "isn't a level in floors.yaml (typo? or add it, page: false if it has no page)")
    unknown_floors(point_source("floors"), (f for _role, f in read_bms_bindings()))
    unknown_floors("reports.yaml placements", (r["floor"] for r in reports if "floor" in r))
    tenants = read_tenants()
    for tenant in tenants:
        t = tenant["data"]
        unknown_floors(tenant["where"],
                       [*(t.get("extra_floors") or []), *(t.get("exclude_floors") or []), *(t.get("floors") or {})])
    unknown_floors("energy_flow.yaml floors", (fl["key"] for fl in (_read_yaml(data_path("energy_flow.yaml")) or {}).get("floors") or []))
    sidebar = sidebar_cfg() or {}
    for items in [sidebar.get("top_items"), sidebar.get("bottom_items"),
                  *(sec.get("items") for sec in sidebar.get("sections") or [])]:
        unknown_floors("sidebar floor groups", _floor_group_keys(items or []))

    # 6. Every meter's utility must be in the site's catalog — otherwise it
    # gets no zone subtitle and no styling (an unmatched cell is passed
    # through as-is by meters.csv normalisation, so it shows up here).
    for code in sorted({base_utility(m["utility"]) for m in meters if m["utility"]} - site_data.UTILITIES.keys()):
        ids = [m["id"] for m in meters if base_utility(m["utility"]) == code]
        problems.append(f"{meters_file().name}: utility '{code}' (meter ids {ids[:8]}{' …' if len(ids) > 8 else ''}) "
                        f"isn't in site.yaml `utilities:` (known: {', '.join(site_data.UTILITIES)})")

    # 8. Every `building:` an incomer, page or switchboard names must be a
    # site.yaml building (levels are checked as floors.yaml is read).
    placed = [(point_source("incomers"), key, entry) for key, entry in (read_incomers() or {}).items()]
    placed += [("pages.yaml", pg.get("key"), pg) for pg in own_pages()]
    placed += [("switchboards.yaml", key, board)
               for key, board in ((_read_yaml(data_path("switchboards.yaml")) or {}).get("boards") or {}).items()]
    for source, key, entry in placed:
        try:
            check_building((entry or {}).get("building"), f"{source} '{key}'")
        except SystemExit as e:
            problems.append(str(e))

    # Warnings — data that's harmless but does nothing (not counted as errors).
    warnings: list[str] = []

    # A report card a page names (data-report) is built from one set of
    # fields; a second, different set for the same name is ignored.
    warnings.extend(report_cards()[1])

    # A file in data/ the build doesn't know — a misspelt name (numbered or
    # not) would otherwise be silently ignored.
    known = set(DATA_FILES) | set(LEGACY_DATA_FILES)
    for path in sorted(p for p in site_data.DATA_DIR.iterdir() if p.is_file()):
        if re.sub(r"^\d+_", "", path.name) not in known:
            warnings.append(f"{_rel(path)}: the build doesn't read this file (data files: {', '.join(DATA_FILES)})")

    # 9. Every extras.yaml placement must name a known component, page and
    # slot, and give the component's required options (and no unknown ones).
    placements = components.resolve(read_extras(), read_component_catalog(), extras_pages(), problems, warnings)
    # A frozen page in a campus building's folder must write its relative
    # URLs as {{ path_prefix }}… — a bare "img/x.png" or "home.htm" would
    # resolve inside the folder and 404. A bare link to another page of the
    # same building (same folder) is fine.
    bare_url = re.compile(r'(?:src|href)="(?!\{\{|/|#|\.\./|[a-z]+:)([^"?#]+)')
    for pg in own_pages():
        if page_folder(pg.get("building")):
            neighbours = _building_page_files(pg["building"])
            for frag in sorted((site_data.SITE_ROOT / "pages").glob(f"{pg['key']}.*.html")):
                for url in sorted(set(bare_url.findall(frag.read_text(encoding="utf-8"))) - neighbours):
                    warnings.append(f"{_rel(frag)}: '{url}' resolves inside the {pg['building']}/ folder — "
                                    "write it as {{ path_prefix }}" + url)
    # Each utility's meters are styled by a .meter-<code> CSS rule.
    css = "".join(p.read_text(encoding="utf-8", errors="replace")
                  for root in (ASSETS_DIR / "css", site_data.SITE_ROOT / "assets" / "css") if root.exists()
                  for p in root.rglob("*.css"))
    if ".meter-" in css:
        for code in site_data.UTILITIES:
            if f".meter-{code}" not in css:
                warnings.append(f"site.yaml utility '{code}' has no .meter-{code} CSS rule — its meters will be unstyled")
    else:
        print("  (no project CSS with .meter-* rules found — skipping the utility CSS check)")
    # 7. Bindings for a role no page shows (e.g. the floor_demand_* rows,
    # left over from a Summary-tab card set the floor template never rendered).
    shown = {role for tab in site_data.FLOOR_PAGE["tabs"] for role in tab["roles"]}
    unused: dict[str, int] = defaultdict(int)
    for role, _floor in read_bms_bindings():
        if role not in shown:
            unused[role] += 1
    for role, n in sorted(unused.items()):
        warnings.append(f"{point_source('floors')}: role '{role}' (on {n} level(s)) isn't shown on any page")
    # A floor page whose cards use more columns than its riser grid has
    # (meter_columns): the extra columns wrap onto a new row.
    for lv in levels:
        columns = level_layout(lv)["meter_columns"]
        grid = MAX_METER_COLUMNS if columns == "auto" else columns
        used = {m["column"] for m in meters
                if lv["key"] in m["floors"] and m["main_display"] and m["column"] is not None}
        if lv["page"] and len(used) > grid:
            warnings.append(f"floors.yaml: '{lv['page_key']}' has cards in {len(used)} columns "
                            f"({meters_file().name} `column`) but its grid has {grid} "
                            f"(meter_columns: {columns}): the rest wrap onto a new row")
    _check_cores(levels, tenants, meters, problems, warnings)

    if problems:
        warnings.append("skipped the build checks (rendered data-point/meter ids, missing assets and links) "
                        "until the problems below are fixed")
    else:
        check_build(resolve_modules(None) if modules is None else modules,
                    set(points), meter_ids, problems, warnings, placements, report_urls)

    for w in warnings:
        print(f"  [!] {w}")
    if problems:
        print(f"VALIDATION FAILED - {len(problems)} problem(s):")
        for p in problems:
            print(f"  [X] {p}")
    else:
        print("Validation passed: the site data cross-references resolve and the site builds"
              + (f" ({len(warnings)} warning(s))." if warnings else "."))
    return len(problems)


def check_build(modules: list[str], points: set[str], meter_ids: set[int],
                problems: list[str], warnings: list[str], placements: list[dict] = (),
                report_urls: set[str] = frozenset()) -> None:
    """Build the site into a throwaway output root and check what it
    renders (linkcheck.py): a data-point, meter id or data-report naming
    nothing is a problem; a file a page references that the build doesn't produce (an
    asset not yet in _assets/ or site/assets/, a page no module writes,
    another site's /docs/ URL) is a warning, and so are a page whose markup
    needs a runtime script it doesn't load (data-meter-id without
    meter-templates.js, …) and an extras placement no built page rendered.
    The real output root is never touched."""
    out_root = site_data.OUT_ROOT
    with tempfile.TemporaryDirectory(prefix="build-check-") as tmp:
        try:
            configure(site_data.SITE_ROOT, Path(tmp) / "project")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build_site(modules)
            except SystemExit as e:
                problems.append(f"the build fails: {e}")
                return
            except Exception as e:
                problems.append(f"the build fails: {type(e).__name__}: {e}")
                return
            problems.extend(linkcheck.unknown_names(site_data.OUT_ROOT, site_data.SITE_DIR, points, meter_ids, report_urls))
            warnings.extend(linkcheck.missing_references(site_data.OUT_ROOT, site_data.SITE_DIR))
            warnings.extend(linkcheck.unloaded_scripts(site_data.OUT_ROOT, site_data.SITE_DIR))
            pages = extras_pages()
            for p in placements:
                keys = sorted({k for k, kind in pages.items() if k in p["pages"] or kind in p["pages"]})
                unseen = [k for k in keys if (k, p["slot"]) not in RENDERED_SLOTS]
                if unseen:
                    warnings.append(
                        f"extras.yaml placement {p['number']} ({p['component']}) doesn't appear on "
                        f"{', '.join(unseen[:4])}{' …' if len(unseen) > 4 else ''} — its module is off, or the "
                        "page uses a site template override without that slot")
        finally:
            configure(site_data.SITE_ROOT, out_root)


# ─── Modules ─────────────────────────────────────────────────────────────────
# Every page family the engine can build, in build order. A site's pages.yaml
# menu decides which run (an older site lists them in site.yaml `modules:`);
# --modules overrides that for one run.
# Each builder takes (env, only) and returns the paths it wrote. sidebar runs
# last; it only rewrites the staged sidebar-template.js. The switchboards and
# risers modules live in their own files and read the site from site_data.
MODULES = {
    "floors":               build_floors,
    "incomers":             build_incomers,
    "home":                 build_home,
    "meters_hierarchy":     build_meters_hierarchy,
    "schematics":           build_schematics,
    "building_performance": build_building_performance,
    "pages":                build_pages,
    "tenants":              build_tenants,
    "energy_flow":          build_energy_flow,
    "dials":                build_dials,
    "switchboards":         build_switchboards.run,
    "risers":               build_risers.run,
    "sidebar":              build_sidebar,
}


def resolve_modules(spec: str | None) -> list[str]:
    """The modules to run, in MODULES order: from --modules ("all", or a
    comma-separated list) if given, else the menu in pages.yaml, else
    site.yaml `modules:`."""
    if spec is None and (menu := read_menu()):
        return menu["modules"]
    if spec is None:
        source = f"{_rel(site_data.BUILDING_FILE)} `modules:`"
        names = read_building().get("modules")
        if not names:
            raise SystemExit(f"{_rel(site_data.BUILDING_FILE)}: `modules:` is required — the page families to build, "
                             f"from: {', '.join(MODULES)}")
    else:
        source = "--modules"
        names = list(MODULES) if spec == "all" else [n.strip() for n in spec.split(",") if n.strip()]
    unknown = [n for n in names if n not in MODULES]
    if unknown:
        raise SystemExit(f"{source}: unknown module(s) {unknown} — available: {', '.join(MODULES)}")
    return [name for name in MODULES if name in names]


def build_site(modules: list[str], only: str | None = None) -> dict[Path, str]:
    """Build the configure()d site into its output root: stage it, write the
    generated JS blocks, run `modules` in order. Returns {path: module} for
    every file the modules wrote."""
    # A single-page rebuild (`only`) reuses an already-staged output root;
    # a full build — or a first build — always restages from scratch.
    if not only or not (site_data.OUT_ROOT / OUTPUT_MARKER).exists():
        stage_output()
    write_js_blocks()

    env = make_env()
    print(f"Building modules: {', '.join(modules)}")
    # Two modules writing the same file means one silently replaces the
    # other's page (e.g. the switchboards module vs a frozen swb_lv01.htm
    # in pages.yaml) — refuse rather than guess which one the site meant.
    written_by: dict[Path, str] = {}
    for name in modules:
        for path in MODULES[name](env, only=only):
            if path in written_by:
                raise SystemExit(
                    f"modules {written_by[path]!r} and {name!r} both write {_rel(path)} — "
                    "drop one of them from pages.yaml (or site.yaml `modules:`), or the duplicate page"
                )
            written_by[path] = name
    return written_by


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "only",
        nargs="?",
        default=None,
        help="Optional page key (e.g. floor_ground, incomer_gas). Builds everything if omitted.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the site data, then build it into a temporary directory and check the "
             "pages' points, meter ids, assets and links. Writes nothing to --out.",
    )
    parser.add_argument(
        "--site",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help="Site directory to build (default: site/).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help="Output root; the site lands in <out>/<slug>/ (default: project/).",
    )
    parser.add_argument(
        "--modules",
        default=None,
        help=f"Comma-separated modules to build instead of those pages.yaml (or site.yaml `modules:`) names, or 'all'. "
             f"Available: {', '.join(MODULES)}.",
    )
    args = parser.parse_args(argv)

    configure(args.site, args.out)
    modules = resolve_modules(args.modules)
    if args.check:
        # Builds into a throwaway directory only — never touches the output root.
        return 1 if validate(modules) else 0

    written_by = build_site(modules, args.only)
    print(f"Done. {len(written_by)} file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
