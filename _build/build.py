#!/usr/bin/env python
"""
Generate static .htm pages from _data/*.yaml + _templates/*.j2.

Usage:
    python _build/build.py                 # build every page
    python _build/build.py floor_ground    # build a single floor by key

Floor layout is derived from _data/meters.csv (via generate_meter_registry.py
→ METER_REGISTRY): meters carrying
floor / column / zone / position / function / utility fields are grouped
into floor-cards by zone, ordered by position within each column. Per-floor
YAML in _data/floors.yaml supplies only the bits that aren't in the meter
registry — summary cards with BMS aggregate BACnets, report library item
IDs, and any non-conventional heading / tabs / floorplan image overrides.

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
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import ChainableUndefined, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "_templates"
DATA_DIR = ROOT / "_data"
BUILDING_FILE = DATA_DIR / "building.yaml"

# The output directory name — project/<slug>/ — comes from _data/building.yaml
# (the site's single source of identity, see that file's own header comment).
# Porting this build system to a new site: rename project/<old-slug>/ to
# project/<new-slug>/ and set building.yaml's slug to match — nothing else
# in this file needs to change.
_SITE_SLUG = "st-peters"
if BUILDING_FILE.exists():
    _building_raw = yaml.safe_load(BUILDING_FILE.read_text(encoding="utf-8")) or {}
    _SITE_SLUG = _building_raw.get("slug", _SITE_SLUG)

SITE_DIR = ROOT / "project" / _SITE_SLUG
# Tenant pages live directly under project/tenants/ — a sibling of SITE_DIR,
# not nested inside it (see build_tenants()/TENANT_PATH_PREFIX below).
TENANTS_DIR = ROOT / "project" / "tenants"
METERS_JS = SITE_DIR / "js" / "project" / "2.0" / "meter-templates.js"
REPORTS_JS = SITE_DIR / "js" / "project" / "2.0" / "reports.js"
REGISTRY_BEGIN = "// ── BEGIN GENERATED METER_REGISTRY ── DO NOT EDIT BY HAND ──"
REGISTRY_END = "// ── END GENERATED METER_REGISTRY ──"
BMS_BEGIN = "// ── BEGIN GENERATED BMS_BINDINGS ── DO NOT EDIT BY HAND ──"
BMS_END = "// ── END GENERATED BMS_BINDINGS ──"
REPORTS_BEGIN = "// ── BEGIN GENERATED REPORT_REGISTRY ── EDIT BY HAND ──"
REPORTS_END = "// ── END GENERATED REPORT_REGISTRY ──"
POINTS_BEGIN = "// ── BEGIN POINTS ──"
POINTS_END = "// ── END POINTS ──"


# ─── Conventions for floor pages ─────────────────────────────────────────────
# Floor key → human heading. Override by setting `heading:` in YAML.
HEADING_OVERRIDES: dict[str, str] = {}
# Utilities considered "heat" for tab/location derivation
HEAT_UTILITIES = {"chw", "lphw", "lthw"}

# A meter's `utility` may carry a "-virtual" suffix ("lthw-virtual" in the
# CSV) marking it as calculated rather than physical. That suffix exists only
# to pick the meter-<utility>-virtual CSS class, so every comparison asking
# *which* utility a meter carries has to strip it first — a virtual LTHW
# meter is still LTHW, and still heat.
VIRTUAL_UTILITY_SUFFIX = "-virtual"


def base_utility(utility: str) -> str:
    """The utility code without its virtual marker: "lthw-virtual" -> "lthw"."""
    return utility.removesuffix(VIRTUAL_UTILITY_SUFFIX)


# ─── Summary-card role catalog ───────────────────────────────────────────────
# Each role names a summary-card slot that appears on floor pages. The
# (role, floor) pair indexes into BMS_BINDINGS (in meter-templates.js) to
# resolve the BACnet point. Title and format live here so each role has one
# canonical label across all floors.
SUMMARY_CARD_ROLES: dict[str, dict[str, str]] = {
    "floor_demand_electricity":         {"title": "Electricity Demand",       "format": "power"},
    "floor_demand_heat_apportioned":    {"title": "Heating Demand",           "format": "power"},
    "floor_demand_cool":                {"title": "Cooling Demand",           "format": "power"},
    "floor_demand_ventilation":         {"title": "Ventilation Demand",       "format": "power"},
    "floor_today_electricity":          {"title": "Today Electricity Consumption",   "format": "energy"},
    "floor_monthly_electricity":        {"title": "Monthly Electricity Consumption", "format": "energy"},
    "floor_monthly_change_electricity": {"title": "vs Last Month",            "format": "percentage_signed"},
    "floor_monthly_heat_apportioned":   {"title": "Monthly Heat Energy",      "format": "energy"},
    "floor_monthly_change_heat":        {"title": "vs Last Month",            "format": "percentage_signed"},
    "floor_monthly_cool_apportioned":   {"title": "Monthly Cooling Energy",   "format": "energy"},
    "floor_monthly_change_cool":        {"title": "vs Last Month",            "format": "percentage_signed"},
    "floor_peak_cool_demand":           {"title": "Peak Cooling Demand",      "format": "power"},
    "floor_ventilation_status":         {"title": "Ventilation AHU Status",   "format": "status"},
    "floor_supply_air_temp":            {"title": "Supply Air Temp",          "format": "temperature"},
    "floor_extract_air_temp":           {"title": "Extract Air Temp",         "format": "temperature"},
}

FLOORPLAN_TAB_ROLES = (
    "floor_demand_electricity",
    "floor_demand_heat_apportioned",
    "floor_demand_cool",
    "floor_demand_ventilation",
)
ELECTRICITY_TAB_ROLES = (
    "floor_today_electricity",
    "floor_monthly_electricity",
    "floor_monthly_change_electricity",
)
HEAT_TAB_ROLES = (
    "floor_monthly_heat_apportioned",
    "floor_monthly_change_heat",
    "floor_monthly_cool_apportioned",
)
COOLING_TAB_ROLES = (
    "floor_monthly_cool_apportioned",
    "floor_monthly_change_cool",
    "floor_peak_cool_demand",
)
VENTILATION_TAB_ROLES = (
    "floor_ventilation_status",
    "floor_supply_air_temp",
    "floor_extract_air_temp",
)


def floor_key_from_page_key(page_key: str) -> str:
    """floor_ground → ground, floor_1st → 1st."""
    return page_key.removeprefix("floor_")


def default_heading(floor_key: str) -> str:
    override = HEADING_OVERRIDES.get(floor_key)
    pretty = override if override else floor_key.capitalize()
    return f"{pretty} Floor Overview"


def default_floorplan_image(floor_key: str) -> str:
    # Each floor has its own floorplan image, named img/floors/floor_<floor_key>.png
    # (e.g. img/floors/floor_3rd.png, img/floors/floor_ground.png) — override by setting
    # `floorplan_image:` in YAML.
    return f"img/floors/floor_{floor_key}.png"


# ─── Meter registry ──────────────────────────────────────────────────────────
# The committed source of truth is the METER_REGISTRY block inside
# js/project/2.0/meter-templates.js. meter_tmp.csv is a scratch editing
# format (gitignored). Build reads JS directly so a fresh checkout works
# without first regenerating the CSV.

_FIELD_RE = re.compile(
    r'(\w+)\s*:\s*'
    r'(?:"((?:[^"\\]|\\.)*)"'  # double-quoted string  → group 2
    r'|(-?\d+)'                # bare integer          → group 3
    r'|(true|false))'          # bare boolean          → group 4
)


def _parse_entry(body: str) -> dict:
    """Parse the contents of a single { id: …, tag: "…", … } entry."""
    out: dict = {}
    for m in _FIELD_RE.finditer(body):
        key, str_val, int_val, bool_val = m.group(1), m.group(2), m.group(3), m.group(4)
        if int_val is not None:
            out[key] = int(int_val)
        elif bool_val is not None:
            out[key] = bool_val == "true"
        else:
            out[key] = str_val
    return out


def read_meters() -> list[dict]:
    """Parse METER_REGISTRY from meter-templates.js into a list of dicts."""
    if not METERS_JS.exists():
        return []
    js = METERS_JS.read_text(encoding="utf-8")
    try:
        block = js.split(REGISTRY_BEGIN, 1)[1].split(REGISTRY_END, 1)[0]
    except IndexError:
        raise SystemExit(f"METER_REGISTRY markers not found in {METERS_JS}")

    out: list[dict] = []
    # Match each { … } entry on a registry line (skip the const declaration etc.)
    for entry_match in re.finditer(r"\{\s*id:[^{}]*\}", block):
        entry = _parse_entry(entry_match.group(0))
        # Normalise: pull placement fields out as flat keys with sane defaults
        out.append(
            {
                "id":        entry["id"],
                "tag":       entry.get("tag", ""),
                "base":      entry.get("base"),
                "type":      entry.get("type", ""),
                "parent_id": entry.get("parent_id"),  # None if not in hierarchy
                "floor":     entry.get("floor", ""),
                # A meter placed on more than one floor page (e.g. a riser
                # meter serving both) carries a "/"-separated floor list in
                # the CSV/registry, e.g. floor: "3rd/4th" — split into a
                # tuple so it renders on every floor it names. Single-floor
                # meters just get a 1-tuple. Column/zone/position/function/
                # utility are shared across all of them (one placement per
                # meter, not one per floor).
                "floors":    tuple(f.strip() for f in entry.get("floor", "").split("/") if f.strip()),
                "column":    entry.get("column"),     # None if not pinned
                "zone":      entry.get("zone", ""),
                "position":  entry.get("position"),   # None if not pinned
                "function":  entry.get("function", ""),
                "utility":   entry.get("utility", ""),
                # tenant is comma-separated; split into a tuple of slugs for
                # quick membership tests (`"metro" in m["tenants"]`).
                "tenants":   tuple(t.strip() for t in entry.get("tenant", "").split(",") if t.strip()),
                # Explicit opt-in gate for tenant pages (CSV "tenant_display"
                # column) — absent/false means the meter never appears on any
                # tenant page, regardless of its tenant tag.
                "tenant_display": entry.get("tenant_display", False) is True,
                # Opt-OUT gate for main (non-tenant) floor pages (CSV
                # "main_display" column) — inverse polarity from
                # tenant_display: absent/true (the default, matching every
                # meter that predates this column) means it shows on the
                # main floor page; only an explicit `main_display: false`
                # hides it there. Independent of tenant_display/tenant, so a
                # meter can be main-only, tenant-only, both, or neither.
                "main_display": entry.get("main_display", True) is not False,
            }
        )
    _check_registry_integrity(out)
    return out


def _check_registry_integrity(meters: list[dict]) -> None:
    """Fail loudly on METER_REGISTRY collisions the renderer can't safely
    disambiguate on its own.

    - Duplicate `id`: this is what BACnet address resolution and every
      data-meter-id binding key off, so two rows sharing an id make it
      ambiguous which one the client-side JS actually binds to — a silent,
      wrong-live-data bug rather than a crash.
    - Duplicate floor+column+zone+position: derive_layout() groups meters
      into grid cells by (column, zone), so an exact duplicate doesn't
      crash — both meters just render stacked in the same card — but it's
      almost always a copy-paste slip in the CSV rather than intentional,
      so it's caught here instead of relying on someone spotting a doubled
      card. Meters not pinned to the grid (column: null) are exempt, same
      as derive_layout's own on_floor filter.
    """
    problems: list[str] = []

    by_id: dict[int, list[dict]] = defaultdict(list)
    for m in meters:
        by_id[m["id"]].append(m)
    for mid, rows in sorted(by_id.items()):
        if len(rows) > 1:
            problems.append(
                f"duplicate id {mid}: {len(rows)} entries (tags: {[r['tag'] for r in rows]})"
            )

    by_slot: dict[tuple, list[dict]] = defaultdict(list)
    for m in meters:
        if m["column"] is None:
            continue
        for floor_key in m["floors"]:
            by_slot[(floor_key, m["column"], m["zone"], m["position"])].append(m)
    for (floor_key, column, zone, position), rows in sorted(by_slot.items(), key=lambda kv: kv[0][0]):
        if len(rows) > 1:
            problems.append(
                f"duplicate floor={floor_key!r} column={column} zone={zone!r} position={position}: "
                f"{len(rows)} meters (ids: {[r['id'] for r in rows]})"
            )

    if problems:
        raise SystemExit("METER_REGISTRY integrity check failed:\n" + "\n".join(f"  - {p}" for p in problems))


def read_reports() -> list[dict]:
    """Parse REPORT_REGISTRY from reports.js into a list of report rows.

    Each row mirrors what _data/*.yaml used to carry inline, plus placement
    fields (page/floor/tenant/incomer/slot/position) used to filter the
    rows for any given page.
    """
    if not REPORTS_JS.exists():
        return []
    js = REPORTS_JS.read_text(encoding="utf-8")
    try:
        block = js.split(REPORTS_BEGIN, 1)[1].split(REPORTS_END, 1)[0]
    except IndexError:
        return []
    out: list[dict] = []
    for m in re.finditer(r"\{\s*\w+:[^{}]*\}", block):
        entry = _parse_entry(m.group(0))
        if "image_ref" not in entry:
            continue  # Skip non-report braces just in case
        out.append(entry)
    return out


def reports_for(reports: list[dict], **filters) -> list[dict]:
    """Filter reports by exact-match placement fields, then sort by position.

    Example:
        reports_for(reports, page="floor", floor="ground", slot="electricity")
    """
    matched = [
        r for r in reports
        if all(r.get(k) == v for k, v in filters.items())
    ]
    matched.sort(key=lambda r: r.get("position", 0))
    return matched


def reports_to_cards(rows: list[dict]) -> list[dict]:
    """Convert REPORT_REGISTRY rows to the dict shape the report_card macro expects."""
    cards: list[dict] = []
    for r in rows:
        card: dict = {
            "image_ref": "reports." + r["image_ref"],
            "alt":       r.get("alt", "📊 Report"),
        }
        if "id" in r:
            card["library_item_id"] = r["id"]
        if "title" in r:
            card["title"] = r["title"]
        if "subtitle" in r:
            card["subtitle"] = r["subtitle"]
        if "kind" in r:
            card["kind"] = r["kind"]
        cards.append(card)
    return cards


def read_building() -> dict:
    """Load _data/building.yaml (site/building facts). Empty dict if absent."""
    if not BUILDING_FILE.exists():
        return {}
    return yaml.safe_load(BUILDING_FILE.read_text(encoding="utf-8")) or {}


def read_points() -> dict[str, dict]:
    """Parse the POINTS table from meter-templates.js → {name: {bacnet, format}}.

    Named non-meter BACnet points referenced by `data-point="<name>"`.
    """
    if not METERS_JS.exists():
        return {}
    js = METERS_JS.read_text(encoding="utf-8")
    try:
        block = js.split(POINTS_BEGIN, 1)[1].split(POINTS_END, 1)[0]
    except IndexError:
        return {}
    out: dict[str, dict] = {}
    for m in re.finditer(r"(\w+)\s*:\s*\{([^{}]*)\}", block):
        out[m.group(1)] = _parse_entry(m.group(2))
    return out


def read_report_urls() -> set[str]:
    """Parse the keys of ReportUrls.reports from reports.js (image-ref names)."""
    if not REPORTS_JS.exists():
        return set()
    js = REPORTS_JS.read_text(encoding="utf-8")
    # The reports: { … } object precedes REPORT_REGISTRY; keys look like
    #   home_elec_demand: "/images/…"
    head = js.split(REPORTS_BEGIN, 1)[0]
    return set(re.findall(r'^\s+([A-Za-z_]\w*)\s*:\s*"', head, flags=re.MULTILINE))


def read_bms_bindings() -> dict[tuple[str, str], dict]:
    """Parse BMS_BINDINGS from meter-templates.js into a {(role, floor): row} map."""
    if not METERS_JS.exists():
        return {}
    js = METERS_JS.read_text(encoding="utf-8")
    try:
        block = js.split(BMS_BEGIN, 1)[1].split(BMS_END, 1)[0]
    except IndexError:
        return {}

    out: dict[tuple[str, str], dict] = {}
    for entry_match in re.finditer(r"\{\s*role:[^{}]*\}", block):
        entry = _parse_entry(entry_match.group(0))
        key = (entry["role"], entry["floor"])
        out[key] = entry
    return out


def derive_summary_cards(
    roles: tuple[str, ...],
    floor_key: str,
    bindings: dict[tuple[str, str], dict],
    leading: list[dict] | None = None,
) -> list[dict]:
    """Compose a summary_cards list for a tab from the role catalog + bindings.

    Each role emits one card. If a (role, floor) binding exists in BMS_BINDINGS,
    the card is live (id + bacnet + format). Otherwise a static "N/A" placeholder
    is emitted so the layout stays stable across floors.
    """
    cards: list[dict] = list(leading) if leading else []
    for role in roles:
        meta = SUMMARY_CARD_ROLES[role]
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


# ─── Floor Summary section (Total Electricity / Tenants / Landlords cards) ──
# These are floor-level aggregate/calculated meters, not part of the East/
# North/West riser grid — identified in METER_REGISTRY by `function` (with
# `column: null`, so `derive_layout` above skips them) rather than by
# position. At most one meter per (floor, function) is expected; add the
# matching METER_REGISTRY row (any `type`, e.g. "Calculation") with the
# `function` value below to wire a floor's card to live data — until then
# the card renders a static "N/A" placeholder (see `floor_summary_card` in
# macros.j2).
FLOOR_SUMMARY_CARD_ROLES: dict[str, dict[str, str]] = {
    "total_card":     {"function": "Floor Total Electricity", "title": "Floor Total Electricity",
                        "wrapper_class": "floor-summary-center-block floor-card"},
    "tenants_card":   {"function": "Floor Tenants Electricity",   "title": "Floor Tenants Electricity"},
    "landlords_card": {"function": "Floor Landlords Electricity", "title": "Floor Landlords Electricity"},
}


def find_floor_summary_meter(
    meters: list[dict], floor_key: str, function: str, registry_names: list[str] | None = None
) -> dict | None:
    """The METER_REGISTRY row for (floor_key, function), or None if absent.

    Each of these three cards is single-valued per floor by design. Main-page
    lookups (registry_names=None) match against every row for (floor,
    function), same as always.

    Tenant-page lookups (registry_names given) only ever use a row with
    `tenant_display` set and tagged to this tenant (e.g. the 641+ "Aon Level
    NN Electricity" override meters) — the generic/landlord row for the same
    role (the old building-wide "Floor Total Electricity" calc meters,
    492-628) is never used as a fallback there. No matching override means
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
    for key, role in FLOOR_SUMMARY_CARD_ROLES.items():
        card = {"title": role["title"]}
        if "wrapper_class" in role:
            card["wrapper_class"] = role["wrapper_class"]
        meter = find_floor_summary_meter(meters, floor_key, role["function"], registry_names)
        if meter:
            card["meter_id"] = meter["id"]
        cards[key] = card
    return cards


def derive_zone_location(utilities: set[str]) -> str:
    """The card subtitle below the zone name."""
    has_electric = "electricity" in utilities
    has_heat = bool(utilities & HEAT_UTILITIES)
    if has_electric and has_heat:
        return "Electrical & Heat Energy"
    if has_heat:
        return "Heat Energy"
    return "Electricity"


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


# ─── Jinja env / build ───────────────────────────────────────────────────────
def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=ChainableUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    # Site/building facts available to every template as `building`.
    env.globals["building"] = read_building()
    return env


# Fixed 5-tab set every floor page carries (matches floor_23rd.htm, the
# reference layout): Summary + one report tab per utility. Unlike the old
# conditional tab list, these always render — reports/summary-cards with no
# registry data yet just render "N/A" / an unresolved image, same as any
# other not-yet-wired role.
FLOOR_TABS = [
    {"id": "floorplan",           "label": "Summary"},
    {"id": "electricity-report",  "label": "Electricity Report"},
    {"id": "heat-report",         "label": "Heating Energy Report"},
    {"id": "cooling-report",      "label": "Cooling Energy Report"},
    {"id": "ventilation-report",  "label": "Building Ventilation Report"},
]

# Every floor report tab (electricity/heat/cooling/ventilation) shows up to
# 2 reports, in REPORT_REGISTRY position order: Demand first, Consumption
# second.
REPORT_CARD_LABELS = ("Demand", "Consumption")


def build_floors(env: Environment, only: str | None = None) -> list[Path]:
    floors_file = DATA_DIR / "floors.yaml"
    if not floors_file.exists():
        print(f"  (skip floors: {floors_file} not found)")
        return []

    floors = yaml.safe_load(floors_file.read_text(encoding="utf-8")) or {}
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

    for key, raw in floors.items():
        if only and only != key:
            continue
        ctx = dict(raw or {})
        floor_key = floor_key_from_page_key(key)

        ctx.setdefault("container_class", "floor-container")
        ctx.setdefault("heading", default_heading(floor_key))
        ctx.setdefault("page_title", f"{ctx['heading']} · {ems_name}")
        ctx.setdefault("tabs", FLOOR_TABS)

        # Floorplan tab: derive layout + summary_cards unless YAML supplies them.
        fp_tab = dict(ctx.get("floorplan_tab") or {})
        if "layout" not in fp_tab:
            image = fp_tab.get("floorplan_image") or default_floorplan_image(floor_key)
            after_col = fp_tab.get("floorplan_after_column", 0)
            fp_tab.setdefault("image", image)
            fp_tab["layout"] = derive_layout(main_meters, floor_key, image, after_col)
            if not fp_tab["layout"]:
                raise SystemExit(
                    f"{key}: no meters pinned to floor={floor_key!r} in meter_tmp.csv "
                    f"and no `layout:` in YAML — cannot render."
                )
        if "summary_cards" not in fp_tab:
            fp_tab["summary_cards"] = derive_summary_cards(
                FLOORPLAN_TAB_ROLES, floor_key, bindings
            )
        for card_key, card in derive_floor_summary_cards(main_meters, floor_key).items():
            fp_tab.setdefault(card_key, card)
        ctx["floorplan_tab"] = fp_tab

        # Report tabs: derive summary_cards + reports unless YAML supplies them.
        # Always materialised (all 4 report tabs render on every floor now,
        # per FLOOR_TABS) — floors without registry data for a slot just get
        # an empty reports list and "N/A" summary cards, same as any other
        # not-yet-wired role.
        for tab_key, slot, roles in (
            ("electricity_tab", "electricity", ELECTRICITY_TAB_ROLES),
            ("heat_tab",        "heat",        HEAT_TAB_ROLES),
            ("cooling_tab",     "cooling",     COOLING_TAB_ROLES),
            ("ventilation_tab", "ventilation", VENTILATION_TAB_ROLES),
        ):
            tab = dict(ctx.get(tab_key) or {})
            if "summary_cards" not in tab:
                tab["summary_cards"] = derive_summary_cards(roles, floor_key, bindings)
            if "reports" not in tab:
                cards = reports_to_cards(reports_for(
                    reports, page="floor", floor=floor_key, slot=slot
                ))
                # Each tab shows up to 2 reports: Demand (lowest position) then
                # Consumption. reports_for already sorts by position, so the
                # first card is always Demand — floors that don't have a
                # consumption report yet just render the one Demand card.
                for i, card in enumerate(cards):
                    card.setdefault("title", REPORT_CARD_LABELS[i] if i < len(REPORT_CARD_LABELS) else f"Report {i + 1}")
                tab["reports"] = cards
            ctx[tab_key] = tab

        html = template.render(**ctx)
        out_path = SITE_DIR / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")

    return written


def build_incomers(env: Environment, only: str | None = None) -> list[Path]:
    """Render incomer pages from _data/incomers.yaml. Template supports the
    simple form (chw/gas/lphw/lthw/water: summary cards + reports) and the
    rich form (electricity: + stat_grids + headed report)."""
    incomers_file = DATA_DIR / "incomers.yaml"
    if not incomers_file.exists():
        print(f"  (skip incomers: {incomers_file} not found)")
        return []

    incomers = yaml.safe_load(incomers_file.read_text(encoding="utf-8")) or {}
    reports = read_reports()
    building = env.globals.get("building", {})
    ems_name = building.get("ems_name", "EMS")
    written: list[Path] = []

    for key, raw in incomers.items():
        if only and only != key:
            continue
        ctx = dict(raw or {})
        ctx.setdefault("page_title", f"{ctx.get('heading', '')} · {ems_name}")

        if "reports" not in ctx:
            incomer_slug = key.removeprefix("incomer_")
            derived = reports_for(reports, page="incomer", incomer=incomer_slug, slot="main")
            ctx["reports"] = reports_to_cards(derived)

        # incomer_electricity has a bespoke floor-grid/transformer-grid layout.
        tmpl_name = ("incomer_electricity.html.j2"
                     if key == "incomer_electricity" else "incomer.html.j2")
        html = env.get_template(tmpl_name).render(**ctx)
        out_path = SITE_DIR / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")

    return written


def build_meters_hierarchy(env: Environment, only: str | None = None) -> list[Path]:
    """Render meters_hierarchy.htm by walking the parent_id tree in
    METER_REGISTRY from one or more configurable roots — e.g. one per
    utility (electricity / CHW / LTHW), each with its own top-level meter
    that carries no parent_id of its own."""
    if only and only != "meters_hierarchy":
        return []
    data_file = DATA_DIR / "meters_hierarchy.yaml"
    if not data_file.exists():
        print(f"  (skip meters_hierarchy: {data_file} not found)")
        return []

    ctx = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}

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
    root_ids = ctx.get("root_meter_ids")
    if root_ids is None:
        root_ids = [ctx.get("root_meter_id", 97)]
    missing = [r for r in root_ids if r not in by_id]
    if missing:
        raise SystemExit(f"meters_hierarchy: root_meter_id(s) {missing} not in METER_REGISTRY")
    ctx["root_meters"] = [by_id[r] for r in root_ids]
    ctx["children_map"] = dict(children_map)

    template = env.get_template("meters_hierarchy.html.j2")
    html = template.render(**ctx)
    out_path = SITE_DIR / "meters_hierarchy.htm"
    out_path.write_text(html, encoding="utf-8")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


# ─── Tenants ─────────────────────────────────────────────────────────────────
# Each tenant page lives at project/tenants/<tenant-slug>/<page>.htm — a
# sibling of SITE_DIR (project/<site-slug>/), not nested inside it. Asset
# paths and the sidebar script resolve via `path_prefix` ("../../<site-slug>//"),
# i.e. up two levels (tenants/<tenant-slug>/ → tenants/ → project/) then into
# the site directory. Floor placement and meter assignment derive from
# METER_REGISTRY: meters whose `tenant` field contains the tenant slug AND
# whose `floor` matches the page.
TENANT_PATH_PREFIX = f"../../{_SITE_SLUG}//"

# Floor sort key for floors-occupied lists and sidebar nav. Parses the
# leading ordinal digits ("37th" -> 37, "1st" -> 1) so it works for any
# floor count without a hardcoded per-building list (this build system
# targets multiple sites, not just this one). "ground" sorts as 0;
# "basementN"/"BN" (matching the CSV's own "B1"/"B4" basement-level codes)
# sorts below ground as -N; anything unrecognised sorts last rather than
# crashing, preserving its position relative to other unknowns. Every call
# site sorts with reverse=True (top floor first, going down), so "last"
# means the very bottom of that display — the SMALLEST key, not the
# largest, wins that spot once reversed. A bare "Basement" (no number) is
# exactly this case: it must sort below every numbered basement, not above
# every floor.
def _floor_sort_key(f: str) -> int:
    if f == "ground":
        return 0
    m = re.match(r"(?:basement|b)(\d+)$", f, re.IGNORECASE)
    if m:
        return -int(m.group(1))
    m = re.match(r"(\d+)", f)
    if m:
        return int(m.group(1))
    return -9999


def _floor_label(floor_key: str) -> str:
    if floor_key == "ground":
        return "Ground Floor"
    m = re.match(r"basement(\d+)$", floor_key)
    if m:
        return "Basement" if m.group(1) == "1" else f"Basement {m.group(1)}"
    # "B1"/"B4"-style keys (the CSV's own basement-level codes) keep their
    # existing bare form rather than becoming "B1 Floor".
    if re.match(r"b\d+$", floor_key, re.IGNORECASE):
        return floor_key
    return f"{floor_key} Floor"


def build_tenants(env: Environment, only: str | None = None) -> list[Path]:
    tenants_file = DATA_DIR / "tenants.yaml"
    if not tenants_file.exists():
        print(f"  (skip tenants: {tenants_file} not found)")
        return []
    tenants = yaml.safe_load(tenants_file.read_text(encoding="utf-8")) or {}

    meters = read_meters()
    reports = read_reports()
    bindings = read_bms_bindings()
    floor_template = env.get_template("tenant_floor.html.j2")
    index_template = env.get_template("tenant_index.html.j2")
    sidebar_template = env.get_template("tenant_sidebar.js.j2")
    written: list[Path] = []

    for slug, raw in tenants.items():
        if only and only != f"tenant_{slug}":
            continue
        data = dict(raw or {})
        display_name = data.get("display_name", slug.capitalize())
        tenant_dir = TENANTS_DIR / slug
        tenant_dir.mkdir(parents=True, exist_ok=True)

        # METER_REGISTRY's `tenant` field holds the display string as typed
        # in the CSV/registry (e.g. "MS Amlin", "Aegon / Draft Kings"), which
        # is usually NOT a clean slug/folder name — so matching against the
        # YAML key directly would miss most tenants (or break on embedded
        # "/"). `registry_tenant` supplies the real registry string(s) to
        # match on; defaults to the slug itself for tenants where they
        # happen to coincide. Accepts a single string or a list (a tenant
        # spelled more than one way across rows).
        registry_tenant = data.get("registry_tenant", slug)
        registry_names = (
            [registry_tenant] if isinstance(registry_tenant, str) else list(registry_tenant)
        )

        # Floors this tenant occupies (derived from registry), plus any
        # `extra_floors` the tenant YAML adds by hand (e.g. a Basement level
        # with no METER_REGISTRY rows yet — same "N/A" fallback as any other
        # not-yet-wired floor), minus any `exclude_floors` — a floor a
        # registry row tags this tenant onto (e.g. a calc meter with no
        # tenant_display yet) that shouldn't get its own page until it's
        # actually wired up. Ordered top floor first, going down — matching
        # the main sidebar's floor order (_auto_floors) rather than
        # ascending numeric order; basement keys sort below ground on their
        # own via _floor_sort_key, so they land at the bottom without any
        # special-casing here.
        tenant_meters = [m for m in meters if any(n in m["tenants"] for n in registry_names)]
        floor_keys = {f for m in tenant_meters for f in m["floors"]} | set(data.get("extra_floors") or [])
        floor_keys -= set(data.get("exclude_floors") or [])
        floors_occupied = sorted(floor_keys, key=_floor_sort_key, reverse=True)
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
                "floors_occupied": ", ".join(_floor_label(f) for f in floors_occupied),
                "reports":       idx_reports,
                "path_prefix":   TENANT_PATH_PREFIX,
                "sidebar_src":   "sidebar-template.js",
            }
            html = index_template.render(**ctx)
            out_path = tenant_dir / "index.htm"
            out_path.write_text(html, encoding="utf-8")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(ROOT / 'project')}")

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

            image = floor_data.get("floorplan_image") or (TENANT_PATH_PREFIX + default_floorplan_image(floor_key).lstrip("/"))
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
            # tenant's own tenant_display'd override meter (e.g. the 641+
            # "Aon Level NN Electricity" family) rather than falling back to
            # the shared generic row — see find_floor_summary_meter. A role
            # with no override for this tenant renders "N/A".
            floorplan_tab = {"layout": layout, "image": image}
            for card_key, card in derive_floor_summary_cards(meters, floor_key, registry_names).items():
                floorplan_tab[card_key] = card

            # Report tabs: Electricity/Heat/Cooling (Building Ventilation Report
            # is intentionally omitted on tenant floor pages) — a tenant
            # without registry/YAML data for a slot just gets an empty
            # reports list and "N/A" summary cards, same as any not-yet-wired
            # floor.
            tabs = [{"id": "floorplan", "label": floor_data.get("floorplan_tab_label", "Floorplan")}]
            tab_ctx: dict[str, dict] = {}
            for tab_key, tab_id, tab_label, override_key, slot, roles in (
                ("electricity_tab", "electricity-report", "Electricity Report",          "electricity_reports", "electricity", ELECTRICITY_TAB_ROLES),
                ("heat_tab",        "heat-report",         "Heating Energy Report",       "heat_reports",        "heat",        HEAT_TAB_ROLES),
                ("cooling_tab",     "cooling-report",      "Cooling Energy Report",       "cooling_reports",     "cooling",     COOLING_TAB_ROLES),
            ):
                tabs.append({"id": tab_id, "label": tab_label})
                tab_reports = floor_data.get(override_key)
                if tab_reports is None:
                    # No REPORT_REGISTRY rows are ever tagged page="tenant_floor"
                    # today (that'd mean a separate, tenant-scoped report library
                    # item per floor/slot, which doesn't exist) — fall back to
                    # the same floor's own page="floor" rows, so a tenant's
                    # report tab shows the identical report the main floor page
                    # does, with no duplicate registry entries required.
                    rows = reports_for(reports, page="tenant_floor", tenant=slug, floor=floor_key, slot=slot)
                    if not rows:
                        rows = reports_for(reports, page="floor", floor=floor_key, slot=slot)
                    tab_reports = reports_to_cards(rows)
                tab_ctx[tab_key] = {
                    "summary_cards": derive_summary_cards(roles, floor_key, bindings),
                    "reports":       tab_reports,
                }

            ctx = {
                "page_title":      floor_data.get("page_title", f"{display_name} - Floor Overview"),
                "heading":         floor_data.get("heading", f"{_floor_label(floor_key)} Overview"),
                "container_class": "floor-container",
                "tabs":            tabs,
                "floorplan_tab":   floorplan_tab,
                "path_prefix":     TENANT_PATH_PREFIX,
                "sidebar_src":     "sidebar-template.js",
                **tab_ctx,
            }

            html = floor_template.render(**ctx)
            out_path = tenant_dir / f"floor_{floor_key}.htm"
            out_path.write_text(html, encoding="utf-8")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(ROOT / 'project')}")

        # ── tenant sidebar-template.js ──
        floor_links = [
            {"href": f"floor_{f}.htm", "label": _floor_label(f)}
            for f in floors_occupied
        ]
        sidebar_ctx = {
            "tenant_name":  display_name,
            "path_prefix":  TENANT_PATH_PREFIX,
            "has_index":    has_index,
            "floor_links":  floor_links,
            "docs_href":    f"docs/{slug}-submetering.pdf",
        }
        sidebar_js = sidebar_template.render(**sidebar_ctx)
        out_path = tenant_dir / "sidebar-template.js"
        out_path.write_text(sidebar_js, encoding="utf-8")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(ROOT / 'project')}")

    return written


def build_schematics(env: Environment, only: str | None = None) -> list[Path]:
    """Render riser_*.htm + tariff_*.htm from _data/schematics.yaml.

    Each page is an SVG background + a list of positioned overlay widgets.
    """
    data_file = DATA_DIR / "schematics.yaml"
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

        html = template.render(**ctx)
        out_path = SITE_DIR / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return written


# ─── Sidebar ─────────────────────────────────────────────────────────────────
# The main sidebar (js/project/2.0/sidebar-template.js) is generated from
# _data/sidebar.yaml. Only the SIDEBAR_HTML constant between the BEGIN/END
# markers is touched; the runtime behaviour code below is hand-maintained.

SIDEBAR_BEGIN = "// ── BEGIN GENERATED SIDEBAR_HTML ── DO NOT EDIT BY HAND ──"
SIDEBAR_END = "// ── END GENERATED SIDEBAR_HTML ──"
SIDEBAR_JS = SITE_DIR / "js" / "project" / "2.0" / "sidebar-template.js"

# Auto-list expansion: maps `auto: <type>` to the function that produces
# the list of items the parent's children should be expanded with.
INCOMER_LABELS = {
    "electricity": "Electricity",
    "gas": "Gas",
    "water": "Water",
    "lphw": "LPHW",
    "lthw": "LTHW",
    "chw": "CHW",
}


def _auto_floors() -> list[dict]:
    """List of floor menu-items, top floors first (reverse natural order)."""
    floors_file = DATA_DIR / "floors.yaml"
    floors = yaml.safe_load(floors_file.read_text(encoding="utf-8")) or {}
    keys = [floor_key_from_page_key(k) for k in floors]
    keys.sort(key=_floor_sort_key, reverse=True)
    items: list[dict] = []
    for k in keys:
        label = "Ground Floor" if k == "ground" else f"Floor {k}"
        items.append({"_key": k, "label": label, "href": f"floor_{k}.htm"})
    return items


def _auto_incomers() -> list[dict]:
    incomers_file = DATA_DIR / "incomers.yaml"
    data = yaml.safe_load(incomers_file.read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    for page_key in data:
        slug = page_key.removeprefix("incomer_")
        items.append({
            "_key":  slug,
            "label": INCOMER_LABELS.get(slug, slug.capitalize()),
            "href":  f"{page_key}.htm",
        })
    return items


def _auto_switchboards() -> list[dict]:
    """Switchboard sub-items: 'LV-01', 'LV-02', etc. Driven by switchboards.yaml."""
    sb_file = DATA_DIR / "switchboards.yaml"
    if not sb_file.exists():
        return []
    cfg = yaml.safe_load(sb_file.read_text(encoding="utf-8")) or {}
    boards = cfg.get("boards") or {}
    items: list[dict] = []
    for key in boards:
        # swb_lv01 → "LV-01"
        suffix = key.removeprefix("swb_")
        if suffix.lower().startswith("lv") and suffix[2:].isdigit():
            label = f"LV-{int(suffix[2:]):02d}"
        else:
            label = suffix.upper()
        items.append({"_key": key, "label": label, "href": f"{key}.htm"})
    return items


def _auto_tenants(meters: list[dict]) -> list[dict]:
    """Tenant menu-items in tenants.yaml order; href varies by whether the
    tenant has an index page or only a single floor view."""
    t_file = DATA_DIR / "tenants.yaml"
    tenants = yaml.safe_load(t_file.read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    for slug, raw in tenants.items():
        data = raw or {}
        display_name = data.get("display_name", slug.capitalize())
        # Match METER_REGISTRY's `tenant` field the same way build_tenants()
        # does — it's the display string as typed in the registry (e.g. "MS
        # Amlin"), which usually isn't the slug, so matching on slug alone
        # silently finds nothing and every tenant falls back to /index.htm.
        registry_tenant = data.get("registry_tenant", slug)
        registry_names = (
            [registry_tenant] if isinstance(registry_tenant, str) else list(registry_tenant)
        )
        tenant_meters = [m for m in meters if any(n in m["tenants"] for n in registry_names)]
        floors_occupied = sorted({f for m in tenant_meters for f in m["floors"]},
                                  key=_floor_sort_key)
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
        return [{k: v for k, v in it.items() if k != "_key"} for it in items]
    by_key = {it.get("_key"): it for it in items}
    out: list[dict] = []
    for key in only:
        it = by_key.get(key)
        if it is None:
            continue
        out.append({k: v for k, v in it.items() if k != "_key"})
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
        i_from, i_to = by_key_index.get(g.get("from")), by_key_index.get(g.get("to"))
        if i_from is None or i_to is None:
            continue
        lo, hi = sorted((i_from, i_to))
        members = [{k: v for k, v in it.items() if k != "_key"} for it in items[lo:hi + 1]]
        if members:
            out.append({"label": g["label"], "children": members})
    return out


def _expand_auto(children: list[dict], auto_lists: dict) -> list[dict]:
    """Walk a children list and replace {auto: <type>} markers with the
    corresponding expanded item list. Supports `only: [<key>, ...]` to
    filter + reorder the auto list, or `groups: [{label, from, to}, ...]`
    to bucket it into range sub-menus instead (see _apply_groups)."""
    out: list[dict] = []
    for child in children:
        auto = child.get("auto")
        if auto:
            base = auto_lists.get(auto, [])
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


def build_sidebar(env: Environment, only: str | None = None) -> list[Path]:
    if only and only != "sidebar":
        return []
    sidebar_file = DATA_DIR / "sidebar.yaml"
    if not sidebar_file.exists():
        print(f"  (skip sidebar: {sidebar_file} not found)")
        return []
    if not SIDEBAR_JS.exists():
        print(f"  (skip sidebar: {SIDEBAR_JS} not found)")
        return []

    cfg = yaml.safe_load(sidebar_file.read_text(encoding="utf-8")) or {}
    meters = read_meters()

    # Brand + footer are site facts: take them from building.yaml unless the
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
        "tenants":      _auto_tenants(meters),
    }

    # Expand auto: markers inside top/sections/bottom item lists
    cfg["top_items"] = _expand_auto(cfg.get("top_items") or [], auto_lists)
    cfg["bottom_items"] = _expand_auto(cfg.get("bottom_items") or [], auto_lists)
    for section in cfg.get("sections", []):
        section["items"] = _expand_auto(section.get("items", []), auto_lists)

    template = env.get_template("sidebar.js.j2")
    new_block = SIDEBAR_BEGIN + "\n" + template.render(**cfg) + "\n" + SIDEBAR_END

    js = SIDEBAR_JS.read_text(encoding="utf-8")
    pattern = re.escape(SIDEBAR_BEGIN) + r".*?" + re.escape(SIDEBAR_END)
    if not re.search(pattern, js, flags=re.DOTALL):
        raise SystemExit(f"BEGIN/END SIDEBAR_HTML markers not found in {SIDEBAR_JS}")
    js2 = re.sub(pattern, new_block, js, flags=re.DOTALL)
    SIDEBAR_JS.write_text(js2, encoding="utf-8")
    print(f"  wrote {SIDEBAR_JS.relative_to(SITE_DIR)}")
    return [SIDEBAR_JS]


def build_home(env: Environment, only: str | None = None) -> list[Path]:
    """Render the home landing page from _data/home.yaml (singleton)."""
    if only and only != "home":
        return []
    home_file = DATA_DIR / "home.yaml"
    if not home_file.exists():
        print(f"  (skip home: {home_file} not found)")
        return []

    ctx = yaml.safe_load(home_file.read_text(encoding="utf-8")) or {}
    building = env.globals.get("building", {})
    ctx.setdefault("page_title", f"{building.get('name', '')} - Dashboard")
    ctx.setdefault("container_class", "floor-container")

    reports = read_reports()
    if "top_reports" not in ctx:
        ctx["top_reports"] = reports_to_cards(reports_for(reports, page="home", slot="top"))
    if "reports" not in ctx:
        ctx["reports"] = reports_to_cards(reports_for(reports, page="home", slot="main"))

    template = env.get_template("home.html.j2")
    html = template.render(**ctx)
    out_path = SITE_DIR / "home.htm"
    out_path.write_text(html, encoding="utf-8")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def _floor_node_name(floor_key: str) -> str:
    """Registry floor key → diagram node name: '1st' → 'Floor 1'."""
    digits = "".join(c for c in floor_key if c.isdigit())
    return f"Floor {digits}" if digits else floor_key.capitalize()


def build_energy_flow(env: Environment, only: str | None = None) -> list[Path]:
    """Render the LIVE electrical-demand Sankey from _data/energy_flow.yaml.

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
    data_file = DATA_DIR / "energy_flow.yaml"
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
    for floor_key in ctx.get("floors") or []:
        node = _floor_node_name(floor_key)
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
    html = template.render(**ctx)
    out_path = SITE_DIR / "energy_flow.htm"
    out_path.write_text(html, encoding="utf-8")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def build_dials(env: Environment, only: str | None = None) -> list[Path]:
    """Render the live KPI dials page from _data/dials.yaml (singleton).

    Each `dials` entry is a segmented gauge bound to a live BACnet point,
    rendered by the live_dial macro + js/project/2.0/energy-dials.js."""
    if only and only != "dials":
        return []
    data_file = DATA_DIR / "dials.yaml"
    if not data_file.exists():
        print(f"  (skip dials: {data_file} not found)")
        return []

    ctx = yaml.safe_load(data_file.read_text(encoding="utf-8")) or {}
    ctx.setdefault("page_title", "Live KPI Dials")
    ctx.setdefault("heading", "Live KPI Dials")
    ctx.setdefault("container_class", "floor-container")

    template = env.get_template("dials.html.j2")
    html = template.render(**ctx)
    out_path = SITE_DIR / "dials.htm"
    out_path.write_text(html, encoding="utf-8")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def build_pages(env: Environment, only: str | None = None) -> list[Path]:
    """Render one-off singleton pages (_data/pages.yaml) through the base shell.

    These are pages not driven by a data registry (building performance,
    landlord services, docs, the legacy verde-template floors 6–11, the report
    viewer scaffold, …). Their bespoke body and any head/script extras live as
    raw HTML fragments in _templates/pages/<key>.{body,styles,extra_scripts,
    tail_scripts}.html (produced once by _build/extract_pages.py, then hand
    maintained); pages.yaml carries only per-page metadata.
    """
    pages_file = DATA_DIR / "pages.yaml"
    if not pages_file.exists():
        print(f"  (skip pages: {pages_file} not found)")
        return []

    data = yaml.safe_load(pages_file.read_text(encoding="utf-8")) or {}
    pages_dir = TEMPLATES_DIR / "pages"
    template = env.get_template("page.html.j2")
    written: list[Path] = []
    for page in data.get("pages", []):
        key = page["key"]
        if only and only != key:
            continue

        def frag(suffix: str, _key: str = key) -> str:
            path = pages_dir / f"{_key}.{suffix}.html"
            if not path.exists():
                return ""
            # Rendered through the shared env so fragments can reference
            # {{ building.* }} (e.g. the homepage welcome banner) instead of
            # hardcoding site facts.
            return env.from_string(path.read_text(encoding="utf-8")).render()

        ctx = dict(page)
        ctx["body"] = frag("body")
        ctx["extra_styles_html"] = frag("styles")
        ctx["extra_scripts_html"] = frag("extra_scripts")
        ctx["tail_scripts_html"] = frag("tail_scripts")
        # heading/page_title in pages.yaml may themselves reference
        # {{ building.* }} (kept as data so a rename only touches building.yaml).
        for meta_key in ("heading", "page_title"):
            if isinstance(ctx.get(meta_key), str):
                ctx[meta_key] = env.from_string(ctx[meta_key]).render()

        out_path = SITE_DIR / page["out"]
        out_path.write_text(template.render(**ctx), encoding="utf-8")
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")
        written.append(out_path)
    return written


def build_building_performance(env: Environment, only: str | None = None) -> list[Path]:
    """Render building_performance.htm — NABERS base-building page.

    Fully data-driven: building facts from building.yaml (via the `building`
    global), live values via named POINTS (data-point in the template), and the
    report cards from REPORT_REGISTRY rows (page=building_performance, slots
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
    out_path = SITE_DIR / "building_performance.htm"
    out_path.write_text(template.render(**ctx), encoding="utf-8")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def validate() -> int:
    """Cross-check the input data and report problems. Returns count of errors.

    Catches the failures that turn "data in → displays out" from a promise into
    a guarantee: dangling report image-refs, unknown named points, meter/point
    ids referenced by a page that don't exist, and floors that can't render.
    """
    problems: list[str] = []

    meters = read_meters()
    meter_ids = {m["id"] for m in meters}
    points = read_points()
    report_urls = read_report_urls()
    reports = read_reports()

    # 1. Every REPORT_REGISTRY row's image_ref must resolve in ReportUrls.reports.
    for r in reports:
        ref = r.get("image_ref")
        if ref and ref not in report_urls:
            problems.append(f"REPORT_REGISTRY: image_ref '{ref}' not found in ReportUrls.reports")

    # 2. POINTS must each carry a bacnet address.
    for name, pt in points.items():
        if not pt.get("bacnet"):
            problems.append(f"POINTS: '{name}' has no bacnet address")

    # 3. data-point / data-meter-id literals in templates+fragments must resolve.
    sources = list((TEMPLATES_DIR).rglob("*.j2")) + list((TEMPLATES_DIR / "pages").glob("*.html"))
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for name in set(re.findall(r'data-point="([^"]+)"', text)):
            if name not in points:
                problems.append(f"{path.relative_to(SITE_DIR)}: data-point '{name}' not in POINTS")
        for mid in set(re.findall(r'data-meter-id="(\d+)"', text)):
            if int(mid) not in meter_ids:
                problems.append(f"{path.relative_to(SITE_DIR)}: data-meter-id '{mid}' not in METER_REGISTRY")

    # 4. Every floor in floors.yaml must be renderable (registry meters or layout).
    floors_file = DATA_DIR / "floors.yaml"
    defined_floor_keys: set[str] = set()
    if floors_file.exists():
        floors = yaml.safe_load(floors_file.read_text(encoding="utf-8")) or {}
        defined_floor_keys = {floor_key_from_page_key(k) for k in floors}
        for key, raw in floors.items():
            fkey = floor_key_from_page_key(key)
            has_meters = any(fkey in m["floors"] for m in meters)
            has_layout = bool((raw or {}).get("floorplan_tab", {}).get("layout"))
            if not has_meters and not has_layout:
                problems.append(f"floors.yaml: '{key}' has no registry meters and no explicit layout")

        # 5. Every floor token a meter names (a meter can list several,
        # "/"-separated, e.g. floor: "3rd/4th") must match a floors.yaml page —
        # otherwise a typo silently drops the meter from that floor with no error.
        # column: null meters aren't placed in a floor's riser grid at all
        # (derive_layout excludes them the same way) — they use `floor` as a
        # bare location label (basement plant rooms, etc.), so an unmatched
        # token there isn't a page-rendering bug.
        #
        # A floor token with no floors.yaml page is only a real typo risk if
        # it was meant for a main-building page — a tenant-only floor (e.g.
        # AON's "Basement", which only ever renders via build_tenants, never
        # build_floors) legitimately has no floors.yaml entry. Distinguish
        # the two by tenant tag: if every grid-placed meter naming this
        # floor is tagged to a tenant, it's tenant-only and not a typo;
        # an untagged (landlord/common) meter on an undefined floor means
        # someone meant a main-page floor and mistyped its key.
        used_floor_tokens = {f for m in meters if m["column"] is not None for f in m["floors"]}
        for token in sorted(used_floor_tokens - defined_floor_keys):
            tagged_meters = [m for m in meters if m["column"] is not None and token in m["floors"]]
            if all(m["tenants"] for m in tagged_meters):
                continue
            problems.append(f"METER_REGISTRY: floor '{token}' has no matching page in floors.yaml (typo?)")

    if problems:
        print(f"VALIDATION FAILED - {len(problems)} problem(s):")
        for p in problems:
            print(f"  [X] {p}")
    else:
        print("Validation passed: reports, points, meter refs, and floors all resolve.")
    return len(problems)


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
        help="Validate input data cross-references and exit (no pages written).",
    )
    args = parser.parse_args(argv)

    if args.check:
        return 1 if validate() else 0

    env = make_env()
    print("Building pages...")
    written = build_floors(env, only=args.only)
    written += build_incomers(env, only=args.only)
    written += build_home(env, only=args.only)
    written += build_meters_hierarchy(env, only=args.only)
    written += build_schematics(env, only=args.only)
    written += build_building_performance(env, only=args.only)
    written += build_pages(env, only=args.only)
    written += build_sidebar(env, only=args.only)
    # NOTE: build_energy_flow / build_dials are omitted — those pages don't
    # exist on this site. build_tenants is deferred (tenant pages not yet
    # reconciled); re-enable it once _data/tenants.yaml is aligned to test2.

    # Switchboards (swb_lv01/swb_lv02) are bespoke pixel-overlay pages over a
    # hand-drawn SVG (img/lv01.svg, img/lv02.svg) — reproduced as frozen-body
    # singletons via _data/pages.yaml + _templates/pages/<key>.body.html, the
    # same way the risers are. The data-driven build_switchboards.py generator
    # is retained in _build/ but no longer run from main().

    print(f"Done. {len(written)} file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
