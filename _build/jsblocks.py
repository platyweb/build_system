"""
Generated blocks in the runtime JS.

The runtime skeleton (_assets/js/project/2.0/*.js) carries BEGIN/END marker
pairs. The build stages a copy of it (build.stage_output) and replaces what
sits between each pair with a block rendered here from site data. Data only
flows one way — site files → JS; nothing reads these blocks back.

Every string value is emitted with json.dumps, so a quote or backslash in the
data (a meter tag, a URL) can't break the JS — an unquoted value used to.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ─── Marker pairs ────────────────────────────────────────────────────────────
METER_REGISTRY = (
    "// ── BEGIN GENERATED METER_REGISTRY ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED METER_REGISTRY ──",
)
POINTS = (
    "// ── BEGIN POINTS ──",
    "// ── END POINTS ──",
)
SIDEBAR_HTML = (
    "// ── BEGIN GENERATED SIDEBAR_HTML ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED SIDEBAR_HTML ──",
)
REPORT_URLS = (  # reports.js
    "// ── BEGIN GENERATED REPORT_URLS ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED REPORT_URLS ──",
)
REPORT_CARDS = (  # reports.js
    "// ── BEGIN GENERATED REPORT_CARDS ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED REPORT_CARDS ──",
)
BACNET_CONFIG = (  # meter-templates.js
    "// ── BEGIN GENERATED BACNET_CONFIG ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED BACNET_CONFIG ──",
)
SIDEBAR_RUNTIME = (  # sidebar-template.js
    "// ── BEGIN GENERATED SIDEBAR_RUNTIME ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED SIDEBAR_RUNTIME ──",
)
OVERRIDE_FILE = (  # live-points.js
    "// ── BEGIN GENERATED OVERRIDE_FILE ── DO NOT EDIT BY HAND ──",
    "// ── END GENERATED OVERRIDE_FILE ──",
)


def inject(js_file: Path, markers: tuple[str, str], body: str) -> None:
    """Replace everything between `markers` in js_file with `body`, keeping
    the marker lines themselves. Fails loudly if the markers are missing."""
    begin, end = markers
    js = js_file.read_text(encoding="utf-8")
    pattern = re.escape(begin) + r".*?" + re.escape(end)
    if not re.search(pattern, js, flags=re.DOTALL):
        raise SystemExit(f"{begin!r} … {end!r} markers not found in {js_file}")
    block = f"{begin}\n{body}\n{end}"
    # A function replacement, not a string: re.sub would otherwise interpret
    # backslashes in the block (e.g. a JSON-escaped quote) as escape codes.
    js_file.write_text(re.sub(pattern, lambda _m: block, js, flags=re.DOTALL), encoding="utf-8", newline="\n")


def js_value(v: object) -> str:
    """A JS literal for a scalar from site data."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


# ─── METER_REGISTRY ──────────────────────────────────────────────────────────
def _render_meter(m: dict, widths: dict[str, int]) -> str:
    """One registry entry, with id/tag/base/daily/monthly column-aligned."""
    parts = [
        f'id: {str(m["id"]).rjust(widths["id"])}',
        f'tag: {js_value(m["tag"]).ljust(widths["tag"])}',
        f'base: {str(m["base"]).rjust(widths["base"])}',
        f'type: {js_value(m["type"])}',
        f'daily: {str(m["daily"]).rjust(widths["daily"])}',
        f'monthly: {str(m["monthly"]).rjust(widths["monthly"])}',
    ]

    # parent_id is emitted only for meters that appear in meters_hierarchy.htm
    # (0 marks the root). Meters outside the hierarchy carry no parent_id.
    if m.get("parent_id") is not None:
        parts.append(f'parent_id: {m["parent_id"]}')

    # Placement fields are emitted only when set, so meters not pinned to a
    # floor don't carry empty properties. column/position are ints or None —
    # None becomes the JS keyword null.
    if m["floor"]:
        parts.append(f'floor: {js_value(m["floor"])}')
        parts.append(f'column: {js_value(m["column"])}')
        parts.append(f'zone: {js_value(m["zone"])}')
        parts.append(f'position: {js_value(m["position"])}')
        parts.append(f'function: {js_value(m["function"])}')
        parts.append(f'utility: {js_value(m["utility"])}')

    # tenant: comma-separated tenant names for shared meters; emitted only
    # when set so non-tenant meters stay clean.
    if m.get("tenant"):
        parts.append(f'tenant: {js_value(m["tenant"])}')

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


def render_meter_registry(meters: list[dict]) -> str:
    """`const METER_REGISTRY = [ … ];` from meters.csv rows
    (generate_meter_registry.read_csv)."""
    widths = {
        "id":      max((len(str(m["id"]))      for m in meters), default=0),
        "tag":     max((len(js_value(m["tag"])) for m in meters), default=0),
        "base":    max((len(str(m["base"]))    for m in meters), default=0),
        "daily":   max((len(str(m["daily"]))   for m in meters), default=0),
        "monthly": max((len(str(m["monthly"])) for m in meters), default=0),
    }
    lines = ["const METER_REGISTRY = ["]
    for i, m in enumerate(meters):
        comma = "," if i < len(meters) - 1 else ""
        lines.append(_render_meter(m, widths) + comma)
    lines.append("];")
    return "\n".join(lines)


# ─── POINTS ──────────────────────────────────────────────────────────────────
def render_points(points: dict[str, dict]) -> str:
    """`const POINTS = { name: { bacnet, format }, … };` from points.yaml,
    names padded so the entries line up."""
    width = max((len(name) for name in points), default=0) + 2  # "name:" + at least one space
    items = list(points.items())
    lines = ["const POINTS = {"]
    for i, (name, fields) in enumerate(items):
        body = ", ".join(f"{k}: {js_value(v)}" for k, v in fields.items())
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {(name + ':').ljust(width)}{{ {body} }}{comma}")
    lines.append("};")
    return "\n".join(lines)


# ─── BACNET_CONFIG ───────────────────────────────────────────────────────────
def render_bacnet_config(bacnet: dict) -> str:
    """`const BACNET_CONFIG = { device, powerOffset };` from site.yaml `bacnet:`
    — read by meter-templates.js bacnet() / getPowerOffset()."""
    offsets = ", ".join(f"{js_value(str(t))}: {js_value(o)}" for t, o in bacnet["power_offset"].items())
    return "\n".join([
        "const BACNET_CONFIG = {",
        f"    device: {js_value(bacnet['device'])},",
        f"    powerOffset: {{ {offsets} }}",
        "};",
    ])


def render_sidebar_runtime(src: str) -> str:
    """`const SIDEBAR_RUNTIME_SRC = "…";`: where sidebar-template.js loads
    the sidebar runtime from, relative to the page."""
    return f"const SIDEBAR_RUNTIME_SRC = {json.dumps(src)};"


def render_override_file(display: str) -> str:
    """`const LIVE_POINTS_OVERRIDE_FILE = "…";`: the Optergy display file
    live-points.js posts point overrides to ("" for none)."""
    return f"const LIVE_POINTS_OVERRIDE_FILE = {json.dumps(display, ensure_ascii=False)};"


# ─── ReportUrls ──────────────────────────────────────────────────────────────
def render_report_urls(urls: dict[str, str]) -> str:
    """`const ReportUrls = { reports: { image_ref: "url", … } };` from
    reports.yaml `urls:` — the runtime resolves data-image-ref="reports.<image_ref>"."""
    items = list(urls.items())
    lines = ["const ReportUrls = {", "    reports: {"]
    for i, (ref, url) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"        {ref}: {js_value(url)}{comma}")
    lines += ["    }", "};"]
    return "\n".join(lines)


# ─── REPORT_CARDS ────────────────────────────────────────────────────────────
REPORT_CARD_FIELDS = (("kind", "kind"), ("title", "title"), ("subtitle", "subtitle"), ("alt", "alt"),
                      ("library_item_id", "libraryItemId"))


def render_report_cards(cards: dict[str, dict]) -> str:
    """`const REPORT_CARDS = { <name>: { kind, title, subtitle, alt, libraryItemId }, … };`
    from build.report_cards(): what the runtime needs to build the card a
    page asks for with <div data-report="<name>">. A field that isn't set
    is left out (no kind: a plain card; no title: no header band; no id:
    the card links to #)."""
    if not cards:
        return "const REPORT_CARDS = {};"
    items = list(cards.items())
    lines = ["const REPORT_CARDS = {"]
    for i, (name, card) in enumerate(items):
        fields = ", ".join(f"{js}: {js_value(card[key])}" for key, js in REPORT_CARD_FIELDS if key in card)
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {name}: {{ {fields} }}{comma}")
    lines.append("};")
    return "\n".join(lines)
