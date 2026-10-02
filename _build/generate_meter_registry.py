"""
Generate METER_REGISTRY block for js/project/2.0/meter-templates.js from _data/meters.csv.

Usage:  python generate_meter_registry.py

Reads _data/meters.csv and replaces the METER_REGISTRY block in
js/project/2.0/meter-templates.js between the BEGIN/END markers.

CSV columns (in order):
  id, tag, base, type, daily, monthly, parent_id, floor, column, zone,
  position, function, utility, tenant, tenant_display, main_display

The first six are the "core" fields that drive BACnet address resolution at
runtime (see meter-templates.js). parent_id is consumed by the static
generator to render the meters_hierarchy tree (0 = root). The next five
placement fields are consumed by the static generator to derive floor
layouts. `floor` may name more than one floor, "/"-separated (e.g.
"3rd/4th"), for a meter that belongs on several floor pages — it's placed
with the same column/zone/position/function/utility on each (build.py's
read_meters() splits it into a "floors" tuple). `utility` may either
name a broad category the spreadsheet groups by ("Electricity", "Fluid
energy") or spell out a code directly ("lthw", "chw", "electricity"), and
either form may carry a "-virtual" suffix ("lthw-virtual") to mark a
calculated meter — that picks the meter-<code>-virtual CSS class, which
colours as its utility does but fades into #2A0048 along the right edge.
`tenant` (comma-separated
string for shared meters) and `tenant_display` (yes/no — must be "yes" for
the meter to appear on any tenant page; blank/anything else means no) are
consumed by the tenant-pages builder. `main_display` is the opposite
polarity — an opt-OUT flag for the main (non-tenant) floor pages: blank or
"yes" shows the meter there (the default — matches every row that predates
this column), and only an explicit "no" hides it. It's independent of
tenant_display/tenant, so a meter can be main-only, tenant-only, both, or
neither. All optional fields are emitted as JS object properties only when
set.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
from build import DATA_DIR, ROOT, SITE_DIR  # noqa: E402  (SITE_DIR derives from _data/building.yaml's slug)

CSV_FILE = DATA_DIR / "meters.csv"
JS_FILE = SITE_DIR / "js" / "project" / "2.0" / "meter-templates.js"

BEGIN_MARKER = "// ── BEGIN GENERATED METER_REGISTRY ── DO NOT EDIT BY HAND ──"
END_MARKER = "// ── END GENERATED METER_REGISTRY ──"

CORE_FIELDS = ["id", "tag", "base", "type", "daily", "monthly"]
PLACEMENT_FIELDS = ["floor", "column", "zone", "position", "function", "utility"]
# parent_id is its own thing — emitted between monthly and the placement
# block. 0 means "root of the hierarchy"; blank means "not in the
# hierarchy".


def clean(raw: str | None) -> str:
    """Strip a CSV cell and treat 'n/a' (any case) as blank.

    id/base are never 'n/a' (always-required ints, parsed separately below) —
    every other column is free to carry 'n/a' as a "not applicable" marker in
    the spreadsheet, and it collapses to the same blank each field already
    treats as absent (0 for daily/monthly, None for parent_id, omitted for
    the placement/tenant fields, literal `null` for column/position — see
    _render_entry).
    """
    v = (raw or "").strip()
    return "" if v.lower() == "n/a" else v


def normalise_type(raw: str) -> str:
    """Normalise type values — fix common typos like 'Calcualtion' → 'Calculation'."""
    t = clean(raw)
    if t.lower().startswith("calc"):
        return "Calculation"
    return t


# The CSS (--meter-chw-bg, --meter-lthw-bg, --meter-electricity-bg, …) and the
# `meter-{{ m.utility }}` class the floor-card macro emits both key off these
# exact lowercase codes. The spreadsheet instead groups meters under broader
# category labels ("Electricity", "Fluid energy"), so "Fluid energy" alone
# can't tell chw from lthw/lphw — the `function` column can, since every
# fluid-energy meter is tagged CHW/LTHW/LPHW 1:1 there.
FLUID_ENERGY_FUNCTIONS = {"chw", "lthw", "lphw"}

# Codes the CSS styles by name, i.e. what a utility cell may spell out
# directly instead of going through a category label. Lower-cased on the way
# through so "LTHW" in the spreadsheet still lands on .meter-lthw.
UTILITY_CODES = {"electricity", "gas", "water"} | FLUID_ENERGY_FUNCTIONS

# Suffix marking a virtual (calculated) meter, e.g. a utility cell of
# "lthw-virtual". It rides along on whatever the base code normalises to, so
# the class becomes meter-lthw-virtual — the CSS pairs each of these with its
# physical counterpart: same fill and accent, plus a #2A0048 fade down the
# right-hand edge. Every *comparison* of a meter's utility strips it back off
# (build.py's base_utility()), so a virtual LTHW meter still counts as heat.
VIRTUAL_SUFFIX = "-virtual"


def parse_yes_no(raw: str | None) -> bool:
    """CSV/xlsx carries this as a human-edited 'yes'/'no' cell — anything
    other than a case-insensitive 'yes' (blank included) is 'no'."""
    return clean(raw).strip().lower() == "yes"


def parse_yes_no_default_true(raw: str | None) -> bool:
    """Opt-OUT counterpart of parse_yes_no: blank or 'yes' is True (the
    default — every row that predates this column keeps behaving as before);
    only a case-insensitive 'no' is False."""
    return clean(raw).strip().lower() != "no"


def normalise_utility(raw: str, function: str) -> str:
    """Map a utility cell to the lowercase code the CSS classes key off,
    preserving a trailing "-virtual" marker (see VIRTUAL_SUFFIX)."""
    u = clean(raw)
    is_virtual = u.lower().endswith(VIRTUAL_SUFFIX)
    if is_virtual:
        u = u[: -len(VIRTUAL_SUFFIX)]
    base = _normalise_base_utility(u, function)
    return base + VIRTUAL_SUFFIX if is_virtual else base


def _normalise_base_utility(u: str, function: str) -> str:
    if u.lower() == "fluid energy":
        # Most fluid-energy rows carry a descriptive function string (e.g.
        # "HM/04/LTHW - L04 Tenants LTHW", "CHW Basement Cooling") rather
        # than the bare "CHW"/"LTHW"/"LPHW" ticker an exact match would
        # need — a contains-check finds the tag wherever it sits in the
        # string. Every fluid-energy row in the registry carries exactly
        # one of the three (checked against the full CSV), so first match
        # wins with no ambiguity in practice.
        f = function.strip().lower()
        for token in FLUID_ENERGY_FUNCTIONS:
            if token in f:
                return token
        return u
    # Anything the CSS knows by name is lower-cased; anything else is passed
    # through untouched, so an unrecognised label stays visible in the
    # registry (as a class with no styling) rather than being silently
    # mangled into one.
    return u.lower() if u.lower() in UTILITY_CODES else u


def read_csv() -> list[dict]:
    meters: list[dict] = []
    with CSV_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not clean(row.get("id")):
                continue  # blank trailing row (common Excel-export artifact)
            parent_raw = clean(row.get("parent_id"))
            function = clean(row["function"])
            meters.append(
                {
                    "id":        int(row["id"]),
                    "tag":       clean(row["tag"]),
                    "base":      int(row["base"]),
                    "type":      normalise_type(row["type"]),
                    "daily":     int(clean(row["daily"]) or 0),
                    "monthly":   int(clean(row["monthly"]) or 0),
                    "parent_id": int(parent_raw) if parent_raw != "" else None,
                    "floor":     clean(row["floor"]),
                    "column":    clean(row["column"]),
                    "zone":      clean(row["zone"]),
                    "position":  clean(row["position"]),
                    "function":  function,
                    "utility":   normalise_utility(row["utility"], function),
                    "tenant":    clean(row.get("tenant")),
                    "tenant_display": parse_yes_no(row.get("tenant_display")),
                    "main_display": parse_yes_no_default_true(row.get("main_display")),
                }
            )
    return meters


def _render_entry(m: dict, widths: dict[str, int]) -> str:
    """Render one registry entry with aligned columns."""
    parts = [
        f'id: {str(m["id"]).rjust(widths["id"])}',
        f'tag: {(chr(34) + m["tag"] + chr(34)).ljust(widths["tag"] + 2)}',
        f'base: {str(m["base"]).rjust(widths["base"])}',
        f'type: "{m["type"]}"',
        f'daily: {str(m["daily"]).rjust(widths["daily"])}',
        f'monthly: {str(m["monthly"]).rjust(widths["monthly"])}',
    ]

    # parent_id is emitted only for meters that appear in meters_hierarchy.htm
    # (0 marks the root). Meters outside the hierarchy carry no parent_id.
    if m.get("parent_id") is not None:
        parts.append(f'parent_id: {m["parent_id"]}')

    # Placement fields are emitted only when set, so meters not pinned to a
    # floor don't carry empty properties.
    if m["floor"]:
        parts.append(f'floor: "{m["floor"]}"')
        # column/position are emitted as bare JS tokens (ints, or the keyword
        # null) — never quoted — so a blank (cleared from "n/a") must become
        # the literal `null` rather than nothing, or the JS fails to parse.
        parts.append(f'column: {m["column"] or "null"}')
        parts.append(f'zone: "{m["zone"]}"')
        parts.append(f'position: {m["position"] or "null"}')
        parts.append(f'function: "{m["function"]}"')
        parts.append(f'utility: "{m["utility"]}"')

    # tenant: comma-separated tenant slugs for shared meters; emitted only
    # when set so non-tenant meters stay clean.
    if m.get("tenant"):
        parts.append(f'tenant: "{m["tenant"]}"')

    # tenant_display: explicit opt-in gate for the tenant-pages builder —
    # emitted only when true (blank/"no" in the CSV is the default and
    # needs no property at all, same as the other optional fields).
    if m.get("tenant_display"):
        parts.append("tenant_display: true")

    # main_display: opt-OUT gate for the main (non-tenant) floor pages —
    # inverse polarity from tenant_display, so it's emitted only when
    # false (blank/"yes" in the CSV is the default and needs no property,
    # same as every other optional field).
    if not m.get("main_display", True):
        parts.append("main_display: false")

    return "    { " + ", ".join(parts) + " }"


def build_registry_block(meters: list[dict]) -> str:
    widths = {
        "id":      max(len(str(m["id"]))      for m in meters),
        "tag":     max(len(m["tag"])          for m in meters),
        "base":    max(len(str(m["base"]))    for m in meters),
        "daily":   max(len(str(m["daily"]))   for m in meters),
        "monthly": max(len(str(m["monthly"])) for m in meters),
    }

    lines = [BEGIN_MARKER, "const METER_REGISTRY = ["]
    for i, m in enumerate(meters):
        comma = "," if i < len(meters) - 1 else ""
        lines.append(_render_entry(m, widths) + comma)
    lines.append("];")
    lines.append(END_MARKER)
    return "\n".join(lines)


def update_js(new_block: str) -> bool:
    content = JS_FILE.read_text(encoding="utf-8")
    pattern = re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER)
    if not re.search(pattern, content, re.DOTALL):
        print(f"ERROR: BEGIN/END markers not found in {JS_FILE}")
        return False
    new_content = re.sub(pattern, new_block, content, flags=re.DOTALL)
    JS_FILE.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    if not CSV_FILE.exists():
        raise SystemExit(f"{CSV_FILE} not found")
    if not JS_FILE.exists():
        raise SystemExit(f"{JS_FILE} not found")

    meters = read_csv()
    print(f"Read {len(meters)} meters from {CSV_FILE.name}")

    block = build_registry_block(meters)
    if update_js(block):
        with_placement = sum(1 for m in meters if m["floor"])
        print(f"Updated METER_REGISTRY in {JS_FILE.relative_to(ROOT)}")
        print(f"  ({with_placement} meters carry placement fields)")
    else:
        raise SystemExit("Failed to update JS file")


if __name__ == "__main__":
    main()
