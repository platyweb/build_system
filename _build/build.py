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
data/bms_bindings.yaml, report cards from data/reports.yaml. README.md
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
import io
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context

import components
import generate_meter_registry
import jsblocks
import linkcheck

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "_templates"   # engine templates
ASSETS_DIR = ROOT / "_assets"         # engine runtime skeleton (project JS/CSS, vendor libs)
COMPONENTS_DIR = ROOT / "_components" # engine component catalog (see components.py)
DEFAULT_SITE_ROOT = ROOT / "site"
DEFAULT_OUT_ROOT = ROOT / "project"

# Written into the output root by stage_output(). A full build only ever
# wipes an output root that carries it, so pointing --out at a directory
# this build didn't create (a hand-maintained deploy copy, say) can't
# destroy it.
OUTPUT_MARKER = ".build-output"

# ─── Site + output paths ─────────────────────────────────────────────────────
# Everything specific to one building lives under its site directory
# (default site/):
#   site.yaml   site/building identity (the `building` template global)
#   data/       the YAML data files + meters.csv
#   pages/      frozen page fragments rendered by build_pages()
#   templates/  template overrides, searched before _templates/
#   assets/     site images (floorplans, SVG backgrounds, logos), copied
#               over _assets/ into the output by stage_output()
#
# configure() points the module-level paths below at one site directory and
# output root; main() calls it from --site/--out. The module builders in
# their own files (build_switchboards.py, build_risers.py) read these paths
# from this module at call time. Nothing here is evaluated at import time.
SITE_ROOT: Path            # site/
DATA_DIR: Path             # site/data/
BUILDING_FILE: Path        # site/site.yaml
OUT_ROOT: Path             # project/
SITE_DIR: Path             # project/<slug>/ — the deployed site
# Tenant pages live directly under project/tenants/ — a sibling of SITE_DIR,
# not nested inside it (see build_tenants()/TENANT_PATH_PREFIX below).
TENANTS_DIR: Path
METERS_JS: Path
REPORTS_JS: Path
SIDEBAR_JS: Path
LIVE_POINTS_JS: Path
TENANT_PATH_PREFIX: str
# site.yaml `bacnet:` — {device, power_offset: {<meter type>: <offset>}}.
# The one source of the point-address rule (see bacnet_address/demand_address).
BACNET: dict
# site.yaml `utilities:` — {code: {label, kind}}, in the site's order. See
# read_utilities().
UTILITIES: dict[str, dict]
# site.yaml `buildings:` — [{key, name}] (empty for a site that doesn't list
# its buildings). CAMPUS: more than one, so each building's pages get their
# own subfolder — see page_location().
BUILDINGS: list[dict]
CAMPUS: bool


def configure(site_root: Path = DEFAULT_SITE_ROOT, out_root: Path = DEFAULT_OUT_ROOT) -> None:
    """Point every module-level path at `site_root` (input) and `out_root`
    (output). The output directory name — project/<slug>/ — is site.yaml's
    `slug`, the site's single source of identity."""
    global SITE_ROOT, DATA_DIR, BUILDING_FILE, OUT_ROOT, SITE_DIR, TENANTS_DIR
    global METERS_JS, REPORTS_JS, SIDEBAR_JS, LIVE_POINTS_JS, TENANT_PATH_PREFIX, BACNET, UTILITIES
    global SUMMARY_ROLES, FLOOR_PAGE, TENANT_PAGE, BUILDINGS, CAMPUS
    SITE_ROOT = Path(site_root).resolve()
    DATA_DIR = SITE_ROOT / "data"
    BUILDING_FILE = SITE_ROOT / "site.yaml"
    if not BUILDING_FILE.exists():
        raise SystemExit(f"{BUILDING_FILE} not found — is {SITE_ROOT} a site directory? "
                         "(A new site starts as a copy of an example: cp -r examples/minimal site)")
    building = read_building()
    slug = building.get("slug")
    if not slug:
        raise SystemExit(f"{BUILDING_FILE}: `slug` is required (it names the output directory)")
    BACNET = building.get("bacnet") or {}
    if "device" not in BACNET or not isinstance(BACNET.get("power_offset"), dict):
        raise SystemExit(
            f"{BUILDING_FILE}: `bacnet: {{device: <id>, power_offset: {{<meter type>: <offset>, …}}}}` is required"
        )
    UTILITIES = read_utilities(building)
    BUILDINGS = read_buildings(building)
    CAMPUS = len(BUILDINGS) > 1
    SUMMARY_ROLES, FLOOR_PAGE, TENANT_PAGE = read_page_config(building)

    OUT_ROOT = Path(out_root).resolve()
    SITE_DIR = OUT_ROOT / slug
    TENANTS_DIR = OUT_ROOT / "tenants"
    js_dir = SITE_DIR / "js" / "project" / "2.0"
    METERS_JS = js_dir / "meter-templates.js"
    REPORTS_JS = js_dir / "reports.js"
    SIDEBAR_JS = js_dir / "sidebar-template.js"
    LIVE_POINTS_JS = js_dir / "live-points.js"
    # Asset paths and the sidebar script on tenant pages resolve via this
    # prefix: up two levels (tenants/<tenant-slug>/ → tenants/ → project/),
    # then into the site directory.
    TENANT_PATH_PREFIX = f"../../{slug}//"


def stage_output() -> None:
    """Recreate the output root from scratch for a full build.

    Wipes OUT_ROOT (only if a previous build created it — see
    OUTPUT_MARKER), copies the engine skeleton (_assets/) into SITE_DIR and
    overlays the site's own assets (site/assets/) on top. The builders then
    write pages into it and inject generated blocks into its JS — _assets/
    itself is never modified.
    """
    if OUT_ROOT.exists():
        if not (OUT_ROOT / OUTPUT_MARKER).exists():
            raise SystemExit(
                f"{OUT_ROOT} exists but has no {OUTPUT_MARKER} marker, so this build didn't create it — "
                "refusing to wipe it. Move it aside or pass a different --out."
            )
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    (OUT_ROOT / OUTPUT_MARKER).write_text(
        "Created by _build/build.py. A full build deletes and recreates this whole directory.\n",
        encoding="utf-8", newline="\n",
    )
    shutil.copytree(ASSETS_DIR, SITE_DIR)
    site_assets = SITE_ROOT / "assets"
    if site_assets.exists():
        shutil.copytree(site_assets, SITE_DIR, dirs_exist_ok=True)
    print(f"  staged {SITE_DIR.relative_to(OUT_ROOT)}/ from _assets/"
          + (" + site assets" if site_assets.exists() else ""))


def write_js_blocks() -> None:
    """Write the site's data into the staged runtime JS (see jsblocks.py):
    METER_REGISTRY from data/meters.csv, POINTS from data/points.yaml,
    BACNET_CONFIG from site.yaml `bacnet:` and ReportUrls from
    data/reports.yaml `urls:`. SIDEBAR_HTML is written by build_sidebar(),
    which owns that rendering. live-points.js's OVERRIDE_FILE — the Optergy
    display that point overrides post to — is site.yaml
    `optergy_override_display` (left blank in the skeleton if unset)."""
    meters = generate_meter_registry.read_csv(DATA_DIR / "meters.csv", UTILITIES)
    jsblocks.inject(METERS_JS, jsblocks.METER_REGISTRY, jsblocks.render_meter_registry(meters))
    jsblocks.inject(METERS_JS, jsblocks.POINTS, jsblocks.render_points(read_points()))
    jsblocks.inject(METERS_JS, jsblocks.BACNET_CONFIG, jsblocks.render_bacnet_config(BACNET))
    jsblocks.inject(REPORTS_JS, jsblocks.REPORT_URLS,
                    jsblocks.render_report_urls(_read_data("reports.yaml", "urls", {})))
    override_display = read_building().get("optergy_override_display")
    if override_display:
        jsblocks.set_string_property(LIVE_POINTS_JS, "OVERRIDE_FILE", str(override_display))


def _rel(path: Path) -> str:
    """`path` relative to the repo root for messages, absolute if outside it."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ─── BACnet point addresses ──────────────────────────────────────────────────
# One rule, shared by every page generator and (via the generated
# BACNET_CONFIG block) the runtime's FIELD_CONFIG in meter-templates.js:
#   "<device>|<object type>|<instance>|85|-1"
# A meter's live demand is analog value (object type 0) instance
# base + power_offset[meter type]; its comms status is binary value
# (object type 3) instance base.
def bacnet_address(object_type: int, instance: int) -> str:
    return f"{BACNET['device']}|{object_type}|{instance}|85|-1"


def demand_address(meter: dict) -> str:
    return bacnet_address(0, meter["base"] + BACNET["power_offset"][meter["type"]])



# ─── Utilities ───────────────────────────────────────────────────────────────
# A site's utilities are a catalog in site.yaml, in display order:
#     utilities:
#       electricity: {label: Electricity, kind: electric}
#       lthw:        {label: LTHW,        kind: thermal}
# The code is what meters.csv rows resolve to and what the CSS keys off
# (.meter-<code>); the label names it on pages (incomer menu, zone cards);
# the kind groups utilities for the zone-card subtitle — electric, thermal
# (heating and cooling both: heat meters measure LTHW and CHW alike) or other.
UTILITY_KINDS = ("electric", "thermal", "other")


def read_utilities(building: dict) -> dict[str, dict]:
    """site.yaml `utilities:` → {code: {label, kind}}, checked."""
    raw = building.get("utilities")
    if not isinstance(raw, dict) or not raw:
        raise SystemExit(f"{_rel(BUILDING_FILE)}: `utilities:` is required — "
                         "{<code>: {label: <name>, kind: electric|thermal|other}, …}")
    out: dict[str, dict] = {}
    for code, spec in raw.items():
        code, spec = str(code), spec or {}
        if not re.fullmatch(r"[a-z0-9_]+", code):
            raise SystemExit(f"{_rel(BUILDING_FILE)}: utility code '{code}' must be lowercase letters, "
                             "digits or _ (it becomes the CSS class meter-<code>)")
        if spec.get("kind") not in UTILITY_KINDS:
            raise SystemExit(f"{_rel(BUILDING_FILE)}: utility '{code}' needs `kind:` — one of {', '.join(UTILITY_KINDS)}")
        out[code] = {"label": str(spec.get("label", code)), "kind": spec["kind"]}
    return out


# ─── Conventions for floor pages ─────────────────────────────────────────────
# A meter's `utility` may carry a "-virtual" suffix ("lthw-virtual" in the
# CSV) marking it as calculated rather than physical. That suffix exists only
# to pick the meter-<utility>-virtual CSS class, so every comparison asking
# *which* utility a meter carries has to strip it first — a virtual LTHW
# meter is still LTHW, and still heat.
VIRTUAL_UTILITY_SUFFIX = "-virtual"


def base_utility(utility: str) -> str:
    """The utility code without its virtual marker: "lthw-virtual" -> "lthw"."""
    return utility.removesuffix(VIRTUAL_UTILITY_SUFFIX)


# ─── Floor & tenant page configuration ───────────────────────────────────────
# site.yaml `summary_roles:` (the summary-card catalog: role → {title,
# format}; a card's live point comes from bms_bindings.yaml by (role,
# floor)), `floor_page:` and `tenant_page:` — read and given their defaults
# by read_page_config(), whose defaults list every field.
SUMMARY_ROLES: dict[str, dict]
FLOOR_PAGE: dict
TENANT_PAGE: dict

# floor_page.summary_cards keys → extra card fields (the total card sits
# beside the floorplan image; tenants/landlords share the row below).
FLOOR_SUMMARY_CARDS: dict[str, dict] = {
    "total":     {"wrapper_class": "floor-summary-center-block floor-card"},
    "tenants":   {},
    "landlords": {},
}


def read_page_config(building: dict) -> tuple[dict, dict, dict]:
    """(summary_roles, floor_page, tenant_page) from site.yaml, checked,
    with defaults filled in."""
    where = _rel(BUILDING_FILE)
    roles: dict[str, dict] = {}
    for role, spec in (building.get("summary_roles") or {}).items():
        spec = spec or {}
        if "title" not in spec or "format" not in spec:
            raise SystemExit(f"{where}: summary_roles '{role}' needs `title:` and `format:`")
        roles[str(role)] = {"title": str(spec["title"]), "format": str(spec["format"])}

    fp = building.get("floor_page") or {}
    tabs: list[dict] = []
    for t in fp.get("tabs") or []:
        missing = [k for k in ("id", "label", "slot") if k not in t]
        if missing:
            raise SystemExit(f"{where}: floor_page tab {t!r} needs {', '.join(missing)}")
        unknown = [r for r in t.get("roles") or [] if r not in roles]
        if unknown:
            raise SystemExit(f"{where}: floor_page tab '{t['id']}' lists role(s) {unknown} "
                             "that aren't in `summary_roles:`")
        tabs.append({"id": str(t["id"]), "label": str(t["label"]), "slot": str(t["slot"]),
                     "roles": [str(r) for r in t.get("roles") or []]})
    cards = {str(k): str(v) for k, v in (fp.get("summary_cards") or {}).items()}
    unknown = sorted(cards.keys() - FLOOR_SUMMARY_CARDS.keys())
    if unknown:
        raise SystemExit(f"{where}: floor_page.summary_cards {unknown} — known: {', '.join(FLOOR_SUMMARY_CARDS)}")
    floor_page = {
        "riser_card_link": str(fp.get("riser_card_link", "#")),
        "summary_label":   str(fp.get("summary_label", "Summary")),
        "summary_cards":   cards,
        "centre_zone":     fp.get("centre_zone"),
        "zone_suffix":     {"centre": "", "side": ""} | (fp.get("zone_suffix") or {}),
        "zone_subtitles":  DEFAULT_ZONE_SUBTITLES | (fp.get("zone_subtitles") or {}),
        "report_titles":   [str(x) for x in fp.get("report_titles") or []],
        "tabs":            tabs,
    }

    tp = building.get("tenant_page") or {}
    by_id = {t["id"]: t for t in tabs}
    tab_ids = [str(i) for i in tp["tabs"]] if "tabs" in tp else list(by_id)
    unknown = [i for i in tab_ids if i not in by_id]
    if unknown:
        raise SystemExit(f"{where}: tenant_page.tabs {unknown} aren't floor_page tab ids ({', '.join(by_id)})")
    tenant_page = {
        "summary_label": str(tp.get("summary_label", "Floorplan")),
        "tabs":          [by_id[i] for i in tab_ids],
    }
    return roles, floor_page, tenant_page


def floor_key_from_page_key(page_key: str) -> str:
    """floor_ground → ground, floor_1st → 1st."""
    return page_key.removeprefix("floor_")


# ─── Buildings ───────────────────────────────────────────────────────────────
# A campus lists its buildings in site.yaml:
#     buildings:
#       - { key: north, name: "North Tower" }
#       - { key: south, name: "South Annex" }
# Every level names its building (floors.yaml `building:`), and so may an
# incomer, switchboard or pages.yaml entry. With more than one building, a
# building's pages go to <site>/<key>/ — floors, its incomers/switchboards/
# risers/pages — while site-wide pages (home, meters hierarchy, energy flow,
# dials, site-wide incomers and pages) stay at the root. Each building folder
# gets its own sidebar-template.js with links rewritten for that folder.
# A single-building site needn't list `buildings:` at all; its pages stay at
# the root either way.
def read_buildings(building: dict) -> list[dict]:
    """site.yaml `buildings:` → [{key, name}], checked."""
    out: list[dict] = []
    for b in building.get("buildings") or []:
        key = str((b or {}).get("key", ""))
        if not re.fullmatch(r"[a-z0-9_-]+", key):
            raise SystemExit(f"{_rel(BUILDING_FILE)}: building {b!r} needs a `key:` of lowercase letters, "
                             "digits, - or _ (it names the building's page folder)")
        if any(o["key"] == key for o in out):
            raise SystemExit(f"{_rel(BUILDING_FILE)}: building key '{key}' is listed twice")
        out.append({"key": key, "name": str(b.get("name", key))})
    return out


def check_building(key, where: str, *, level: bool = False) -> str | None:
    """A `building:` field's value, checked against site.yaml `buildings:`.
    Levels must name one on a campus; anything else may leave it out to
    stay site-wide."""
    if key is None:
        if level and CAMPUS:
            raise SystemExit(f"{where}: needs `building:` — this site has several buildings "
                             f"({', '.join(b['key'] for b in BUILDINGS)})")
        return None
    key = str(key)
    if key not in {b["key"] for b in BUILDINGS}:
        known = ", ".join(b["key"] for b in BUILDINGS) or "none — add `buildings:` to site.yaml"
        raise SystemExit(f"{where}: building '{key}' isn't in site.yaml `buildings:` ({known})")
    return key


def page_location(building: str | None) -> tuple[Path, dict]:
    """(output directory, extra template context) for a page belonging to
    `building` (None: site-wide). On a campus a building's pages live in
    their own subfolder, so assets resolve via path_prefix "../" and the
    folder's own sidebar-template.js (see build_sidebar)."""
    if not (CAMPUS and building):
        return SITE_DIR, {}
    out_dir = SITE_DIR / building
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, {"path_prefix": "../", "sidebar_src": "sidebar-template.js"}


def page_folder(building: str | None) -> str | None:
    """The subfolder a building's pages live in (None: the site root)."""
    return building if CAMPUS and building else None


def site_href(building: str | None, filename: str) -> str:
    """A page's URL relative to the site root, e.g. "north/floor_n-l01.htm"."""
    folder = page_folder(building)
    return f"{folder}/{filename}" if folder else filename


def relative_url(url: str, folder: str | None) -> str:
    """`url` — written relative to the site root, as data and templates
    write them — rewritten for a page in `folder` (None: the root, unchanged).
    Absolute, external and in-page URLs are left alone."""
    if not folder or not url or url.startswith(("/", "#", "mailto:", "javascript:", "../")) or "://" in url:
        return url
    if url.startswith(folder + "/"):
        return url[len(folder) + 1:]
    return "../" + url


# ─── Level roster ────────────────────────────────────────────────────────────
# site/data/floors.yaml is the site's ordered list of levels, bottom → top:
# each `floor_<key>:` entry is one level, and its position in the file is its
# physical position. That order — never the spelling of the key — drives
# every floor ordering in the build (sidebar, tenant floor lists, riser
# diagrams), so any naming works: ground/1st, L00/L01, Mezzanine, Roof, B2.
#
# Level fields (all optional):
#   label     : display name, e.g. "1st Floor"       — default: the key
#   nav_label : sidebar menu text                    — default: label
#   heading   : the floor page's <h1>                — default: "<label> Overview"
#   page      : false for a level with meters but no page of its own
#               (plant basements, a roof)            — default: true
# Any other field is page data for build_floors (floorplan_tab, tabs, …).
#   building  : the building it belongs to (site.yaml `buildings:` key) —
#               required on a campus, where it picks the page's subfolder
LEVEL_FIELDS = ("label", "nav_label", "heading", "page", "building")


def read_levels() -> list[dict]:
    """The level roster, bottom → top. Each level is
    {key, page_key, label, nav_label, heading, page, data} — `data` holds the
    entry's non-roster fields (the floor page's own overrides)."""
    floors_file = DATA_DIR / "floors.yaml"
    if not floors_file.exists():
        return []
    levels: list[dict] = []
    for page_key, entry in (_load_yaml_unique_keys(floors_file) or {}).items():
        page_key = str(page_key)
        if not page_key.startswith("floor_"):
            raise SystemExit(f"{_rel(floors_file)}: level '{page_key}' must be written floor_<key>")
        entry = dict(entry or {})
        key = floor_key_from_page_key(page_key)
        label = str(entry.get("label", key))
        levels.append({
            "key":       key,
            "page_key":  page_key,
            "label":     label,
            "nav_label": str(entry.get("nav_label", label)),
            "heading":   str(entry.get("heading", f"{label} Overview")),
            "page":      entry.get("page", True) is not False,
            "building":  check_building(entry.get("building"), f"{_rel(floors_file)} '{page_key}'", level=True),
            "data":      {k: v for k, v in entry.items() if k not in LEVEL_FIELDS},
        })
    return levels


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys — PyYAML otherwise
    keeps the last one silently, which in floors.yaml would drop a level."""

    def construct_mapping(self, node, deep=False):
        seen: set = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


def _load_yaml_unique_keys(path: Path):
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506 (SafeLoader subclass)
    except yaml.constructor.ConstructorError as e:
        raise SystemExit(f"{_rel(path)}: {e.problem}{e.problem_mark}")


def level_rank() -> dict[str, int]:
    """{level key: physical position}, 0 = lowest level."""
    return {lv["key"]: i for i, lv in enumerate(read_levels())}


def sort_floors(keys, rank: dict[str, int], what: str, *, top_first: bool = False) -> list[str]:
    """`keys` in physical order (bottom → top, or top → bottom). A key that
    isn't a level has no position, so it stops the build naming `what`
    rather than landing somewhere arbitrary."""
    unknown = sorted(set(keys) - rank.keys())
    if unknown:
        raise SystemExit(f"{what}: floor(s) {unknown} aren't levels in floors.yaml — "
                         "add them there (page: false for a level with no page of its own)")
    return sorted(set(keys), key=rank.__getitem__, reverse=top_first)


def default_floorplan_image(floor_key: str) -> str:
    # Each floor has its own floorplan image, named img/floors/floor_<floor_key>.png
    # (e.g. img/floors/floor_3rd.png, img/floors/floor_ground.png) — override by setting
    # `floorplan_image:` in YAML.
    return f"img/floors/floor_{floor_key}.png"


# ─── Meter registry ──────────────────────────────────────────────────────────
# The source of truth is site/data/meters.csv. read_meters() reads it
# directly; the build also writes it into the runtime's METER_REGISTRY block
# (write_js_blocks) for the browser — nothing reads that block back.

def read_meters() -> list[dict]:
    """meters.csv as a list of normalised meter dicts.

    Placement fields (column/zone/position/function/utility) only count for
    a meter placed on a floor: an unplaced meter gets the same empty
    defaults as a blank cell — matching METER_REGISTRY, which omits
    placement fields for meters with no `floor`.
    """
    csv_file = DATA_DIR / "meters.csv"
    if not csv_file.exists():
        return []

    out: list[dict] = []
    for row in generate_meter_registry.read_csv(csv_file, UTILITIES):
        placed = bool(row["floor"])
        out.append(
            {
                "id":        row["id"],
                "tag":       row["tag"],
                "base":      row["base"],
                "type":      row["type"],
                "parent_id": row["parent_id"],  # None if not in hierarchy
                "floor":     row["floor"],
                # A meter placed on more than one floor page (e.g. a riser
                # meter serving both) carries a "/"-separated floor list in
                # the CSV, e.g. floor: "3rd/4th" — split into a tuple so it
                # renders on every floor it names. Single-floor meters just
                # get a 1-tuple. Column/zone/position/function/utility are
                # shared across all of them (one placement per meter, not
                # one per floor).
                "floors":    tuple(f.strip() for f in row["floor"].split("/") if f.strip()),
                "column":    row["column"] if placed else None,      # None if not pinned
                "zone":      row["zone"] if placed else "",
                "position":  row["position"] if placed else None,    # None if not pinned
                "function":  row["function"] if placed else "",
                "utility":   row["utility"] if placed else "",
                # tenant is comma-separated; split into a tuple of names for
                # quick membership tests (`"metro" in m["tenants"]`).
                "tenants":   tuple(t.strip() for t in row["tenant"].split(",") if t.strip()),
                # Explicit opt-in gate for tenant pages (CSV "tenant_display"
                # column) — absent/false means the meter never appears on any
                # tenant page, regardless of its tenant tag.
                "tenant_display": row["tenant_display"],
                # Opt-OUT gate for main (non-tenant) floor pages (CSV
                # "main_display" column) — inverse polarity from
                # tenant_display: blank/yes (the default, matching every
                # meter that predates this column) means it shows on the
                # main floor page; only an explicit "no" hides it there.
                # Independent of tenant_display/tenant, so a meter can be
                # main-only, tenant-only, both, or neither.
                "main_display": row["main_display"],
            }
        )
    _check_registry_integrity(out)
    _check_meter_types(out)
    return out


def _check_meter_types(meters: list[dict]) -> None:
    """Every meter type needs a bacnet.power_offset in site.yaml — without
    one, neither the page generators nor the runtime can address the
    meter's demand point."""
    missing = sorted({m["type"] for m in meters} - BACNET["power_offset"].keys())
    if missing:
        raise SystemExit(
            f"{_rel(BUILDING_FILE)}: bacnet.power_offset has no entry for meter type(s) "
            f"{missing} used in meters.csv"
        )


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


def _read_data(filename: str, key: str, default):
    """Top-level `key` of site/data/<filename>; `default` if the file or key is absent."""
    path = DATA_DIR / filename
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get(key) or default


def read_reports() -> list[dict]:
    """Report placements (site/data/reports.yaml `placements:`).

    Each row carries the report's image_ref / library item id / alt plus
    placement fields (page/floor/tenant/incomer/slot/position) used to
    filter the rows for any given page.
    """
    return _read_data("reports.yaml", "placements", [])


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
    """Convert report placement rows to the dict shape the report_card macro expects."""
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
    """Load site.yaml (site/building facts). Empty dict if absent."""
    if not BUILDING_FILE.exists():
        return {}
    return yaml.safe_load(BUILDING_FILE.read_text(encoding="utf-8")) or {}


def read_points() -> dict[str, dict]:
    """Named non-meter BACnet points (site/data/points.yaml) → {name: {bacnet, format}},
    referenced from pages by `data-point="<name>"`."""
    return _read_data("points.yaml", "points", {})


def read_report_urls() -> set[str]:
    """The image_ref names that have a chart URL (site/data/reports.yaml `urls:`)."""
    return set(_read_data("reports.yaml", "urls", {}))


def read_bms_bindings() -> dict[tuple[str, str], dict]:
    """BMS bindings (site/data/bms_bindings.yaml) as a {(role, floor): row} map."""
    return {(row["role"], row["floor"]): row for row in _read_data("bms_bindings.yaml", "bindings", [])}


def derive_summary_cards(
    roles: tuple[str, ...],
    floor_key: str,
    bindings: dict[tuple[str, str], dict],
    leading: list[dict] | None = None,
) -> list[dict]:
    """Compose a summary_cards list for a tab from the role catalog + bindings.

    Each role emits one card. If a (role, floor) binding exists in bms_bindings.yaml,
    the card is live (id + bacnet + format). Otherwise a static "N/A" placeholder
    is emitted so the layout stays stable across floors.
    """
    cards: list[dict] = list(leading) if leading else []
    for role in roles:
        meta = SUMMARY_ROLES[role]
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
    for key, function in FLOOR_PAGE["summary_cards"].items():
        card = {"title": function, **FLOOR_SUMMARY_CARDS[key]}
        meter = find_floor_summary_meter(meters, floor_key, function, registry_names)
        if meter:
            card["meter_id"] = meter["id"]
        cards[f"{key}_card"] = card
    return cards


# Zone-card subtitle by the kinds of utility its meters carry, joined in
# UTILITY_KINDS order. site.yaml `floor_page.zone_subtitles` adds to or
# overrides these; a combination with no subtitle lists the utilities' labels.
DEFAULT_ZONE_SUBTITLES = {
    "electric":         "Electricity",
    "thermal":          "Heat Energy",
    "electric+thermal": "Electrical & Heat Energy",
}


def derive_zone_location(utilities: set[str]) -> str:
    """The card subtitle below the zone name (see DEFAULT_ZONE_SUBTITLES)."""
    codes = [code for code in UTILITIES if code in utilities]  # catalog order
    kinds = "+".join(k for k in UTILITY_KINDS if any(UTILITIES[c]["kind"] == k for c in codes))
    return FLOOR_PAGE["zone_subtitles"].get(kinds) or " & ".join(UTILITIES[c]["label"] for c in codes)


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
        # Site overrides first: site/templates/<name> replaces the engine's
        # _templates/<name> (e.g. a bespoke incomer_electricity.html.j2).
        loader=FileSystemLoader([str(SITE_ROOT / "templates"), str(TEMPLATES_DIR)]),
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
    env.globals["floor_page"] = FLOOR_PAGE
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
    return components.load_catalog(COMPONENTS_DIR, SITE_ROOT / "components")


def read_extras() -> list[dict]:
    return _read_data("extras.yaml", "extras", [])


def extras_pages() -> dict[str, str]:
    """{page key: page kind} for every page an extra can name: the floor
    pages, the incomer pages and home."""
    pages = {lv["page_key"]: "floor" for lv in read_levels() if lv["page"]}
    pages |= {str(key): "incomer" for key in (_read_yaml(DATA_DIR / "incomers.yaml") or {})}
    pages["home"] = "home"
    return pages


@pass_context
def render_fragment(ctx, name: str) -> str:
    """site/pages/<name>, rendered like a frozen page's fragment ({{ path_prefix }},
    {{ building.* }}) — the `html` component's body."""
    path = SITE_ROOT / "pages" / str(name)
    if not path.is_file():
        raise SystemExit(f"extras: fragment {_rel(path)} not found")
    return ctx.environment.from_string(path.read_text(encoding="utf-8")).render(
        path_prefix=ctx.get("path_prefix") or "").strip("\n")


def build_floors(env: Environment, only: str | None = None) -> list[Path]:
    floors_file = DATA_DIR / "floors.yaml"
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
        ctx.setdefault("tabs", [{"id": "floorplan", "label": FLOOR_PAGE["summary_label"]}]
                       + [{"id": t["id"], "label": t["label"]} for t in FLOOR_PAGE["tabs"]])

        # Floorplan tab: derive layout + summary_cards unless YAML supplies them.
        fp_tab = dict(ctx.get("floorplan_tab") or {})
        if "layout" not in fp_tab:
            image = relative_url(fp_tab.get("floorplan_image") or default_floorplan_image(floor_key), folder)
            after_col = fp_tab.get("floorplan_after_column", 0)
            fp_tab.setdefault("image", image)
            fp_tab["layout"] = derive_layout(main_meters, floor_key, image, after_col)
            if not fp_tab["layout"]:
                raise SystemExit(
                    f"{key}: no meters pinned to floor={floor_key!r} in meters.csv "
                    f"and no `layout:` in YAML — cannot render."
                )
        if "image" in fp_tab:
            fp_tab["image"] = relative_url(fp_tab["image"], folder)
        for card_key, card in derive_floor_summary_cards(main_meters, floor_key).items():
            fp_tab.setdefault(card_key, card)
        ctx["floorplan_tab"] = fp_tab

        # Report tabs (floor_page.tabs): each tab's summary cards from its
        # roles, then the floor's report placements for its slot, titled by
        # position (floor_page.report_titles, e.g. Demand then Consumption).
        # A floor without data for a slot gets "N/A" cards and no reports,
        # same as any other not-yet-wired role.
        titles = FLOOR_PAGE["report_titles"]
        report_tabs = []
        for tab in FLOOR_PAGE["tabs"]:
            cards = reports_to_cards(reports_for(reports, page="floor", floor=floor_key, slot=tab["slot"]))
            if titles:
                for i, card in enumerate(cards):
                    card.setdefault("title", titles[i] if i < len(titles) else f"Report {i + 1}")
            report_tabs.append({
                "id":            tab["id"],
                "label":         tab["label"],
                "summary_cards": derive_summary_cards(tab["roles"], floor_key, bindings),
                "reports":       cards,
            })
        ctx["report_tabs"] = report_tabs

        html = template.render(**ctx)
        out_path = out_dir / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")

    return written


def build_incomers(env: Environment, only: str | None = None) -> list[Path]:
    """Render incomer pages from site/data/incomers.yaml. The engine's
    incomer.html.j2 supports the simple form (summary cards + reports) and
    the rich form (+ stat_grids + headed report). An entry may name a
    different template with `template:` — e.g. a site override in
    site/templates/ for a bespoke layout."""
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
        # Placement/menu fields, not page data — and `building` would shadow
        # the template's `building` global.
        out_dir, location_ctx = page_location(check_building(ctx.pop("building", None), f"incomers.yaml '{key}'"))
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
        html = env.get_template(tmpl_name).render(**ctx)
        out_path = out_dir / f"{key}.htm"
        out_path.write_text(html, encoding="utf-8", newline="\n")
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
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
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
    tenants_file = DATA_DIR / "tenants.yaml"
    if not tenants_file.exists():
        print(f"  (skip tenants: {tenants_file} not found)")
        return []
    tenants = yaml.safe_load(tenants_file.read_text(encoding="utf-8")) or {}

    meters = read_meters()
    reports = read_reports()
    bindings = read_bms_bindings()
    levels = {lv["key"]: lv for lv in read_levels()}
    rank = level_rank()
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
        # actually wired up. Ordered top floor first, going down — the
        # floors.yaml roster order reversed, matching the main sidebar's
        # floor order (_auto_floors).
        tenant_meters = [m for m in meters if any(n in m["tenants"] for n in registry_names)]
        floor_keys = {f for m in tenant_meters for f in m["floors"]} | {str(f) for f in data.get("extra_floors") or []}
        floor_keys -= {str(f) for f in data.get("exclude_floors") or []}
        floors_occupied = sort_floors(floor_keys, rank, f"tenants.yaml '{slug}'", top_first=True)
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
                "path_prefix":   TENANT_PATH_PREFIX,
                "sidebar_src":   "sidebar-template.js",
            }
            html = index_template.render(**ctx)
            out_path = tenant_dir / "index.htm"
            out_path.write_text(html, encoding="utf-8", newline="\n")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(OUT_ROOT)}")

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
            # tenant's own tenant_display'd override meter (e.g. a
            # "<Tenant> Level NN Electricity" meter) rather than falling back to
            # the shared generic row — see find_floor_summary_meter. A role
            # with no override for this tenant renders "N/A".
            floorplan_tab = {"layout": layout, "image": image}
            for card_key, card in derive_floor_summary_cards(meters, floor_key, registry_names).items():
                floorplan_tab[card_key] = card

            # Report tabs: tenant_page.tabs (a subset of floor_page.tabs) — a
            # tenant without registry/YAML data for a slot just gets an empty
            # reports list, same as any not-yet-wired floor. Tenant pages
            # don't title their report cards.
            tabs = [{"id": "floorplan", "label": floor_data.get("floorplan_tab_label", TENANT_PAGE["summary_label"])}]
            report_tabs = []
            for tab in TENANT_PAGE["tabs"]:
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
                "path_prefix":     TENANT_PATH_PREFIX,
                "sidebar_src":     "sidebar-template.js",
                "report_tabs":     report_tabs,
            }

            html = floor_template.render(**ctx)
            out_path = tenant_dir / f"floor_{floor_key}.htm"
            out_path.write_text(html, encoding="utf-8", newline="\n")
            written.append(out_path)
            print(f"  wrote {out_path.relative_to(OUT_ROOT)}")

        # ── tenant sidebar-template.js ──
        floor_links = [
            {"href": f"floor_{f}.htm", "label": levels[f]["label"]}
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
        out_path.write_text(sidebar_js, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(OUT_ROOT)}")

    return written


def build_schematics(env: Environment, only: str | None = None) -> list[Path]:
    """Render riser_*.htm + tariff_*.htm from site/data/schematics.yaml.

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
        out_path.write_text(html, encoding="utf-8", newline="\n")
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")
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
    incomers_file = DATA_DIR / "incomers.yaml"
    if not incomers_file.exists():
        return []
    data = yaml.safe_load(incomers_file.read_text(encoding="utf-8")) or {}
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
            "label":     entry.get("nav_label") or (UTILITIES[slug]["label"] if slug in UTILITIES else slug.capitalize()),
            "href":      site_href(building, f"{page_key}.htm"),
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


def _auto_buildings(auto_lists: dict, icon: str | None) -> list[dict]:
    """One sub-menu per site.yaml building: its floors (top first), then its
    incomers and switchboards."""
    items: list[dict] = []
    for b in BUILDINGS:
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
    """Tenant menu-items in tenants.yaml order; href varies by whether the
    tenant has an index page or only a single floor view."""
    t_file = DATA_DIR / "tenants.yaml"
    if not t_file.exists():
        return []
    tenants = yaml.safe_load(t_file.read_text(encoding="utf-8")) or {}
    rank = level_rank()
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
        floors_occupied = sort_floors({f for m in tenant_meters for f in m["floors"]}, rank,
                                      f"tenants.yaml '{slug}'")
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


# The sidebar runtime (below the SIDEBAR_HTML markers) loads sidebar.js by a
# page-relative URL; a building folder's copy points it up a level.
SIDEBAR_RUNTIME_SCRIPT = 'script.src = "js/project/2.0/sidebar.js";'


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
        "tenants":      _auto_tenants(meters),
    }

    # Expand auto: markers inside top/sections/bottom item lists
    cfg["top_items"] = _expand_auto(cfg.get("top_items") or [], auto_lists)
    cfg["bottom_items"] = _expand_auto(cfg.get("bottom_items") or [], auto_lists)
    for section in cfg.get("sections", []):
        section["items"] = _expand_auto(section.get("items", []), auto_lists)

    template = env.get_template("sidebar.js.j2")
    jsblocks.inject(SIDEBAR_JS, jsblocks.SIDEBAR_HTML, template.render(**cfg, rel=lambda url: url))
    print(f"  wrote {SIDEBAR_JS.relative_to(SITE_DIR)}")
    written = [SIDEBAR_JS]

    # Campus: each building folder's pages load <folder>/sidebar-template.js
    # (page_location's sidebar_src) — the same file with every link and the
    # runtime's own sidebar.js URL rewritten for that folder.
    if CAMPUS:
        root_js = SIDEBAR_JS.read_text(encoding="utf-8")
        if root_js.count(SIDEBAR_RUNTIME_SCRIPT) != 1:
            raise SystemExit(f"{SIDEBAR_JS}: expected the runtime line {SIDEBAR_RUNTIME_SCRIPT!r} once — "
                             "update SIDEBAR_RUNTIME_SCRIPT in build.py to match the skeleton")
        for b in BUILDINGS:
            folder = b["key"]
            out = SITE_DIR / folder / "sidebar-template.js"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(root_js.replace(SIDEBAR_RUNTIME_SCRIPT, SIDEBAR_RUNTIME_SCRIPT.replace(
                '"js/', f'"{relative_url("js/", folder)}')), encoding="utf-8", newline="\n")
            jsblocks.inject(out, jsblocks.SIDEBAR_HTML,
                            template.render(**cfg, rel=lambda url, f=folder: relative_url(url, f)))
            print(f"  wrote {out.relative_to(SITE_DIR)}")
            written.append(out)
    return written


def build_home(env: Environment, only: str | None = None) -> list[Path]:
    """Render the home landing page from site/data/home.yaml (singleton)."""
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
    ctx["page_kind"], ctx["page_key"] = "home", "home"

    reports = read_reports()
    if "top_reports" not in ctx:
        ctx["top_reports"] = reports_to_cards(reports_for(reports, page="home", slot="top"))
    if "reports" not in ctx:
        ctx["reports"] = reports_to_cards(reports_for(reports, page="home", slot="main"))

    template = env.get_template("home.html.j2")
    html = template.render(**ctx)
    out_path = SITE_DIR / "home.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
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
    html = template.render(**ctx)
    out_path = SITE_DIR / "energy_flow.htm"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def build_dials(env: Environment, only: str | None = None) -> list[Path]:
    """Render the live KPI dials page from site/data/dials.yaml (singleton).

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
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def build_pages(env: Environment, only: str | None = None) -> list[Path]:
    """Render one-off singleton pages (site/data/pages.yaml) through the base shell.

    These are pages not driven by a data registry (landlord services,
    documents, a report viewer, …). Their bespoke body and any head/script extras live as
    raw HTML fragments in site/pages/<key>.{body,styles,extra_scripts,
    tail_scripts}.html (extracted once from the original hand-written pages,
    then hand maintained); pages.yaml carries only per-page metadata.
    """
    pages_file = DATA_DIR / "pages.yaml"
    if not pages_file.exists():
        print(f"  (skip pages: {pages_file} not found)")
        return []

    data = yaml.safe_load(pages_file.read_text(encoding="utf-8")) or {}
    pages_dir = SITE_ROOT / "pages"
    template = env.get_template("page.html.j2")
    written: list[Path] = []
    for page in data.get("pages", []):
        key = page["key"]
        if only and only != key:
            continue
        ctx = dict(page)
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
        out_path.write_text(template.render(**ctx), encoding="utf-8", newline="\n")
        print(f"  wrote {out_path.relative_to(SITE_DIR)}")
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
    out_path = SITE_DIR / "building_performance.htm"
    out_path.write_text(template.render(**ctx), encoding="utf-8", newline="\n")
    print(f"  wrote {out_path.relative_to(SITE_DIR)}")
    return [out_path]


def _read_yaml(path: Path):
    """A YAML file's contents, or None if it doesn't exist."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def _building_page_files(building: str) -> set[str]:
    """The filenames the build writes into a campus building's folder (its
    floor, incomer, switchboard and pages.yaml pages, and its sidebar)."""
    files = {f"{lv['page_key']}.htm" for lv in read_levels() if lv["page"] and lv["building"] == building}
    files |= {f"{key}.htm" for key, e in (_read_yaml(DATA_DIR / "incomers.yaml") or {}).items()
              if (e or {}).get("building") == building}
    files |= {f"{key}.htm" for key, b in ((_read_yaml(DATA_DIR / "switchboards.yaml") or {}).get("boards") or {}).items()
              if (b or {}).get("building") == building}
    files |= {pg["out"] for pg in (_read_yaml(DATA_DIR / "pages.yaml") or {}).get("pages") or []
              if pg.get("building") == building}
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
    site_templates = SITE_ROOT / "templates"
    overrides = sorted(
        p.relative_to(site_templates).as_posix()
        for p in site_templates.rglob("*.j2")
        if (TEMPLATES_DIR / p.relative_to(site_templates)).exists()
    )
    if overrides:
        print(f"Site template overrides (replace the engine's copy): {', '.join(overrides)}")
    site_components = sorted(c for c in read_component_catalog() if (COMPONENTS_DIR / c).is_dir()
                             and (SITE_ROOT / "components" / c).is_dir())
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
        problems.append(f"meters.csv: floor '{floor}' (meter ids {ids[:8]}{' …' if len(ids) > 8 else ''}) "
                        "isn't a level in floors.yaml (typo? or add it, page: false if it has no page)")
    unknown_floors("bms_bindings.yaml", (f for _role, f in read_bms_bindings()))
    unknown_floors("reports.yaml placements", (r["floor"] for r in reports if "floor" in r))
    for slug, t in (_read_yaml(DATA_DIR / "tenants.yaml") or {}).items():
        t = t or {}
        unknown_floors(f"tenants.yaml '{slug}'",
                       [*(t.get("extra_floors") or []), *(t.get("exclude_floors") or []), *(t.get("floors") or {})])
    unknown_floors("energy_flow.yaml floors", (fl["key"] for fl in (_read_yaml(DATA_DIR / "energy_flow.yaml") or {}).get("floors") or []))
    sidebar = _read_yaml(DATA_DIR / "sidebar.yaml") or {}
    for items in [sidebar.get("top_items"), sidebar.get("bottom_items"),
                  *(sec.get("items") for sec in sidebar.get("sections") or [])]:
        unknown_floors("sidebar.yaml floor groups", _floor_group_keys(items or []))

    # 6. Every meter's utility must be in the site's catalog — otherwise it
    # gets no zone subtitle and no styling (an unmatched cell is passed
    # through as-is by meters.csv normalisation, so it shows up here).
    for code in sorted({base_utility(m["utility"]) for m in meters if m["utility"]} - UTILITIES.keys()):
        ids = [m["id"] for m in meters if base_utility(m["utility"]) == code]
        problems.append(f"meters.csv: utility '{code}' (meter ids {ids[:8]}{' …' if len(ids) > 8 else ''}) "
                        f"isn't in site.yaml `utilities:` (known: {', '.join(UTILITIES)})")

    # 8. Every `building:` an incomer, page or switchboard names must be a
    # site.yaml building (levels are checked as floors.yaml is read).
    placed = [("incomers.yaml", key, entry) for key, entry in (_read_yaml(DATA_DIR / "incomers.yaml") or {}).items()]
    placed += [("pages.yaml", pg.get("key"), pg) for pg in (_read_yaml(DATA_DIR / "pages.yaml") or {}).get("pages") or []]
    placed += [("switchboards.yaml", key, board)
               for key, board in ((_read_yaml(DATA_DIR / "switchboards.yaml") or {}).get("boards") or {}).items()]
    for source, key, entry in placed:
        try:
            check_building((entry or {}).get("building"), f"{source} '{key}'")
        except SystemExit as e:
            problems.append(str(e))

    # Warnings — data that's harmless but does nothing (not counted as errors).
    warnings: list[str] = []

    # 9. Every extras.yaml placement must name a known component, page and
    # slot, and give the component's required options (and no unknown ones).
    placements = components.resolve(read_extras(), read_component_catalog(), extras_pages(), problems, warnings)
    # A frozen page in a campus building's folder must write its relative
    # URLs as {{ path_prefix }}… — a bare "img/x.png" or "home.htm" would
    # resolve inside the folder and 404. A bare link to another page of the
    # same building (same folder) is fine.
    bare_url = re.compile(r'(?:src|href)="(?!\{\{|/|#|\.\./|[a-z]+:)([^"?#]+)')
    for pg in (_read_yaml(DATA_DIR / "pages.yaml") or {}).get("pages") or []:
        if page_folder(pg.get("building")):
            neighbours = _building_page_files(pg["building"])
            for frag in sorted((SITE_ROOT / "pages").glob(f"{pg['key']}.*.html")):
                for url in sorted(set(bare_url.findall(frag.read_text(encoding="utf-8"))) - neighbours):
                    warnings.append(f"{_rel(frag)}: '{url}' resolves inside the {pg['building']}/ folder — "
                                    "write it as {{ path_prefix }}" + url)
    # Each utility's meters are styled by a .meter-<code> CSS rule.
    css = "".join(p.read_text(encoding="utf-8", errors="replace")
                  for root in (ASSETS_DIR / "css", SITE_ROOT / "assets" / "css") if root.exists()
                  for p in root.rglob("*.css"))
    if ".meter-" in css:
        for code in UTILITIES:
            if f".meter-{code}" not in css:
                warnings.append(f"site.yaml utility '{code}' has no .meter-{code} CSS rule — its meters will be unstyled")
    else:
        print("  (no project CSS with .meter-* rules found — skipping the utility CSS check)")
    # 7. Bindings for a role no page shows (e.g. the floor_demand_* rows,
    # left over from a Summary-tab card set the floor template never rendered).
    shown = {role for tab in FLOOR_PAGE["tabs"] for role in tab["roles"]}
    unused: dict[str, int] = defaultdict(int)
    for role, _floor in read_bms_bindings():
        if role not in shown:
            unused[role] += 1
    for role, n in sorted(unused.items()):
        warnings.append(f"bms_bindings.yaml: role '{role}' ({n} row(s)) isn't shown on any page")

    if problems:
        warnings.append("skipped the build checks (rendered data-point/meter ids, missing assets and links) "
                        "until the problems below are fixed")
    else:
        check_build(resolve_modules(None) if modules is None else modules,
                    set(points), meter_ids, problems, warnings, placements)

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
                problems: list[str], warnings: list[str], placements: list[dict] = ()) -> None:
    """Build the site into a throwaway output root and check what it
    renders (linkcheck.py): a data-point or meter id naming nothing is a
    problem; a file a page references that the build doesn't produce (an
    asset not yet in _assets/ or site/assets/, a page no module writes,
    another site's /docs/ URL) is a warning, and so is an extras placement
    no built page rendered. The real output root is never touched."""
    out_root = OUT_ROOT
    with tempfile.TemporaryDirectory(prefix="build-check-") as tmp:
        try:
            configure(SITE_ROOT, Path(tmp) / "project")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build_site(modules)
            except SystemExit as e:
                problems.append(f"the build fails: {e}")
                return
            except Exception as e:
                problems.append(f"the build fails: {type(e).__name__}: {e}")
                return
            problems.extend(linkcheck.unknown_names(OUT_ROOT, SITE_DIR, points, meter_ids))
            warnings.extend(linkcheck.missing_references(OUT_ROOT, SITE_DIR))
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
            configure(SITE_ROOT, out_root)


# ─── Modules ─────────────────────────────────────────────────────────────────
# Every page family the engine can build, in build order. A site enables the
# ones it uses in site.yaml `modules:` (--modules overrides that for one run).
# Each builder takes (env, only) and returns the paths it wrote. sidebar runs
# last; it only rewrites the staged sidebar-template.js.
def _switchboards(env: Environment, only: str | None = None) -> list[Path]:
    import build_switchboards  # imported lazily: it imports this module back
    return build_switchboards.run(env, only)


def _risers(env: Environment, only: str | None = None) -> list[Path]:
    import build_risers  # imported lazily: it imports this module back
    return build_risers.run(env, only)


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
    "switchboards":         _switchboards,
    "risers":               _risers,
    "sidebar":              build_sidebar,
}


def resolve_modules(spec: str | None) -> list[str]:
    """The modules to run, in MODULES order: from --modules ("all", or a
    comma-separated list) if given, else site.yaml `modules:`."""
    if spec is None:
        source = f"{_rel(BUILDING_FILE)} `modules:`"
        names = read_building().get("modules")
        if not names:
            raise SystemExit(f"{_rel(BUILDING_FILE)}: `modules:` is required — the page families to build, "
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
    if not only or not (OUT_ROOT / OUTPUT_MARKER).exists():
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
                    "disable one of them (site.yaml `modules:`) or drop the duplicate page"
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
        help=f"Comma-separated modules to build instead of site.yaml `modules:`, or 'all'. "
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
    # Run main() on the importable `build` module rather than on this
    # __main__ copy, so the builders that `import build` back
    # (build_switchboards, build_risers) share its configure()d paths.
    import build

    sys.exit(build.main(sys.argv[1:]))
