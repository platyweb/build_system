#!/usr/bin/env python
"""
The site being built. configure() points the engine at one site directory
and output root; the readers here turn its data files into what the page
builders use: site.yaml's settings, the utilities, buildings and level
roster, tenants, meters, BMS points and reports. page_location() says where
a page goes, and render_page() renders one.

build.py and the module files (build_switchboards.py, build_risers.py)
import this module, never each other's state, so they share one configured
site however build.py is run. Nothing here imports build.py. The paths and
settings below exist once configure() has run.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import Template

import generate_meter_registry
import meters_yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE_ROOT = ROOT / "site"
DEFAULT_OUT_ROOT = ROOT / "project"

# ─── Site + output paths ─────────────────────────────────────────────────────
# Everything specific to one building lives under its site directory
# (default site/):
#   data/       the numbered data files, starting with 00_site.yaml: site/
#               building identity (the `building` template global). An older
#               site keeps its site.yaml at the site root.
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
BUILDING_FILE: Path        # site/data/00_site.yaml
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
    BUILDING_FILE = site_file(SITE_ROOT)
    if BUILDING_FILE is None:
        raise SystemExit(f"{SITE_ROOT}/data/00_site.yaml not found — is {SITE_ROOT} a site directory? "
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


def _rel(path: Path) -> str:
    """`path` relative to the repo root for messages, absolute if outside it."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ─── Data files ──────────────────────────────────────────────────────────────
# A site's data/ files, in the order they're filled in for a new building.
# A file may carry its number — its place in this list, data/02_floors.yaml —
# so a directory listing shows that order; the build finds it either way.
# Only site.yaml and the files the site's modules read are needed.
DATA_FILES = (
    "site.yaml",              # identity, modules, BACnet addressing, utilities, page config
    "pages.yaml",             # every page the site builds, laid out as its menu
    "floors.yaml",            # levels bottom → top, the tenant holding each level's cores
    "meters.yaml",            # every meter, by level → core (or meters.csv)
    "points.yaml",            # every BMS point the pages show: named, floor cards, incomer + home pages
    "tenants.yaml",           # the tenant catalog: proper names, slugs, tenant pages
    "incomers.yaml",          # older sites: points.yaml `incomers:`
    "home.yaml",              # older sites: points.yaml `home:`
    "meters_hierarchy.yaml",  # optional: the hierarchy page's texts and roots
    "switchboards.yaml",
    "risers.yaml",
    "schematics.yaml",
    "energy_flow.yaml",
    "dials.yaml",
    "reports.yaml",           # report cards placed on the pages above
    "extras.yaml",            # components placed on the pages above
    "sidebar.yaml",           # older sites: the menu, before it moved into pages.yaml
)
# Also read: meters.csv, the meters as an export, in place of meters.yaml;
# and an older site's bms_bindings.yaml (now points.yaml `floors:`).
LEGACY_DATA_FILES = ("meters.csv", "bms_bindings.yaml")


def data_path(name: str, data_dir: Path | None = None) -> Path:
    """data/<name>, or its numbered form data/<NN>_<name> — whichever the
    site has (the plain path if neither exists). Both is an error."""
    data_dir = data_dir or DATA_DIR
    found = [p for p in sorted(data_dir.glob(f"*_{name}")) if re.fullmatch(rf"\d+_{re.escape(name)}", p.name)]
    if (data_dir / name).exists():
        found.append(data_dir / name)
    if len(found) > 1:
        raise SystemExit(f"{_rel(data_dir)}: {', '.join(p.name for p in found)} are all {name} — keep one")
    return found[0] if found else data_dir / name


def site_file(site_root: Path) -> Path | None:
    """A site directory's site.yaml — data/00_site.yaml, or site.yaml at the
    root on a site that predates the move — or None: not a site directory."""
    in_data, at_root = data_path("site.yaml", Path(site_root) / "data"), Path(site_root) / "site.yaml"
    if in_data.exists() and at_root.exists():
        raise SystemExit(f"{_rel(Path(site_root))}: both data/{in_data.name} and site.yaml — keep data/{in_data.name}")
    return in_data if in_data.exists() else at_root if at_root.exists() else None


def _read_yaml(path: Path):
    """A YAML file's contents, or None if it doesn't exist."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


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
# format}; a card's live point comes from points.yaml `floors:` by (role,
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

# Floor page layout: key → its choices, the first being the default (the
# page as it always was). site.yaml `floor_page:` sets them for the site, and
# a floors.yaml level for its own floor and tenant pages.
#   floorplan      : the floorplan image beside the summary cards, above
#                    them, or none
#   meter_columns  : the riser grid's columns; auto = as many as the page's
#                    cards use (meters' `column`), at most MAX_METER_COLUMNS
#   summary_layout : split = the total card, then tenants + landlords below;
#                    row = every summary card in one row
FLOOR_LAYOUT: dict[str, tuple] = {
    "floorplan":      ("right", "top", "none"),
    "meter_columns":  (3, 1, 2, 4, "auto"),
    "summary_layout": ("split", "row"),
}
MAX_METER_COLUMNS = 4


def read_floor_layout(spec: dict, where: str) -> dict:
    """The FLOOR_LAYOUT keys `spec` sets, each checked against its choices."""
    out: dict = {}
    for key, choices in FLOOR_LAYOUT.items():
        if key not in spec:
            continue
        value = spec[key]
        if isinstance(value, bool) or value not in choices:   # True == 1 in Python
            raise SystemExit(f"{where}: `{key}: {value}` isn't one of: {', '.join(map(str, choices))}")
        out[key] = value
    return out


# Zone-card subtitle by the kinds of utility its meters carry, joined in
# UTILITY_KINDS order. site.yaml `floor_page.zone_subtitles` adds to or
# overrides these; a combination with no subtitle lists the utilities' labels.
DEFAULT_ZONE_SUBTITLES = {
    "electric":         "Electricity",
    "thermal":          "Heat Energy",
    "electric+thermal": "Electrical & Heat Energy",
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
        "layout":          {key: choices[0] for key, choices in FLOOR_LAYOUT.items()}
                           | read_floor_layout(fp, f"{where} floor_page"),
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


def render_page(template: Template, ctx: dict) -> str:
    """`template` rendered with a page's context. Every page gets
    `path_prefix` ("" at the site root; page_location() gives a building
    folder's), so a template can write {{ path_prefix }}… without a default.
    A context key named like a template global (`building`, `floor_page`,
    `slot`, …) would hide that global on the page, so it stops the build:
    a builder pops placement fields such as `building` before rendering."""
    clash = sorted(ctx.keys() & template.environment.globals.keys())
    if clash:
        raise SystemExit(f"{template.name}: the page's data has {', '.join(clash)}, which would hide the "
                         "template global of that name — rename the field, or pop it before rendering")
    return template.render({"path_prefix": "", **ctx})


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
#   cores     : {<core>: <tenant short name>} — which tenant holds each of
#               the level's cores (see read_tenants). An unlisted core is
#               the landlord's. Checked by --check only; no page shows it yet
#   floorplan, meter_columns, summary_layout : this level's pages' layout
#               (FLOOR_LAYOUT)                       — default: site.yaml floor_page's
# Any other field is page data for build_floors (floorplan_tab, tabs, …).
#   building  : the building it belongs to (site.yaml `buildings:` key) —
#               required on a campus, where it picks the page's subfolder
LEVEL_FIELDS = ("label", "nav_label", "heading", "page", "building", "cores", *FLOOR_LAYOUT)

# The tenant catalog's key: the whole of tenants.yaml, or (on a site from
# before it had its own file) floors.yaml's one top-level key that isn't a level.
TENANTS_KEY = "tenants"


def read_levels() -> list[dict]:
    """The level roster, bottom → top. Each level is
    {key, page_key, label, nav_label, heading, page, building, cores, layout,
    data} — `layout` holds the FLOOR_LAYOUT keys the level sets, `data` its
    non-roster fields (the floor page's own overrides)."""
    floors_file = data_path("floors.yaml")
    if not floors_file.exists():
        return []
    levels: list[dict] = []
    for page_key, entry in (_load_yaml_unique_keys(floors_file) or {}).items():
        page_key = str(page_key)
        if page_key == TENANTS_KEY:
            continue
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
            "cores":     _read_cores(entry.get("cores"), f"{_rel(floors_file)} '{page_key}'"),
            "layout":    read_floor_layout(entry, f"{_rel(floors_file)} '{page_key}'"),
            "data":      {k: v for k, v in entry.items() if k not in LEVEL_FIELDS},
        })
    return levels


def _read_cores(cores, where: str) -> dict[str, str]:
    """A level's `cores:` as {core: tenant short name}. Each listed core
    names exactly one tenant; whether that tenant exists is --check's job."""
    if cores is None:
        return {}
    if not isinstance(cores, dict):
        raise SystemExit(f"{where}: `cores:` must map each core to a tenant's short name, "
                         "e.g. cores: {East: <tenant>, West: <tenant>}")
    out: dict[str, str] = {}
    for core, tenant in cores.items():
        if tenant is None or isinstance(tenant, (list, dict)) or not str(tenant).strip():
            raise SystemExit(f"{where}: core '{core}' must name one tenant's short name "
                             "(leave a landlord core out)")
        out[str(core)] = str(tenant).strip()
    return out


# ─── Tenants ─────────────────────────────────────────────────────────────────
# floors.yaml's `tenants:` block is the site's tenant catalog, keyed by each
# tenant's SHORT NAME: the spelling meters.csv's `tenant` column uses and a
# level's `cores:` refers to. Catalog order is the sidebar's tenant order.
#
# Tenant fields (all optional):
#   name           : proper name, shown on the tenant pages and sidebar
#                                                  — default: the short name
#   slug           : output folder, project/tenants/<slug>/
#                    — default: the short name lower-cased, each run of other
#                      characters a "-" ("Acme & Co" → acme-co)
#   index          : {} (or {page_title, title, reports}) adds index.htm
#   extra_floors   : [<key>, …] floors with no meters tagged to the tenant
#                    yet, given a page anyway
#   exclude_floors : [<key>, …] floors a tagged meter would add, dropped
#   floors         : {<key>: {heading, page_title, floorplan_tab_label,
#                    floorplan_image, floorplan_after_column, <slot>_reports}}
#
# A site from before the catalog keeps data/tenants.yaml instead: keyed by
# slug, with `display_name` (proper name, default the slug capitalised) and
# `registry_tenant` (short name, or a list of them; default the slug).
# read_tenants() reads either into one shape; a site may not have both.
TENANT_FIELDS = ("name", "slug", "index", "extra_floors", "exclude_floors", "floors", "docs")


def tenant_slug(short_name: str) -> str:
    """The default output folder for a tenant: its short name lower-cased,
    each run of anything but a-z/0-9 a "-"."""
    return re.sub(r"[^a-z0-9]+", "-", short_name.lower()).strip("-")


def read_tenants() -> list[dict]:
    """The site's tenants in file order, each
    {slug, name, short_names, where, docs, data}: `short_names` are the
    meters' `tenant` spellings that tag its meters, `where` names it in
    messages, `docs` is its menu's Docs link (tenant_docs_href; None for no
    Docs item), and `data` holds index / extra_floors / exclude_floors / floors.

    The catalog is tenants.yaml `tenants:`, keyed by short name. Also read:
    a floors.yaml `tenants:` catalog (before it had its own file), and an
    older site's tenants.yaml keyed by slug (display_name, registry_tenant)."""
    floors_file = data_path("floors.yaml")
    tenants_file = data_path("tenants.yaml")
    in_floors = (_load_yaml_unique_keys(floors_file) or {}).get(TENANTS_KEY) if floors_file.exists() else None
    file_data = (_load_yaml_unique_keys(tenants_file) or {}) if tenants_file.exists() else None
    if isinstance(file_data, dict) and TENANTS_KEY in file_data:
        if set(file_data) != {TENANTS_KEY}:
            raise SystemExit(f"{_rel(tenants_file)}: unknown key(s) {sorted(set(file_data) - {TENANTS_KEY})} — "
                             f"the catalog is `{TENANTS_KEY}:` alone")
        catalog, catalog_file, legacy = file_data[TENANTS_KEY] or {}, tenants_file, None
        if in_floors is not None:
            raise SystemExit(f"{_rel(floors_file)}: `{TENANTS_KEY}:` is in {_rel(tenants_file)} now — "
                             "move any entries still here across and delete the block")
    else:
        catalog, catalog_file, legacy = in_floors, floors_file, file_data
        if in_floors is not None and legacy is not None:
            raise SystemExit(f"{_rel(tenants_file)}: tenants are in floors.yaml `{TENANTS_KEY}:` now — "
                             "move any entries still here across and delete this file")

    tenants: list[dict] = []
    if catalog is not None:
        if not isinstance(catalog, dict):
            raise SystemExit(f"{_rel(catalog_file)}: `{TENANTS_KEY}:` must map each tenant's short name to its fields")
        for short, raw in catalog.items():
            short = str(short)
            where = f"{_rel(catalog_file)} tenant '{short}'"
            data = dict(raw or {})
            unknown = sorted(set(data) - set(TENANT_FIELDS))
            if unknown:
                raise SystemExit(f"{where}: unknown field(s) {unknown} (known: {', '.join(TENANT_FIELDS)}; "
                                 "the key is the short name, `name` the proper name)")
            slug = str(data.pop("slug", None) or tenant_slug(short))
            name = str(data.pop("name", None) or short)
            tenants.append({"slug": slug, "name": name, "short_names": [short], "where": where, "data": data})
    elif legacy is not None:
        for slug, raw in legacy.items():
            slug = str(slug)
            data = dict(raw or {})
            registry_tenant = data.pop("registry_tenant", slug)
            tenants.append({
                "slug":        slug,
                "name":        data.pop("display_name", slug.capitalize()),
                "short_names": [registry_tenant] if isinstance(registry_tenant, str) else list(registry_tenant),
                "where":       f"tenants.yaml '{slug}'",
                "data":        data,
            })

    seen: dict[str, str] = {}
    for t in tenants:
        if not t["slug"] or "/" in t["slug"] or t["slug"] in (".", ".."):
            raise SystemExit(f"{t['where']}: slug '{t['slug']}' can't be a folder name — set `slug:`")
        if t["slug"] in seen:
            raise SystemExit(f"{t['where']}: slug '{t['slug']}' is also {seen[t['slug']]}'s — "
                             "give one of them its own `slug:`")
        seen[t["slug"]] = t["where"]
        if "docs" in t["data"] and t["data"]["docs"] is None:
            raise SystemExit(f"{t['where']}: `docs:` is empty — write false for no Docs item, "
                             "or leave it out for the default link")
        t["docs"] = tenant_docs_href(t["where"], t["slug"], t["data"].pop("docs", None))
    return tenants


def tenant_docs_href(where: str, slug: str, docs: str | bool | None) -> str | None:
    """A tenant menu's Docs link, from tenants.yaml `docs:`, as the tenant's
    pages (project/tenants/<slug>/) write it:
    - unset: docs/<slug>-submetering.pdf in the tenant's own folder, which
      the build has no way to fill — the link every older site has;
    - false: no Docs item;
    - a URL (https://…) or a path on the controller (/docs/…): as written;
    - a path, e.g. docs/fern-co.pdf: a file the site ships in its assets/,
      so the link climbs to the site folder (TENANT_PATH_PREFIX)."""
    if docs is None:
        return f"docs/{slug}-submetering.pdf"
    if docs is False:
        return None
    if not isinstance(docs, str) or not docs.strip():
        raise SystemExit(f"{where}: `docs:` is a file in the site's assets/ (docs/<name>.pdf), "
                         f"a URL, or false for no Docs item — not {docs!r}")
    if docs.startswith("/") or "://" in docs:
        return docs
    return TENANT_PATH_PREFIX + docs


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
# The source of truth is the site's meters file: data/meters.yaml, laid out
# level → core → meter (meters_yaml.py), or an older site's data/meters.csv.
# read_meters() reads it directly; the build also writes it into the
# runtime's METER_REGISTRY block (write_js_blocks) for the browser — nothing
# reads that block back.

def meters_file() -> Path:
    """The site's meters: data/meters.yaml (level → core → meter), or
    data/meters.csv, an export read as it is. Both is an error: one of them
    is the source (import_meters.py turns an export into meters.yaml)."""
    yaml_file, csv_file = data_path("meters.yaml"), data_path("meters.csv")
    if yaml_file.exists() and csv_file.exists():
        raise SystemExit(f"{_rel(DATA_DIR)}: both {yaml_file.name} and {csv_file.name} — keep {yaml_file.name}. "
                         f"To bring in a new export: _build/import_meters.py <export.csv>, then delete the CSV")
    return yaml_file if yaml_file.exists() else csv_file


def read_meter_rows() -> list[dict]:
    """The site's meters as normalised rows (generate_meter_registry's
    shape), whichever file holds them."""
    path = meters_file()
    if not path.exists():
        return []
    if path.suffix == ".csv":
        return generate_meter_registry.read_csv(path, UTILITIES)
    return meters_yaml.read(path, UTILITIES, {lv["key"]: lv["cores"] for lv in read_levels()})


def read_meters() -> list[dict]:
    """The site's meters as a list of normalised meter dicts.

    Placement fields (column/zone/position/function/utility) only count for
    a meter placed on a floor: an unplaced meter gets the same empty
    defaults as a blank cell — matching METER_REGISTRY, which omits
    placement fields for meters with no `floor`.
    """
    out: list[dict] = []
    for row in read_meter_rows():
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
            f"{missing} used in {meters_file().name}"
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
    path = data_path(filename)
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


def floor_report_title(i: int) -> str | None:
    """The title of a floor tab's i-th report card, in position order, when
    its placement sets none: floor_page.report_titles (Demand, Consumption,
    …), then "Report N". None when the site lists no report_titles."""
    titles = FLOOR_PAGE["report_titles"]
    if not titles:
        return None
    return titles[i] if i < len(titles) else f"Report {i + 1}"


# A card's style when its placement sets no `kind`: home cards have a header
# band, building performance cards a title and subtitle; the rest are plain.
REPORT_KINDS = {"home": "headed", "building_performance": "titled"}


def report_cards() -> tuple[dict[str, dict], list[str]]:
    """Every report card by name, for reports.js REPORT_CARDS, plus a
    --check warning for each name given different fields in two places.

    A page writes a card as <div data-report="<name>"></div>, and the
    runtime builds it from these fields: kind (its style, REPORT_KINDS),
    title and subtitle (the header), alt and library_item_id (the link).
    They come from reports.yaml `placements:`, a floor tab's untitled ones
    titled by their order (floor_report_title), then any page's own
    `reports:` list (points.yaml home and incomers, tenants.yaml index and
    floors). A name given twice keeps its first fields."""
    reports = read_reports()
    derived: dict[int, str] = {}
    for floor, slot in {(r.get("floor"), r.get("slot")) for r in reports if r.get("page") == "floor"}:
        for i, r in enumerate(reports_for(reports, page="floor", floor=floor, slot=slot)):
            if (title := floor_report_title(i)) is not None:
                derived[id(r)] = title

    sources: list[tuple[str, list[dict]]] = []
    for r in reports:
        card = reports_to_cards([r])[0]
        if id(r) in derived:
            card.setdefault("title", derived[id(r)])
        if r.get("page") in REPORT_KINDS:
            card.setdefault("kind", REPORT_KINDS[r["page"]])
        sources.append(("reports.yaml placements", [card]))
    home = read_home() or {}
    for field in ("top_reports", "reports"):
        sources.append((f"{point_source('home')} home {field}",
                        [{"kind": REPORT_KINDS["home"], **row} for row in home.get(field) or []]))
    for key, incomer in (read_incomers() or {}).items():
        sources.append((f"{point_source('incomers')} '{key}' reports", incomer.get("reports") or []))
    for tenant in read_tenants():
        data = tenant["data"]
        sources.append((f"{tenant['where']} index reports", (data.get("index") or {}).get("reports") or []))
        for floor_key, floor_data in (data.get("floors") or {}).items():
            for field, rows in (floor_data or {}).items():
                if field.endswith("_reports"):
                    sources.append((f"{tenant['where']} floors.{floor_key}.{field}", rows or []))

    cards: dict[str, dict] = {}
    first: dict[str, str] = {}
    warnings: list[str] = []
    for where, rows in sources:
        for row in rows:
            if "image_ref" not in row:
                continue
            name = str(row["image_ref"]).removeprefix("reports.")
            card = {"alt": row.get("alt", "Report"),
                    **{k: row[k] for k in ("kind", "title", "subtitle", "library_item_id") if k in row}}
            if name not in cards:
                cards[name], first[name] = card, where
            elif card != cards[name]:
                warnings.append(f"{where}: report '{name}' differs from its card in {first[name]} "
                                f"({cards[name]}); pages show that one")
    return cards, warnings


def read_building() -> dict:
    """Load site.yaml (site/building facts). Empty dict if absent."""
    if not BUILDING_FILE.exists():
        return {}
    return yaml.safe_load(BUILDING_FILE.read_text(encoding="utf-8")) or {}


# ─── BMS points ──────────────────────────────────────────────────────────────
# data/points.yaml holds every BMS point the pages show (a meter's own points
# come from the meters file), grouped by page:
#   named:    {<name>: {bacnet, format}}: data-point="<name>" on any page;
#   floors:   {floor_<key>: {<summary role>: {id, bacnet}}}: the live point
#             behind each floor summary card;
#   incomers: {<key>: {heading, summary_cards, …}}: the incomer pages;
#   home:     {heading, info_bar, …}: the home page.
# An older site writes `points:` for `named:`, and keeps the others in
# bms_bindings.yaml (`bindings:` rows), incomers.yaml and home.yaml. A section
# can't be in both places.
POINT_SECTIONS = {
    # section: (an older site's file, its key there, or None for the whole file)
    "named":    ("points.yaml", "points"),
    "floors":   ("bms_bindings.yaml", "bindings"),
    "incomers": ("incomers.yaml", None),
    "home":     ("home.yaml", None),
}


def _points_file() -> dict | None:
    """data/points.yaml grouped by page (POINT_SECTIONS), checked — or None
    for an older site's `points:` table."""
    path = data_path("points.yaml")
    data = _read_yaml(path) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"{_rel(path)}: expected sections {', '.join(POINT_SECTIONS)}")
    if "points" in data:
        if data.keys() & POINT_SECTIONS.keys():
            raise SystemExit(f"{_rel(path)}: `points:` is the older spelling of `named:` — keep one")
        return None
    unknown = sorted(data.keys() - POINT_SECTIONS.keys())
    if unknown:
        raise SystemExit(f"{_rel(path)}: unknown section(s) {unknown} — expected {', '.join(POINT_SECTIONS)}")
    return data


def point_section(name: str):
    """A POINT_SECTIONS section's data, from data/points.yaml or the file an
    older site keeps it in; None if the site has neither."""
    grouped = _points_file()
    file, key = POINT_SECTIONS[name]
    if grouped is not None and name in grouped:
        if file != "points.yaml" and data_path(file).exists():
            raise SystemExit(f"{_rel(data_path(file))}: its contents are points.yaml `{name}:` now — keep one")
        return grouped[name] or {}
    if file == "points.yaml":
        return None if grouped is not None else _read_data("points.yaml", "points", None)
    path = data_path(file)
    if not path.exists():
        return None
    data = _read_yaml(path) or {}
    return data.get(key) if key else data


def point_source(name: str) -> str:
    """Where a POINT_SECTIONS section lives, for messages."""
    grouped = _points_file()
    return f"points.yaml {name}" if grouped is not None and name in grouped else POINT_SECTIONS[name][0]


def read_points() -> dict[str, dict]:
    """Named non-meter BACnet points (points.yaml `named:`) → {name: {bacnet, format}},
    referenced from pages by `data-point="<name>"`."""
    return point_section("named") or {}


def read_incomers() -> dict | None:
    """The incomer pages (points.yaml `incomers:`), {<key>: entry}; None if the site has none."""
    return point_section("incomers")


def read_home() -> dict | None:
    """The home page (points.yaml `home:`); None if the site has none."""
    return point_section("home")


def read_report_urls() -> set[str]:
    """The image_ref names that have a chart URL (site/data/reports.yaml `urls:`)."""
    return set(_read_data("reports.yaml", "urls", {}))


def read_bms_bindings() -> dict[tuple[str, str], dict]:
    """The floor summary cards' live points (points.yaml `floors:`) as a
    {(role, floor): {role, floor, id, bacnet}} map."""
    section = point_section("floors") or []
    if isinstance(section, list):                   # an older site's bms_bindings.yaml rows
        return {(row["role"], row["floor"]): row for row in section}
    rows: dict[tuple[str, str], dict] = {}
    for floor_key, roles in section.items():
        if not str(floor_key).startswith("floor_"):
            raise SystemExit(f"points.yaml floors: '{floor_key}' must be written floor_<key>, as in floors.yaml")
        floor = str(floor_key).removeprefix("floor_")
        for role, binding in (roles or {}).items():
            if not isinstance(binding, dict) or set(binding) != {"id", "bacnet"}:
                raise SystemExit(f"points.yaml floors {floor_key} {role}: expected {{id, bacnet}}, got {binding!r}")
            rows[(role, floor)] = {"role": role, "floor": floor, "id": binding["id"], "bacnet": binding["bacnet"]}
    return rows
