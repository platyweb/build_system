#!/usr/bin/env python
"""
ONE-OFF migration: move the site data that used to live inside the runtime JS
into plain site data files, so the build reads data and writes JS — never the
other way round.

    BMS_BINDINGS            (meter-templates.js) → site/data/bms_bindings.yaml
    POINTS                  (meter-templates.js) → site/data/points.yaml
    ReportUrls.reports      (reports.js)         → site/data/reports.yaml  `urls:`
    REPORT_REGISTRY         (reports.js)         → site/data/reports.yaml  `placements:`

Reads the JS as COMMITTED in git (default: HEAD), not the working tree — the
working-tree skeleton no longer carries BMS_BINDINGS / REPORT_REGISTRY once
they've moved, so reading git keeps this re-runnable until the move itself is
committed (after that, pass --rev <commit-before-the-move>).

The parsers below are build.py's former read_bms_bindings / read_points /
read_reports / read_report_urls, verbatim in behaviour, so the YAML carries
exactly what the build used to see. The script then reloads every file it
wrote and fails unless it equals the parsed JS.

Delete this script once its output has been reviewed and committed.

Usage:
    python _build/migrate_js_data.py [--rev REV] [--site site]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = "_assets/js/project/2.0"

BMS_BEGIN = "// ── BEGIN GENERATED BMS_BINDINGS ── DO NOT EDIT BY HAND ──"
BMS_END = "// ── END GENERATED BMS_BINDINGS ──"
POINTS_BEGIN = "// ── BEGIN POINTS ──"
POINTS_END = "// ── END POINTS ──"
REPORTS_BEGIN = "// ── BEGIN GENERATED REPORT_REGISTRY ── EDIT BY HAND ──"
REPORTS_END = "// ── END GENERATED REPORT_REGISTRY ──"

# ─── Former build.py parsers ─────────────────────────────────────────────────
_FIELD_RE = re.compile(
    r'(\w+)\s*:\s*'
    r'(?:"((?:[^"\\]|\\.)*)"'  # double-quoted string  → group 2
    r'|(-?\d+)'                # bare integer          → group 3
    r'|(true|false))'          # bare boolean          → group 4
)


def _parse_entry(body: str) -> dict:
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


def _between(js: str, begin: str, end: str) -> str:
    try:
        return js.split(begin, 1)[1].split(end, 1)[0]
    except IndexError:
        raise SystemExit(f"markers not found: {begin!r} … {end!r}")


def parse_bms_bindings(js: str) -> tuple[list[dict], list[tuple[str, object]]]:
    """(rows, layout) — layout is the block's lines in order as
    ("entry", row) / ("comment", text) / ("blank", None), so the YAML keeps
    the hand-written section comments and grouping."""
    block = _between(js, BMS_BEGIN, BMS_END)
    rows: list[dict] = []
    layout: list[tuple[str, object]] = []
    for line in block.splitlines():
        s = line.strip()
        m = re.search(r"\{\s*role:[^{}]*\}", line)
        if m:
            row = _parse_entry(m.group(0))
            rows.append(row)
            layout.append(("entry", row))
        elif s.startswith("//"):
            layout.append(("comment", s[2:].strip()))
        elif not s and layout:
            layout.append(("blank", None))
    return rows, layout


def parse_points(js: str) -> dict[str, dict]:
    block = _between(js, POINTS_BEGIN, POINTS_END)
    return {m.group(1): _parse_entry(m.group(2)) for m in re.finditer(r"(\w+)\s*:\s*\{([^{}]*)\}", block)}


def parse_report_registry(js: str) -> list[dict]:
    block = _between(js, REPORTS_BEGIN, REPORTS_END)
    out: list[dict] = []
    for m in re.finditer(r"\{\s*\w+:[^{}]*\}", block):
        entry = _parse_entry(m.group(0))
        if "image_ref" in entry:
            out.append(entry)
    return out


def parse_report_urls(js: str) -> tuple[dict[str, str], list[str | None]]:
    """(urls, layout) — layout is the key order with None for each blank line
    between groups. Fails on a duplicate key: a JS object literal keeps the
    first key's position but the last value, which YAML can't express."""
    head = js.split(REPORTS_BEGIN, 1)[0]
    body = head.split("reports: {", 1)[1]
    body = body[: body.index("\n    }")]
    urls: dict[str, str] = {}
    layout: list[str | None] = []
    for line in body.splitlines():
        m = re.match(r'^\s+([A-Za-z_]\w*)\s*:\s*"((?:[^"\\]|\\.)*)",?\s*$', line)
        if m:
            key = m.group(1)
            if key in urls:
                raise SystemExit(f"ReportUrls.reports: duplicate key {key!r}")
            urls[key] = m.group(2)
            layout.append(key)
        elif not line.strip():
            if layout and layout[-1] is not None:
                layout.append(None)
        else:
            raise SystemExit(f"ReportUrls.reports: unrecognised line {line!r}")
    while layout and layout[-1] is None:
        layout.pop()
    return urls, layout


# ─── YAML writing ────────────────────────────────────────────────────────────
def _scalar(v: object) -> str:
    """A YAML flow scalar for v. Strings are JSON-quoted (always valid YAML,
    and immune to YAML 1.1's yes/no/on/off and 1st-vs-number surprises)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def _flow_rows(rows: list[dict]) -> list[str]:
    """Each row as an aligned `{ k: v, … }` flow mapping (column-aligned on
    each key's widest value, so the file reads as a table)."""
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    width = {k: max((len(_scalar(r[k])) for r in rows if k in r), default=0) for k in keys}
    lines = []
    for r in rows:
        parts = [f"{k}: {_scalar(r[k])}" for k in r]
        padded = [p + "," + " " * (width[k] - len(_scalar(r[k]))) if i < len(parts) - 1 else p
                  for i, (k, p) in enumerate(zip(r, parts))]
        lines.append("{ " + " ".join(padded) + " }")
    return lines


HEADER_RULE = "# " + "─" * 77


def write_bms_bindings(path: Path, layout: list[tuple[str, object]]) -> None:
    rows = [row for kind, row in layout if kind == "entry"]
    flow = iter(_flow_rows(rows))
    out = [
        HEADER_RULE,
        "# BMS bindings — UI bindings to BMS-side BACnet calculation points that",
        "# aren't physical meters (apportioned heat/cool demand, monthly aggregates,",
        "# vs-last-month percentages, floor-incomer instantaneous demand). Looked up",
        "# by (role, floor) at build time to compose summary cards on floor pages",
        "# (build.py derive_summary_cards). Build-time data only — not shipped in",
        "# the runtime JS.",
        "#",
        "# Schema (one row per binding):",
        "#   role   : semantic key; see SUMMARY_CARD_ROLES in _build/build.py",
        "#   floor  : floor key — \"ground\" | \"1st\" | \"2nd\" | …",
        "#   id     : HTML element id used by live updaters",
        "#   bacnet : \"<device>|<object type>|<instance>|85|-1\"",
        "#",
        "# title and format are NOT stored here — they live in the role catalog so",
        "# each role has one canonical label and format across all floors.",
        HEADER_RULE,
        "",
        "bindings:",
    ]
    for kind, val in layout:
        if kind == "entry":
            out.append(f"  - {next(flow)}")
        elif kind == "comment":
            out.append(f"  # {val}")
        else:
            out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def write_points(path: Path, points: dict[str, dict]) -> None:
    name_w = max(len(n) for n in points) + 1
    flow = _flow_rows(list(points.values()))
    out = [
        HEADER_RULE,
        "# Named non-meter BACnet points (BMS calculation points: NABERS rating,",
        "# degree days, energy intensity, site sensors, …). Pages reference a point",
        "# by name with `data-point=\"<name>\"`; the build writes this table into the",
        "# runtime's POINTS block (meter-templates.js), whose resolver fills in",
        "# data-bacnet + data-format on load (mirroring data-meter-id).",
        "#",
        "# Schema: <name>: { bacnet: \"<device>|<object type>|<instance>|85|-1\", format: \"<fmt>\" }",
        "#   format ∈ number | energy | power | percentage | temperature | nabers | status",
        HEADER_RULE,
        "",
        "points:",
    ]
    for (name, _), row in zip(points.items(), flow):
        out.append(f"  {(name + ':').ljust(name_w)} {row}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def write_reports(path: Path, urls: dict[str, str], url_layout: list[str | None], placements: list[dict]) -> None:
    out = [
        HEADER_RULE,
        "# Report cards. Two tables:",
        "#",
        "#   urls        image_ref → chart image URL. The build writes these into the",
        "#               runtime's ReportUrls.reports (reports.js), which resolves",
        "#               every data-image-ref=\"reports.<image_ref>\" on load.",
        "#   placements  which page/slot each report card appears in (build-time",
        "#               only — not shipped in the runtime JS). Fields:",
        "#",
        "#     id        : report library item id (click-through link)",
        "#     image_ref : key into `urls`",
        "#     alt       : image alt text",
        "#     page      : \"floor\" | \"tenant_floor\" | \"tenant_index\" | \"incomer\" | \"home\" | …",
        "#     floor     : floor key (page=\"floor\" / \"tenant_floor\")",
        "#     tenant    : tenant slug (page=\"tenant_floor\" / \"tenant_index\")",
        "#     incomer   : incomer key (page=\"incomer\")",
        "#     slot      : section on the page — \"electricity\" | \"heat\" | \"main\" | \"top\" | …",
        "#     position  : integer order within (page, …, slot)",
        "#     title     : optional banner title (home + incomer_electricity headed cards)",
        "#     kind      : optional render variant — \"headed\" for report_card_headed",
        "#",
        "# Each builder filters placements by the page's placement fields and uses",
        "# the matching rows in position order (build.py reports_for). A page's own",
        "# YAML may still supply an explicit `reports:` list to bypass this.",
        HEADER_RULE,
        "",
        "urls:",
    ]
    for key in url_layout:
        out.append("" if key is None else f"  {key}: {_scalar(urls[key])}")
    out += ["", "placements:"]
    out += [f"  - {row}" for row in _flow_rows(placements)]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


# ─── Main ────────────────────────────────────────────────────────────────────
def git_show(rev: str, rel: str) -> str:
    proc = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"git show {rev}:{rel} failed: {proc.stderr.strip()}")
    return proc.stdout


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rev", default="HEAD", help="git revision to read the JS from (default: HEAD)")
    parser.add_argument("--site", type=Path, default=ROOT / "site", help="site directory to write into")
    args = parser.parse_args(argv)

    meters_js = git_show(args.rev, f"{JS_DIR}/meter-templates.js")
    reports_js = git_show(args.rev, f"{JS_DIR}/reports.js")

    bindings, bms_layout = parse_bms_bindings(meters_js)
    points = parse_points(meters_js)
    placements = parse_report_registry(reports_js)
    urls, url_layout = parse_report_urls(reports_js)

    data_dir = args.site / "data"
    write_bms_bindings(data_dir / "bms_bindings.yaml", bms_layout)
    write_points(data_dir / "points.yaml", points)
    write_reports(data_dir / "reports.yaml", urls, url_layout, placements)

    # Self-check: what the build will load must equal what it used to parse.
    load = lambda name: yaml.safe_load((data_dir / name).read_text(encoding="utf-8"))  # noqa: E731
    checks = [
        ("bms_bindings.yaml bindings", load("bms_bindings.yaml")["bindings"], bindings),
        ("points.yaml points", load("points.yaml")["points"], points),
        ("reports.yaml urls", load("reports.yaml")["urls"], urls),
        ("reports.yaml placements", load("reports.yaml")["placements"], placements),
    ]
    failed = False
    for label, got, want in checks:
        same = got == want and list(got) == list(want)  # equal AND same order
        print(f"  {'ok ' if same else 'BAD'} {label}: {len(want)} entries")
        failed |= not same
    if failed:
        raise SystemExit("migration self-check failed — the YAML doesn't round-trip to the JS data")
    print(f"Wrote {data_dir.relative_to(ROOT)}/bms_bindings.yaml, points.yaml, reports.yaml from {args.rev}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
