"""
Read site/data/meters.csv — the meter source of truth — into normalised rows.

build.py uses read_csv() twice: read_meters() for every page builder, and
write_js_blocks() to render the runtime's METER_REGISTRY block
(jsblocks.render_meter_registry). The normalisers below map the
spreadsheet's human-edited cells onto the codes the build and CSS expect.

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
from pathlib import Path

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
# `meter-{{ m.utility }}` class the floor-card macro emits both key off the
# site's lowercase utility codes — site.yaml `utilities:`, passed in as
# `utilities` ({code: {label, kind}}). A utility cell may spell out a code or a
# label from that catalog, in any case ("LTHW", "Electricity"). The spreadsheet
# may instead use the broader category "Fluid energy", which alone can't tell
# chw from lthw/lphw — the `function` column can, since every fluid-energy
# meter is tagged with exactly one thermal-kind code there.
FLUID_ENERGY = "fluid energy"

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


def normalise_utility(raw: str, function: str, utilities: dict[str, dict]) -> str:
    """Map a utility cell to the site's lowercase code the CSS classes key
    off, preserving a trailing "-virtual" marker (see VIRTUAL_SUFFIX)."""
    u = clean(raw)
    is_virtual = u.lower().endswith(VIRTUAL_SUFFIX)
    if is_virtual:
        u = u[: -len(VIRTUAL_SUFFIX)]
    base = _normalise_base_utility(u, function, utilities)
    return base + VIRTUAL_SUFFIX if is_virtual else base


def _normalise_base_utility(u: str, function: str, utilities: dict[str, dict]) -> str:
    if u.lower() == FLUID_ENERGY:
        # Most fluid-energy rows carry a descriptive function string (e.g.
        # "HM/04/LTHW - L04 Tenants LTHW", "CHW Basement Cooling") rather
        # than the bare "CHW"/"LTHW"/"LPHW" ticker an exact match would
        # need — a contains-check finds the code wherever it sits in the
        # string. Every fluid-energy row carries exactly one thermal code
        # (checked against the reference site's 650-row CSV), so first match
        # wins with no ambiguity in practice.
        f = function.strip().lower()
        for code, spec in utilities.items():
            if spec["kind"] == "thermal" and code in f:
                return code
        return u
    # A catalog code or label (any case) becomes its code; anything else is
    # passed through untouched, so an unrecognised label stays visible in
    # the registry (and build.py --check reports it) rather than being
    # silently mangled into one.
    names = {code: code for code in utilities} | {spec["label"].lower(): code for code, spec in utilities.items()}
    return names.get(u.lower(), u)


# Integer cells every row must have (BACnet addressing keys off them).
REQUIRED_INT_FIELDS = {"id", "base"}


def _int(row: dict, field: str, *, blank: int | None = None) -> int | None:
    """An integer CSV cell. Blank / "n/a" / "null" gives `blank`; anything
    else that isn't an integer stops the build with a message naming the row
    — these cells are emitted as bare JS numbers, so a stray word would
    otherwise produce a METER_REGISTRY the browser can't parse."""
    v = clean(row.get(field))
    if v == "" or v.lower() == "null":
        if blank is None and field in REQUIRED_INT_FIELDS:
            raise SystemExit(f"meters.csv: meter id={clean(row.get('id'))!r} has no {field}")
        return blank
    if not re.fullmatch(r"-?\d+", v):
        raise SystemExit(
            f"meters.csv: meter id={clean(row.get('id'))!r} has {field}={v!r} — expected a whole number"
            + ("" if field in REQUIRED_INT_FIELDS else ", or blank / n/a")
        )
    return int(v)


def read_csv(csv_file: Path, utilities: dict[str, dict]) -> list[dict]:
    """meters.csv rows, normalised; `utilities` is the site's catalog
    (site.yaml `utilities:`) that utility cells are mapped onto."""
    meters: list[dict] = []
    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not clean(row.get("id")):
                continue  # blank trailing row (common Excel-export artifact)
            function = clean(row["function"])
            meters.append(
                {
                    "id":        _int(row, "id"),
                    "tag":       clean(row["tag"]),
                    "base":      _int(row, "base"),
                    "type":      normalise_type(row["type"]),
                    "daily":     _int(row, "daily", blank=0),
                    "monthly":   _int(row, "monthly", blank=0),
                    "parent_id": _int(row, "parent_id"),
                    "floor":     clean(row["floor"]),
                    "column":    _int(row, "column"),
                    "zone":      clean(row["zone"]),
                    "position":  _int(row, "position"),
                    "function":  function,
                    "utility":   normalise_utility(row["utility"], function, utilities),
                    "tenant":    clean(row.get("tenant")),
                    "tenant_display": parse_yes_no(row.get("tenant_display")),
                    "main_display": parse_yes_no_default_true(row.get("main_display")),
                }
            )
    return meters
