#!/usr/bin/env python
"""
Prefill a site's data files from the building's documents: its floors,
meters, tenants, report cards and floorplans, so they don't have to be
typed in.

Usage:
    python _build/prefill.py                 # site/
    python _build/prefill.py --site DIR
    python _build/prefill.py --dry-run       # report what it would write; write nothing
    python _build/prefill.py --replace       # also overwrite data files it didn't write,
                                             # and make the floorplans again

Put the documents in <site>/sources/; each is found by what it holds:
  - the Optergy import workbook (.xlsx with a sheet headed name … driver):
    the meters, their types, calculation members, utilities, the
    daily/monthly points and the report charts. Every sheet is read, backups
    included: a building prefix on the meter names ("ABC - …") picks this
    building's rows;
  - the meter schedule (.xlsx with a "Meter No." column): tenants, the core
    each meter sits in, utilities;
  - the controller's meter export (.csv with id and tag columns, e.g. a
    meters.csv): meter ids, BACnet bases, types and parents. Without it the
    ids are provisional, numbered from `first_id` in workbook order, and the
    meters have no hierarchy: add the export and run again;
  - the floor drawings, in sources/floorplans/, each named for its level
    ("Ninth_Floor.emf", "L3.svg"): each page level's
    assets/img/floors/floor_<key>.png, copied or converted (PDF with
    pdftoppm; SVG and EMF with inkscape, if installed). An image already
    there is kept unless --replace.

It writes data/floors.yaml, meters.yaml, tenants.yaml and reports.yaml
(numbered, e.g. 02_floors.yaml) and prints a report: where each field came from, what it
couldn't fill, and where the documents disagree. A file it wrote starts
with a "# prefill:" line; a re-run replaces it, and stops instead if the
file was edited since. Make corrections in sources/prefill.yaml, so a re-run
keeps them; every key there is optional (README "Prefilling from a
building's documents").

site.yaml stays the site's own: the report lists the utilities and meter
types the meters need that it lacks.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
import dataclasses
from pathlib import Path
from urllib.parse import quote

import yaml

import generate_meter_registry
import meters_yaml
import site_data
import xlsx

SOURCES = "sources"
SETTINGS = "prefill.yaml"
REPORT = "prefill-report.txt"   # the last run's report, in full
MARK = "# prefill:"

DEFAULTS: dict = {
    "workbook": None,      # file names in sources/; default: found by content
    "schedule": None,
    "controller": None,
    "prefix": None,        # the building prefix on meter names; default: the most common one
    "first_id": 1,         # the first provisional id, without a controller export
    "utility_codes": {"0": "electricity"},       # the workbook's utility codes
    "types": {"Aggregate": "Calculation"},       # workbook driver → meter type
    "points": {                                  # workbook custom points → daily / monthly
        "daily": {"period": "This", "frequency": "month"},
        "monthly": {"period": "Previous To Today Equivalent", "frequency": "month"},
    },
    "levels": {},          # {key: {label, match: [regex], <floors.yaml fields>}}
    "default_core": "Floor",
    "columns": {},         # {core: floor-page column}
    "landlord": ["Landlord", "Landlords", "Vacant", "n/a", "TBD", "Common", "Spare"],
    "tenants": {},         # {proper name: {short, <tenants.yaml fields>}}
    "tenant_display": True,
    "schedule_columns": {},  # {field: header}: meter_no, description, switchboard, tenant, location
    "meters": {},          # {tag: {field: value}}: corrections, applied last
    "report_ids": {},      # {report name: report-library id}: each card's link
    "first_report_id": None,   # or: ids numbered from here in the Reports sheet's order
    "reports": {},         # {urls: {…}, placements: […]}: report cards of the site's own, added as they are
    "floorplans": "floorplans",   # the folder in sources/ holding the floor drawings
}

# ─── Levels ──────────────────────────────────────────────────────────────────
# A level named in a document becomes a canonical (rank, key, label): rank
# orders the levels bottom → top. The first pattern that matches wins;
# prefill.yaml `levels: {<key>: {match: [regex]}}` is tried before these.
ORDINAL_WORDS = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
                 "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth").split()
LEVEL_PATTERNS: list[tuple[str, object]] = [
    (r"\bupper[\s_-]*roof\b", "upper_roof"),
    (r"\broof\b", "roof"),
    (r"\b(?:lower[\s_-]*ground|LGF?)\b", "lower_ground"),
    (r"\b(?:upper[\s_-]*ground|UGF?)\b", "upper_ground"),
    (r"\bmezz(?:anine)?\b", "mezzanine"),
    (r"\b(?:ground|grd|GF|G\d)\b", "ground"),
    (r"\bbasement[\s_-]*(\d)?\b", "basement"),
    (r"\bB\d\b", "basement"),       # B1, B2: a board's number as often as a second basement
    (r"\b(?:FL|floor|level|lvl)[\s_-]*0*(\d{1,2})\b", "number"),
    (r"\b(\d{1,2})(?:st|nd|rd|th)\b", "number"),
    (r"\b(" + "|".join(ORDINAL_WORDS) + r")\b", "word"),
]
NAMED_LEVELS = {  # key: (rank, label)
    "lower_ground": (-2, "Lower Ground Floor"),
    "ground": (0, "Ground Floor"),
    "upper_ground": (0.5, "Upper Ground Floor"),
    "mezzanine": (0.7, "Mezzanine"),
    "roof": (1000, "Roof"),
    "upper_roof": (1001, "Upper Roof"),
}


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _level(kind, match: re.Match) -> str | None:
    if kind == "number":
        n = int(match.group(1))
        return "ground" if n == 0 else ordinal(n)
    if kind == "word":
        return ordinal(ORDINAL_WORDS.index(match.group(1).lower()) + 1)
    if kind == "basement":
        n = int(match.group(1) or 1) if match.groups() else 1
        return "basement" if n == 1 else f"basement_{n}"
    return kind


def level_finder(levels: dict):
    """A function giving the level key a text names, "" for none: prefill.yaml
    `levels: {<key>: {match: [regex]}}` first, then LEVEL_PATTERNS."""
    patterns = [(re.compile(p, re.I), key) for key, spec in levels.items() for p in (spec or {}).get("match", [])]
    patterns += [(re.compile(p, re.I), kind) for p, kind in LEVEL_PATTERNS]

    def level_of(text: str) -> str:
        return next((_level(kind, m) for pattern, kind in patterns if (m := pattern.search(text))), "")
    return level_of


def level_rank(key: str) -> tuple[float, str]:
    if key in NAMED_LEVELS:
        return NAMED_LEVELS[key][0], key
    if m := re.fullmatch(r"basement(?:_(\d+))?", key):
        return -10 - int(m.group(1) or 1), key
    if m := re.fullmatch(r"(\d+)(?:st|nd|rd|th)", key):
        return int(m.group(1)), key
    return 500, key   # a key of the site's own (prefill.yaml levels:)


def level_label(key: str) -> str:
    if key in NAMED_LEVELS:
        return NAMED_LEVELS[key][1]
    if m := re.fullmatch(r"basement_(\d+)", key):
        return f"Basement {m.group(1)}"
    if key == "basement":
        return "Basement"
    if re.fullmatch(r"\d+(?:st|nd|rd|th)", key):
        return f"{key} Floor"
    return key


# ─── Cores and loads ─────────────────────────────────────────────────────────
CORE = re.compile(r"\b((?:north|south|east|west|centre|central|middle)[\s_-]*core(?:[\s_-]*\d+)?|core[\s_-]*\d+)\b", re.I)
# A core's floor-page column, by its compass word; anything else goes in 0.
COMPASS_COLUMNS = {"west": 0, "north": 1, "south": 1, "centre": 1, "central": 1, "middle": 1, "east": 2}
# What a distribution-board meter feeds, to order a core's meters (lighting,
# then power, then mechanical) and to match a schedule row to a meter.
LOADS = (("mech", re.compile(r"\bmech\w*", re.I)),
         ("lighting", re.compile(r"\b(?:lig\w*|ltg)\b|\bL$", re.I)),
         ("power", re.compile(r"\b(?:pow\w*|sp)\b|\bP$", re.I)))


def core_of(text: str) -> str:
    m = CORE.search(text)
    return " ".join(w.capitalize() for w in re.split(r"[\s_-]+", m.group(1))) if m else ""


def load_of(text: str) -> str:
    return next((name for name, pattern in LOADS if pattern.search(text.strip())), "")


def compact(text: str) -> str:
    """A name compared without case, spaces or punctuation."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ─── Settings and sources ────────────────────────────────────────────────────
def read_settings(sources: Path) -> dict:
    path = sources / SETTINGS
    given = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    unknown = sorted(set(given) - set(DEFAULTS))
    if unknown:
        raise SystemExit(f"{site_data._rel(path)}: unknown setting(s) {', '.join(unknown)} — "
                         f"the settings are {', '.join(DEFAULTS)}")
    settings = {**DEFAULTS, **given}
    if not isinstance(settings["first_id"], int):
        raise SystemExit(f"{site_data._rel(path)}: first_id is a whole number, not {settings['first_id']!r}")
    return settings


def _header(rows: list[xlsx.Row]) -> dict[str, int]:
    """A sheet's first row as {lowercased header: column}, first one winning."""
    out: dict[str, int] = {}
    for i, cell in enumerate(rows[0].cells if rows else []):
        out.setdefault(cell.strip().lower(), i)
    return out


WORKBOOK_SHEETS = {"meters": {"name", "driver"},
                   "points": {"meter", "period", "frequency", "instance"},
                   "renames": {"current_name", "new_name"},
                   "reports": {"name", "chart", "report"}}
SCHEDULE_COLUMNS = {  # field: header spellings, compared by compact()
    "meter_no": ["Meter No.", "Meter Number", "Meter Ref", "Meter"],
    "description": ["Description", "Serving"],
    "switchboard": ["Switchboard", "Switch Board", "SWB", "Board"],
    "tenant": ["Tenant", "Tenants"],
    "location": ["Location"],
}


def _schedule_header(rows: list[xlsx.Row]) -> int | None:
    """The index of a schedule sheet's header row: the first with a Meter No. column."""
    names = {compact(n) for n in SCHEDULE_COLUMNS["meter_no"]}
    return next((i for i, r in enumerate(rows[:6]) if any(compact(c) in names for c in r.cells)), None)


def find_sources(sources: Path, settings: dict) -> dict[str, Path | None]:
    """The workbook, schedule and controller export: named in the settings,
    or found in sources/ by what they hold."""
    found: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(sources.iterdir()) if sources.is_dir() else []:
        if path.name.startswith(("~$", ".")):
            continue
        if path.suffix.lower() == ".xlsx":
            sheets = xlsx.read(path)
            if any(WORKBOOK_SHEETS["meters"] <= set(_header(rows)) for rows in sheets.values()):
                found["workbook"].append(path)
            elif any(_schedule_header(rows) is not None for rows in sheets.values()):
                found["schedule"].append(path)
        elif path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as f:
                header = {h.strip().lower() for h in next(csv.reader(f), [])}
            if "id" in header and header & {"tag", "name"}:
                found["controller"].append(path)
    out: dict[str, Path | None] = {}
    for kind in ("workbook", "schedule", "controller"):
        if settings[kind]:
            path = sources / settings[kind]
            if not path.exists():
                raise SystemExit(f"{site_data._rel(sources / SETTINGS)}: {kind} {settings[kind]!r} isn't in {site_data._rel(sources)}")
            out[kind] = path
        elif len(found[kind]) > 1:
            raise SystemExit(f"{site_data._rel(sources)}: {len(found[kind])} files look like the {kind} "
                             f"({', '.join(p.name for p in found[kind])}) — name one in {SETTINGS}: `{kind}: <file>`")
        else:
            out[kind] = found[kind][0] if found[kind] else None
    return out


class Report:
    """What the run found, for the printout."""

    def __init__(self) -> None:
        self.sources: dict[str, Counter] = defaultdict(Counter)   # field → Counter(source)
        self.notes: dict[str, list[str]] = defaultdict(list)      # heading → lines

    def source(self, field: str, where: str) -> None:
        self.sources[field][where] += 1

    def note(self, heading: str, line: str) -> None:
        self.notes[heading].append(line)

    def text(self, files: list[str], limit: int | None = 15) -> str:
        out = ["Fields, and where they came from:"]
        for field, counts in self.sources.items():
            out.append(f"  {field:15} " + ", ".join(f"{where} {n}" for where, n in counts.most_common()))
        for heading, lines in self.notes.items():
            out.append(f"\n{heading} ({len(lines)}):")
            out += [f"  {line}" for line in lines[:limit]]
            if limit is not None and len(lines) > limit:
                out.append(f"  … and {len(lines) - limit} more (all of them: {SOURCES}/{REPORT})")
        out.append("\nFiles:")
        out += [f"  {line}" for line in files]
        return "\n".join(out)


# ─── The workbook ────────────────────────────────────────────────────────────
@dataclasses.dataclass
class Workbook:
    prefix: str = ""                                            # "" for none
    meters: dict[str, dict] = dataclasses.field(default_factory=dict)    # by name, in workbook order
    points: dict[tuple, str] = dataclasses.field(default_factory=dict)   # (name, period, frequency) → instance
    reports: list[dict] = dataclasses.field(default_factory=list)        # the Reports rows, in order


def read_workbook(path: Path, settings: dict, report: Report) -> Workbook:
    sheets = {name: rows for name, rows in xlsx.read(path).items() if rows}
    kinds = {name: next((k for k, cols in WORKBOOK_SHEETS.items() if cols <= set(_header(rows))), None)
             for name, rows in sheets.items()}

    def records(kind: str):
        for name, rows in sheets.items():
            if kinds[name] == kind:
                header = _header(rows)
                for row in rows[1:]:
                    yield name, row.number, {h: row.cell(i) for h, i in header.items()}

    names = [r["name"] for _, _, r in records("meters") if r.get("name")]
    prefix = settings["prefix"] or _prefix(names)
    if prefix is None:
        report.note("Workbook", "no building prefix shared by most meter names: every sheet's meters are read — "
                                "set `prefix:` if the workbook holds other buildings' rows")
    ours = (lambda name: True) if prefix is None else \
        (lambda name: re.match(rf"{re.escape(prefix)}\s*-", name, re.I) is not None)

    renames = {r["current_name"]: r["new_name"] for _, _, r in records("renames")
               if r.get("current_name") and r.get("new_name") and ours(r["new_name"])}
    final = lambda name: renames.get(name, name)

    meters: dict[str, dict] = {}
    for sheet, number, r in records("meters"):
        name = r.get("name", "")
        if not name or not ours(name):
            continue
        name = final(name)
        record = {"description": r.get("description", ""), "utility": r.get("utility", ""),
                  "driver": r.get("driver", ""), "parent": final(r.get("parent", "")),
                  "members": [final(m.strip()) for m in r.get("calculation_meters", "").split(",") if m.strip()]}
        if name not in meters:
            meters[name] = {**record, "where": f"{sheet} row {number}"}
            continue
        kept = meters[name]
        for field, value in record.items():
            if value and not kept[field]:
                kept[field] = value
            elif value and kept[field] != value:
                report.note("Workbook rows that disagree (the first is kept)",
                            f"{name}: {field} {kept[field]!r} ({kept['where']}) vs {value!r} ({sheet} row {number})")

    points: dict[tuple, str] = {}
    for sheet, number, r in records("points"):
        name, instance = final(r.get("meter", "")), r.get("instance", "")
        if not ours(name) or not instance.isdigit():
            continue
        key = (name, r.get("period", ""), r.get("frequency", ""))
        if points.setdefault(key, instance) != instance:
            report.note("Workbook rows that disagree (the first is kept)",
                        f"{name} {key[1]} {key[2]} point: {points[key]} vs {instance} ({sheet} row {number})")

    # Reports: meter1…meter10 and their colours are read by position, as
    # the headers repeat (two "meter7"s).
    reports: list[dict] = []
    for sheet, rows in sheets.items():
        if kinds[sheet] != "reports":
            continue
        header = [c.strip().lower() for c in rows[0].cells]
        at = _header(rows)
        meter_cols = [i for i, h in enumerate(header) if re.fullmatch(r"meter\d+", h)]
        colour_cols = [i for i, h in enumerate(header) if re.fullmatch(r"meter\d+-colou?r", h)]
        for row in rows[1:]:
            name = row.cell(at["name"])
            if not name or not ours(name):
                continue
            get = lambda h: row.cell(at[h]) if h in at else ""
            outputs = [(final(row.cell(m)), row.cell(c) if c is not None else "")
                       for m, c in zip(meter_cols, colour_cols + [None] * len(meter_cols)) if row.cell(m)]
            reports.append({"name": name, "chart": get("chart"), "report": get("report"), "utility": get("utility"),
                            "period": get("period"), "breakup": get("breakup"),
                            "text_colour": get("text-color") or get("text-colour"), "meters": outputs,
                            "where": f"{sheet} row {row.number}"})
    return Workbook(prefix or "", meters, points, reports)


def _prefix(names: list[str]) -> str | None:
    """The "<prefix> -" most meter names start with, if one does."""
    counts = Counter(m.group(1) for n in names if (m := re.match(r"([A-Za-z0-9]{2,6})\s*-", n)))
    if counts:
        prefix, n = counts.most_common(1)[0]
        if n * 2 >= len(names):
            return prefix
    return None


# ─── The schedule ────────────────────────────────────────────────────────────
def sheet_utility(sheet: str, text: str) -> str:
    s = sheet.lower()
    if "elec" in s:
        return "electricity"
    if "gas" in s:
        return "gas"
    if "water" in s:
        return "water"
    if "heat" in s or "thermal" in s:
        t = text.lower()
        return "chw" if re.search(r"chw|cool|chill", t) else "lthw"
    return ""


def read_schedule(path: Path, settings: dict, level_of, report: Report) -> list[dict]:
    """The schedule's meter rows: {sheet, row, utility, meter_no, description,
    switchboard, tenant, location, level, core, load}."""
    spellings = {field: [compact(h) for h in names] for field, names in SCHEDULE_COLUMNS.items()}
    for field, header in settings["schedule_columns"].items():
        if field not in SCHEDULE_COLUMNS:
            raise SystemExit(f"{SETTINGS} schedule_columns: unknown field {field!r} — the fields are {', '.join(SCHEDULE_COLUMNS)}")
        spellings[field] = [compact(header)]
    out: list[dict] = []
    for sheet, rows in xlsx.read(path).items():
        start = _schedule_header(rows)
        if start is None:
            continue
        header = [compact(c) for c in rows[start].cells]
        columns = {field: next((i for i, h in enumerate(header) if h in names), None)
                   for field, names in spellings.items()}
        for row in rows[start + 1:]:
            if compact(row.cell(next(i for i, c in enumerate(row.cells) if c))) == "notes":
                break
            if row.filled() < 2:
                continue   # a section heading, e.g. a gateway's name
            r = {field: (row.cell(i) if i is not None else "") for field, i in columns.items()}
            if not r["meter_no"] and not r["description"]:
                continue
            text = " ".join(r[f] for f in ("meter_no", "description", "location"))
            out.append({**r, "sheet": sheet, "row": row.number,
                        "utility": sheet_utility(sheet, text), "level": level_of(text),
                        "core": core_of(r["location"]) or core_of(text),
                        "load": load_of(r["description"]) or load_of(r["meter_no"])})
    if not out:
        report.note("Schedule", f"{path.name}: no sheet with a Meter No. column")
    return out


# ─── The controller export ───────────────────────────────────────────────────
def read_controller(path: Path) -> dict[str, dict]:
    """The export's meters by tag: id, and base, type, parent_id, daily and
    monthly where it has the column."""
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            get = lambda *names: next((row[n] for n in names if row.get(n) and row[n].lower() != "n/a"), "")
            if not get("id"):
                continue
            tag = get("tag", "name")
            out[tag] = {"id": int(get("id")), "base": get("base"), "type": get("type"),
                        "parent_id": get("parent_id", "parent"), "daily": get("daily"), "monthly": get("monthly"),
                        "utility": get("utility")}
    return out


# ─── Building the data ───────────────────────────────────────────────────────
def prefill(site_root: Path, report: Report) -> dict:
    """The site's meters (read_csv's shape), levels, cores and tenants, from
    the documents in <site_root>/sources/, noting in `report` how."""
    sources = site_root / SOURCES
    settings = read_settings(sources)
    docs = find_sources(sources, settings)
    if not docs["workbook"] and not docs["controller"]:
        raise SystemExit(f"{site_data._rel(sources)}: no meters — put the building's import workbook "
                         "(or the controller's meter export) there")

    level_of = level_finder(settings["levels"])
    workbook = read_workbook(docs["workbook"], settings, report) if docs["workbook"] else Workbook()
    prefix, wb_meters, points = workbook.prefix, workbook.meters, workbook.points
    strip = (lambda tag: re.sub(rf"^{re.escape(prefix)}\s*-\s*", "", tag, flags=re.I)) if prefix else (lambda tag: tag)
    controller = read_controller(docs["controller"]) if docs["controller"] else {}
    schedule = read_schedule(docs["schedule"], settings, level_of, report) if docs["schedule"] else []

    # The meters: the controller's when there's an export, else the workbook's.
    # A workbook name finds its meter by compact(), spacing and case aside.
    if controller:
        tags = sorted(controller, key=lambda t: controller[t]["id"])
    else:
        tags = list(wb_meters)
        report.note("Provisional", f"no controller export: ids are numbered from first_id "
                                   f"{settings['first_id']} in workbook order, and no meter has a parent")
    tag_of = {compact(t): t for t in tags}
    for name in wb_meters:
        if compact(name) not in tag_of:
            report.note("In the workbook, not on the controller (left out)", name)
    wb_by_tag = {tag_of[compact(n)]: rec for n, rec in wb_meters.items() if compact(n) in tag_of}
    wb = lambda tag: wb_by_tag.get(tag, {})
    points = {(tag_of[compact(name)], period, frequency): instance
              for (name, period, frequency), instance in points.items() if compact(name) in tag_of}
    members = {t: [tag_of[compact(m)] for m in wb(t).get("members", []) if compact(m) in tag_of] for t in tags}

    # Schedule rows → meters: by name, then by (level, core, load).
    by_name: dict[str, str] = {compact(strip(t)): t for t in tags}
    by_parts: dict[tuple, list[str]] = defaultdict(list)
    for t in tags:
        parts = (level_of(strip(t)), core_of(t), load_of(strip(t)))
        if all(parts):
            by_parts[parts].append(t)
    sched: dict[str, dict] = {}
    for r in schedule:
        tag = how = None
        for name in (r["meter_no"], r["description"]):
            if name and (t := by_name.get(compact(name))):
                tag, how = t, "name"
                break
        if tag is None:
            for name in (r["meter_no"], r["description"]):
                hits = [t for k, t in by_name.items() if len(k) >= 6 and compact(name).endswith(k)]
                if len(hits) == 1:
                    tag, how = hits[0], "name"
                    break
        if tag is None and len(by_parts.get((r["level"], r["core"], r["load"]), [])) == 1:
            tag, how = by_parts[(r["level"], r["core"], r["load"])][0], "level, core and load"
        if tag is None:
            report.note("Schedule rows matched to no meter", f"{r['sheet']} row {r['row']}: "
                        + " | ".join(x for x in (r["meter_no"], r["description"], r["location"]) if x))
            continue
        if tag in sched:
            report.note("Schedule rows matched to a meter twice (the first is kept)",
                        f"{tag}: {sched[tag]['sheet']} row {sched[tag]['row']} and {r['sheet']} row {r['row']}")
            continue
        sched[tag] = r
        report.source("schedule match", how)

    # Tenants: the schedule's names, short names by the settings or with the
    # legal words dropped.
    landlord = {compact(n) for n in settings["landlord"]}
    proper_names = []
    for r in sorted(schedule, key=lambda r: level_rank(r["level"]) if r["level"] else (9999, "")):
        name = r["tenant"]
        if name and compact(name) not in landlord and name not in proper_names:
            proper_names.append(name)
    short = {name: str((settings["tenants"].get(name) or {}).get("short") or short_name(name)) for name in proper_names}
    for name in settings["tenants"]:
        if name not in short:
            report.note("prefill.yaml tenants not in the schedule", name)
    catalog: dict[str, str] = {}   # short name → the first proper name given it
    for name in proper_names:
        if catalog.setdefault(short[name], name) != name:
            report.note("Tenants merged by their short name (the first name is kept)",
                        f"{short[name]}: {catalog[short[name]]!r} and {name!r}")
    for a in catalog:
        for b in catalog:
            if a != b and compact(a) in compact(b):
                report.note("Tenant names that look alike (give both one short name in prefill.yaml tenants: "
                            "if they're one tenant)", f"{catalog[a]!r} and {catalog[b]!r}")
    tenant_of = lambda name: short.get(name, "")

    # Levels: a meter's own (schedule, then name); a calculation meter's is its
    # members' when they agree, and its members without one take it.
    def own_level(t: str) -> str:
        return (sched[t]["level"] if t in sched and sched[t]["level"] else "") or level_of(strip(t))
    level = {t: own_level(t) for t in tags if not members[t]}
    for _ in range(3):
        for t in tags:
            if members[t]:
                found = {level[m] for m in members[t] if level.get(m)}
                level[t] = found.pop() if len(found) == 1 else own_level(t)
                for m in members[t]:
                    if level[t] and not level.get(m):
                        level[m] = level[t]
    # A meter goes on its level's page with evidence it belongs there: a
    # calculation meter on the level (or one of its members), a schedule row
    # in a core, or a core in its name. A calculation meter the workbook
    # doesn't list (made on the controller) is a level's when its name gives
    # the level and says it's a total.
    def is_calc(t: str) -> bool:
        kind = controller.get(t, {}).get("type") or settings["types"].get(wb(t).get("driver", ""), "")
        return generate_meter_registry.normalise_type(kind) == "Calculation"
    level_calcs = {t for t in tags if members[t] and level.get(t)}
    level_calcs |= {t for t in tags if not members[t] and level.get(t) and is_calc(t) and "total" in t.lower()}
    in_calc = {m for t in level_calcs for m in members[t]}
    placed: dict[str, tuple[str, str]] = {}   # tag → (level, core or "")
    for t in tags:
        lv = level.get(t, "")
        if not lv:
            continue
        core = (sched[t]["core"] if t in sched else "") or core_of(t)
        if t in level_calcs:
            placed[t] = (lv, "")
            report.source("floor", "calculation meters")
        elif t in in_calc or core:
            placed[t] = (lv, core or settings["default_core"])
            report.source("floor", "schedule core" if t in sched and sched[t]["core"] else
                          "core in name" if core else "calculation members")
        else:
            report.note("Named for a level but not placed (add it in prefill.yaml meters: if it belongs on a page)",
                        f"{t} → {lv}")

    # Cores per level, and the tenant holding each, from the schedule.
    cores: dict[str, dict[str, str]] = defaultdict(dict)
    votes: dict[tuple, Counter] = defaultdict(Counter)
    for r in schedule:
        if r["level"] and r["core"] and r["tenant"] and compact(r["tenant"]) not in landlord:
            votes[(r["level"], r["core"])][tenant_of(r["tenant"])] += 1
    for (lv, core), counts in votes.items():
        cores[lv][core] = counts.most_common(1)[0][0]
        if len(counts) > 1:
            report.note("Cores the schedule gives more than one tenant (the most common is kept)",
                        f"{lv} {core}: " + ", ".join(f"{n} ×{c}" for n, c in counts.most_common()))

    # The rows, in read_csv's shape.
    total_function = (site_data.FLOOR_PAGE.get("summary_cards") or {}).get("total", "")
    by_tag_id: dict[str, int] = {}
    rows: list[dict] = []
    for i, t in enumerate(tags):
        c, w = controller.get(t, {}), wb(t)
        if c:
            meter_id = c["id"]
            report.source("id", "controller")
        else:
            meter_id = settings["first_id"] + i
            report.source("id", "provisional")
        by_tag_id[t] = meter_id
        row = {"id": meter_id, "tag": t}
        if c.get("base"):
            row["base"] = int(c["base"])
            report.source("base", "controller")
        else:
            row["base"] = (meter_id + 99) * 100
            report.source("base", "(id + 99) × 100")
        if c.get("type"):
            row["type"] = c["type"]
            report.source("type", "controller")
        elif w.get("driver"):
            row["type"] = settings["types"].get(w["driver"], w["driver"])
            report.source("type", "workbook")
        else:
            row["type"] = ""
        row["type"] = generate_meter_registry.normalise_type(row["type"])
        for field in ("daily", "monthly"):
            spec = settings["points"][field]
            if c.get(field):
                row[field] = int(c[field])
                report.source(field, "controller")
            elif (p := points.get((t, spec["period"], spec["frequency"]))):
                row[field] = int(p)
                report.source(field, "workbook points")
            else:
                row[field] = 0
        lv, core = placed.get(t, ("", ""))
        row.update(floor=lv, zone=core, column=None, position=None)
        is_total = t in level_calcs and "total" in t.lower()
        row["function"] = total_function if is_total and total_function else strip(t)
        utility = c.get("utility") or settings["utility_codes"].get(w.get("utility", ""), "") \
            or (sched[t]["utility"] if t in sched else "")
        if w.get("utility") and w["utility"] not in settings["utility_codes"]:
            report.note("Workbook utility codes prefill.yaml utility_codes doesn't name", f"{t}: {w['utility']}")
        row["utility"] = generate_meter_registry.normalise_utility(utility, row["function"], site_data.UTILITIES) \
            if utility else ""
        report.source("utility", "controller" if c.get("utility") else "workbook" if w.get("utility") in settings["utility_codes"]
                      else "schedule" if utility else "none")
        inherited = cores.get(lv, {}).get(core, "") if core else _floor_tenant(cores.get(lv, {})) if lv else ""
        row["tenant"] = tenant_of(sched[t]["tenant"]) if t in sched and sched[t]["tenant"] else inherited
        if t in sched and sched[t]["tenant"]:
            report.source("tenant", "schedule")
        row["tenant_display"] = bool(row["tenant"]) and bool(settings["tenant_display"])
        row["main_display"] = True
        row["_parent"] = c.get("parent_id", "") or w.get("parent", "")
        rows.append(row)

    # Parents: the export's (an id), or the workbook's (a meter name).
    for row in rows:
        parent = row.pop("_parent")
        if not parent:
            row["parent_id"] = None
        elif parent.isdigit():
            row["parent_id"] = int(parent)
            report.source("parent", "controller")
        elif parent in by_tag_id:
            row["parent_id"] = by_tag_id[parent]
            report.source("parent", "workbook")
        else:
            row["parent_id"] = None
            report.note("Parents that are no meter", f"{row['tag']}: {parent}")

    # A calculation meter on a level with no tenant of its own takes its
    # members' when they agree: a floor's East side, held by one tenant.
    by_tag = {r["tag"]: r for r in rows}
    for _ in range(2):
        for t in level_calcs:
            row = by_tag[t]
            found = {by_tag[m]["tenant"] for m in members[t] if m in by_tag}
            if not row["tenant"] and len(found) == 1 and (tenant := found.pop()):
                row["tenant"], row["tenant_display"] = tenant, bool(settings["tenant_display"])
                report.source("tenant", "calculation members")

    _apply_corrections(rows, settings, by_tag_id, cores, report)

    # Columns and positions: a core's column from the settings or its compass
    # word; its meters lighting, then power, then mechanical, each in id order.
    load_rank = {name: i for i, (name, _) in enumerate(LOADS[1:] + LOADS[:1])}
    for row in rows:
        if row["floor"] and row["zone"] and row["column"] is None:
            row["column"] = int(settings["columns"].get(row["zone"], _compass_column(row["zone"])))
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if row["floor"] and row["zone"]:
            groups[(row["floor"], row["zone"])].append(row)
    for group in groups.values():
        ordered = sorted(group, key=lambda r: (r["position"] is None, r["position"] or 0,
                                               load_rank.get(load_of(strip(r["tag"])), 9), r["id"]))
        taken = {r["position"] for r in group if r["position"] is not None}
        n = 0
        for r in ordered:
            if r["position"] is None:
                while n in taken:
                    n += 1
                r["position"] = n
                taken.add(n)

    # Levels, bottom → top: those with meters get a page; those with only
    # cores don't. A key of the site's own sits below the roof.
    meter_levels = {r["floor"] for r in rows if r["floor"]}
    order = sorted(meter_levels | set(cores) | set(settings["levels"]), key=level_rank)
    for lv in order:
        if lv not in meter_levels:
            report.note("Levels with no meters (no page)", f"{lv}: cores {cores.get(lv) or {}}")

    _check_site(rows, report)
    rows_by_tag = {r["tag"]: r for r in rows}
    report_level = lambda t: rows_by_tag[t]["floor"] or level.get(t, "") if t in rows_by_tag else ""
    reports = draft_reports(workbook.reports, tag_of, rows_by_tag, report_level, level_of, strip,
                            meter_levels, settings, report)
    return {"rows": rows, "cores": dict(cores), "order": order, "meter_levels": meter_levels, "reports": reports,
            "tenants": list(catalog.items()), "settings": settings, "docs": docs,
            "prefix": prefix, "schedule": schedule}


def _floor_tenant(cores: dict[str, str]) -> str:
    tenants = set(cores.values())
    return tenants.pop() if len(tenants) == 1 else ""


def _compass_column(core: str) -> int:
    word = core.split()[0].lower() if core else ""
    return COMPASS_COLUMNS.get(word, 0)


LEGAL_WORDS = {"limited", "ltd", "llp", "plc", "inc", "llc", "uk", "u.k.", "group", "services", "company",
               "co", "international", "europe", "management", "holdings"}


def short_name(proper: str) -> str:
    """A tenant's short name: its proper name without the legal words, at
    most three words, none of them a dangling "and"."""
    words = [w for w in re.split(r"\s+", proper.strip()) if w.lower().strip(",.()") not in LEGAL_WORDS][:3]
    while words and words[-1].lower() in ("and", "&", "of", "the"):
        words.pop()
    return " ".join(words) or proper.strip()


def _apply_corrections(rows: list[dict], settings: dict, ids: dict[str, int],
                       cores: dict[str, dict[str, str]], report: Report) -> None:
    """prefill.yaml `meters: {<tag>: {<field>: value}}`, last. A meter moved
    to another level or core takes the tenant there, unless `tenant:` says."""
    by_tag = {r["tag"]: r for r in rows}
    fields = {"id", "base", "type", "daily", "monthly", "parent", "floor", "core", "column", "position",
              "function", "utility", "tenant", "tenant_display", "main_display"}
    for tag, fix in settings["meters"].items():
        row = by_tag.get(tag)
        if row is None:
            report.note("prefill.yaml meters that are no meter", tag)
            continue
        for field, value in (fix or {}).items():
            if field not in fields:
                raise SystemExit(f"{SETTINGS} meters '{tag}': unknown field {field!r} — the fields are {', '.join(sorted(fields))}")
            if field == "parent":
                row["parent_id"] = ids.get(value, value) if value is not None else None
            elif field == "core":
                row["zone"] = value or ""
            elif field == "floor":
                row["floor"] = value or ""
                if not value:
                    row["zone"], row["column"], row["position"] = "", None, None
            else:
                row[field] = value
            report.source({"core": "zone"}.get(field, field), "prefill.yaml")
        if {"floor", "core"} & set(fix or {}) and "tenant" not in (fix or {}):
            level_cores = cores.get(row["floor"], {})
            row["tenant"] = level_cores.get(row["zone"], "") if row["zone"] else _floor_tenant(level_cores)
            row["tenant_display"] = bool(row["tenant"]) and bool(settings["tenant_display"])


def _check_site(rows: list[dict], report: Report) -> None:
    """The utilities and meter types the meters need that site.yaml lacks."""
    missing = sorted({r["utility"].lower() for r in rows if r["utility"]} - set(site_data.UTILITIES))
    if missing:
        kinds = {"electricity": "electric", "chw": "thermal", "lthw": "thermal", "lphw": "thermal"}
        labels = {"chw": "CHW", "lthw": "LTHW", "lphw": "LPHW"}
        report.note("site.yaml utilities to add",
                    "; ".join(f"{u}: {{label: {labels.get(u, u.capitalize())}, kind: {kinds.get(u, 'other')}}}" for u in missing))
        for r in rows:   # as they'll read once site.yaml has them
            r["utility"] = r["utility"].lower()
    types = sorted({r["type"] for r in rows if r["type"]} - set(site_data.BACNET.get("power_offset", {})))
    if types:
        report.note("site.yaml bacnet.power_offset: meter types with no offset", ", ".join(types))


# ─── Reports ─────────────────────────────────────────────────────────────────
# A report card's chart is the controller's UtilityReport.png, drawn from the
# workbook's Reports row: its meters and their colours, chart and report
# type, utility, period and text colour. The rest is the house style.
CHART_PATH = "/images/dynamic/UtilityReport.png"
CHART_UNITS = {   # customUnits[0..5], by report type (and a thermal demand's)
    "demand": ["48", "", "", "48", "", ""],
    "thermal demand": ["", "", "", "48", "", ""],
    "consumption": ["19", "80", "521", "19", "", ""],
}
TITLE_STYLES = (("mainTitleStyle", "26", "true"), ("subTitleStyle", "16", "false"), ("xaxisStyle", "12", "false"),
                ("yaxisStyle", "12", "false"), ("keyStyle", "14", "false"))
REPORT_TYPES = ("demand", "consumption")


def rgb(colour: str, default: str) -> str:
    """"#097234" as "rgb(9, 114, 52)"; `default` for anything else."""
    m = re.fullmatch(r"#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})", colour.strip(), re.I)
    return f"rgb({', '.join(str(int(x, 16)) for x in m.groups())})" if m else default


def chart_url(cache_id: int, outputs: list[tuple[int, str, str]], chart: str, report_type: str, utility_type: str,
              text_colour: str, period: tuple[str, str], interval: str, units: list[str]) -> str:
    """The chart's URL: `outputs` are (meter id, label, colour) and `period`
    (timePeriod, thisTimeScale), e.g. ("THIS", "WEEK")."""
    params: list[tuple[str, object]] = [("cacheId", cache_id), ("is2D", "true")]
    for i, (meter_id, label, colour) in enumerate(outputs):
        params += [(f"energylogOutputs[{i}].meterId", meter_id), (f"energylogOutputs[{i}].label", label),
                   (f"energylogOutputs[{i}].parameter", 0), (f"energylogOutputs[{i}].colour", colour)]
    params += [("showChartTitle", "true"), ("chartTitle", "default"), ("showChartSubTitle", "true"),
               ("chartSubTitle", "default"), ("displayLegend", "true"), ("vAlignment", "bottom"),
               ("hAlignment", "center")]
    params += [(f"{part}Colour", text_colour) for part in ("headingText", "domainAxis", "rangeAxis", "legendText")]
    params += [("legendBackgroundColour", "rgba(0, 0, 0, 0)"), ("plotBackgroundColour", "rgba(0, 0, 0, 0)"),
               ("hierarchyLevel", 0), ("timeSpan.progressive", "true"), ("timeSpan.timeScaleSteps", 0),
               ("timeSpan.intervalTimePeriod", interval), ("timeSpan.timePeriod", period[0]),
               ("timeSpan.thisTimeScale", period[1]), ("timeSpan.firstDayOfWeek", 2),
               ("startFromCommissioningDate", "false")]
    params += [(f"customUnits[{i}]", unit) for i, unit in enumerate(units)]
    params += [("previousSteps", ""), ("previousYearSteps", "")]
    for style, size, bold in TITLE_STYLES:
        params += [(f"{style}.usesDefault", "true"), (f"{style}.name", "DejaVu Sans"), (f"{style}.size", size),
                   (f"{style}.isBold", bold), (f"{style}.isItalic", "false")]
    params += [("showXAxis", "true"), ("xAxisLabelRotate", 1), ("yAxisLabelRotate", 0), ("xAxisAbbrLabel", "true"),
               ("showYAxis", "true"), ("chartType", f"chart-{chart}"), ("reportType", f"report-{report_type}"),
               ("utilityType", utility_type), ("width", 1600), ("height", 400)]
    return CHART_PATH + "?" + "&".join(f"{k}={quote(str(v), safe='()')}" for k, v in params)


def draft_reports(sheet: list[dict], tag_of: dict[str, str], rows: dict[str, dict], level_of_meter, level_of,
                  strip, page_levels: set[str], settings: dict, report: Report) -> dict:
    """reports.yaml's {urls, placements}: a card per Reports row on its
    level's floor page, in the floor tab of its utility. A row's level is
    where its meters are (the name's when they're on none); a part of its
    name besides the level, utility and report type (East, West) titles it.
    The site's own `reports:` from the settings go after."""
    tabs = {t["slot"] for t in site_data.FLOOR_PAGE.get("tabs") or []}
    urls: dict[str, str] = {}
    placements: list[dict] = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    first_id = settings["first_report_id"]
    for n, r in enumerate(sheet):
        name = r["name"]
        outputs, missing = [], []
        for meter, colour in r["meters"]:
            tag = tag_of.get(compact(meter))
            if tag is None:
                missing.append(meter)
            else:
                outputs.append((tag, colour))
        if missing:
            report.note("Report meters that are no meter (left out of the chart)", f"{name}: {', '.join(missing)}")
        if not outputs:
            report.note("Reports with no meter (no card)", name)
            continue
        levels = {level_of_meter(t) for t, _ in outputs} - {""}
        lv = levels.pop() if len(levels) == 1 else level_of(strip(name))
        if lv not in page_levels:
            report.note("Reports on no floor page (no card)", f"{name}" + (f" → {lv}" if lv else ""))
            continue
        report_type = r["report"].strip().lower()
        utility = generate_meter_registry.normalise_utility(r["utility"], "", site_data.UTILITIES).lower()
        spec = site_data.UTILITIES.get(utility, {"label": r["utility"], "kind": "other"})
        if report_type not in REPORT_TYPES or not utility:
            report.note("Reports of a kind prefill doesn't draw (no card)", f"{name}: {r['report']!r} {r['utility']!r}")
            continue
        if utility not in tabs:
            report.note("Floor-page tabs to add in site.yaml floor_page.tabs (the cards' slot)", utility)
        parts = [p.strip() for p in re.split(r"\s+-\s+", strip(name))]
        qualifier = " ".join(p for p in parts if not level_of(p) and compact(p) not in
                             {compact(utility), compact(spec["label"]), report_type})
        period = re.fullmatch(r"(this|previous|last)-(\w+)", r["period"].strip().lower()) if r["period"] else None
        if not period:
            report.note("Report periods read as this-week", f"{name}: {r['period']!r}")
        thermal = spec["kind"] == "thermal"
        image_ref = "_".join(x for x in ("floor", lv, utility, compact(qualifier), report_type) if x)
        text = rgb(r["text_colour"], "rgb(43, 43, 42)")
        urls[image_ref] = chart_url(
            len(urls) + 1, [(rows[t]["id"], strip(t), rgb(c, "rgb(9, 114, 52)")) for t, c in outputs],
            r["chart"].strip().lower() or ("area" if report_type == "demand" else "bar"), report_type,
            "fluid energy" if thermal else utility, text,
            (period.group(1).upper(), period.group(2).upper()) if period else ("THIS", "WEEK"),
            (r["breakup"] or "Auto").upper(), CHART_UNITS["thermal demand" if thermal and report_type == "demand"
                                                          else report_type])
        card = {"image_ref": image_ref, "alt": f"📊 {spec['label']} {report_type.capitalize()}",
                "page": "floor", "slot": utility, "floor": lv}
        if name in settings["report_ids"]:
            card = {"id": settings["report_ids"][name], **card}
            report.source("report id", "prefill.yaml")
        elif first_id is not None:
            card = {"id": first_id + n, **card}
            report.source("report id", "first_report_id")
        if qualifier:
            card["title"] = f"{qualifier} {report_type.capitalize()}"
        groups[(lv, utility)].append({**card, "_order": (bool(qualifier), n)})
        report.source("report", "workbook")
    for name in settings["report_ids"]:
        if not any(r["name"] == name for r in sheet):
            report.note("prefill.yaml report_ids that are no report", name)
    # Positions within a floor tab: the floor's own reports, then each side's, in sheet order.
    for group in groups.values():
        for position, card in enumerate(sorted(group, key=lambda c: c["_order"])):
            placements.append({**{k: v for k, v in card.items() if k not in ("_order", "floor", "title")},
                               "position": position, "floor": card["floor"],
                               **({"title": card["title"]} if "title" in card else {})})
    own = settings["reports"] or {}
    urls.update(own.get("urls") or {})
    placements += own.get("placements") or []
    return {"urls": urls, "placements": placements}


# ─── Floorplans ──────────────────────────────────────────────────────────────
# Each level with a page shows img/floors/floor_<key>.png (site/assets/), its
# floor and tenant pages alike. A drawing in sources/floorplans/ is named for
# its level ("Ninth_Floor.emf", "L3.svg", "…-Fifth.pdf"); a PNG is copied,
# anything else converted with the first tool installed for it.
FLOORPLAN_FORMATS = (".png", ".svg", ".pdf", ".emf", ".wmf", ".jpg", ".jpeg")   # preferred first
CONVERTERS = {   # suffix: [(tool, command)], {src} and {out} filled in; the first installed is used
    ".pdf": [("pdftoppm", ["pdftoppm", "-png", "-singlefile", "-scale-to", "2400", "{src}", "{out_stem}"])],
    ".svg": [("inkscape", ["inkscape", "{src}", "--export-type=png", "--export-width=2400", "--export-filename={out}"]),
             ("rsvg-convert", ["rsvg-convert", "-w", "2400", "-o", "{out}", "{src}"]),
             ("magick", ["magick", "{src}", "{out}"])],
    ".emf": [("inkscape", ["inkscape", "{src}", "--export-type=png", "--export-width=2400", "--export-filename={out}"]),
             ("soffice", ["soffice", "--headless", "--convert-to", "png", "--outdir", "{out_dir}", "{src}"])],
    ".jpg": [("magick", ["magick", "{src}", "{out}"]), ("convert", ["convert", "{src}", "{out}"])],
}
CONVERTERS[".wmf"] = CONVERTERS[".emf"]
CONVERTERS[".jpeg"] = CONVERTERS[".jpg"]
INSTALL_HINT = {".pdf": "poppler-utils", ".svg": "inkscape", ".emf": "inkscape", ".wmf": "inkscape",
                ".jpg": "imagemagick", ".jpeg": "imagemagick"}


def plan_floorplans(folder: Path, level_of, page_levels: set[str], report: Report) -> dict[str, Path]:
    """{level: drawing}: a page level's drawing in `folder`, by its file name."""
    found: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in FLOORPLAN_FORMATS:
            continue
        stem = re.sub(r"[_-]+", " ", path.stem).strip()
        lv = level_of(stem) or (_level("number", m) if (m := re.fullmatch(r"L\s*0*(\d{1,2})", stem, re.I)) else "")
        if not lv:
            report.note("Drawings named for no level (not used)", path.name)
        elif lv not in page_levels:
            report.note("Drawings for a level with no page (not used)", f"{path.name} → {lv}")
        else:
            found[lv].append(path)
    plan = {}
    for lv, paths in found.items():
        paths.sort(key=lambda p: (FLOORPLAN_FORMATS.index(p.suffix.lower()), p.name))
        plan[lv] = paths[0]
        if len(paths) > 1:
            report.note("Levels with more than one drawing (the first is used: PNG, SVG, PDF, EMF, then JPEG)",
                        f"{lv}: " + ", ".join(p.name for p in paths))
    for lv in sorted(page_levels - set(plan), key=level_rank):
        report.note("Levels with no drawing", lv)
    return plan


def make_floorplan(src: Path, out: Path) -> str | None:
    """Write `src` to `out` as a PNG; None, or why it couldn't."""
    suffix = src.suffix.lower()
    out.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".png":
        shutil.copyfile(src, out)
        return None
    tools = [(tool, cmd) for tool, cmd in CONVERTERS[suffix] if shutil.which(tool)]
    if not tools:
        return f"needs a converter: sudo apt install {INSTALL_HINT[suffix]}"
    tool, cmd = tools[0]
    with tempfile.TemporaryDirectory() as tmp:
        made = Path(tmp) / (src.stem + ".png")
        fill = {"{src}": str(src), "{out}": str(made), "{out_stem}": str(made.with_suffix("")), "{out_dir}": tmp}
        args = [next((arg.replace(k, v) for k, v in fill.items() if k in arg), arg) for arg in cmd]
        run = subprocess.run(args, capture_output=True, text=True, timeout=300)
        if run.returncode != 0 or not made.exists():
            return f"{tool} failed: {(run.stderr or run.stdout).strip()[:200]}"
        shutil.copyfile(made, out)
    return None


# ─── Writing ─────────────────────────────────────────────────────────────────
HEADERS = {
    "floors.yaml": "Levels bottom → top, with the tenant holding each core (from the schedule).",
    "meters.yaml": "Every meter, by level → core (README \"data/meters.yaml\").",
    "tenants.yaml": "The tenant catalog: short name → proper name (from the schedule).",
    "reports.yaml": "Report cards: each chart's URL, and where its card goes (from the workbook's Reports).",
}


def _with_mark(name: str, body: str) -> str:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    return (f"{MARK} {digest} — written by _build/prefill.py from {SOURCES}/. Make changes in\n"
            f"# {SOURCES}/{SETTINGS}, not here: a re-run replaces this file.\n"
            f"# {HEADERS[name]}\n" + body)


def _marked_intact(text: str) -> bool:
    """Whether `text` is a file prefill wrote, unedited since."""
    lines = text.split("\n", 3)
    if len(lines) < 4 or not lines[0].startswith(MARK):
        return False
    digest = lines[0][len(MARK):].split()[0]
    return hashlib.sha256(lines[3].encode("utf-8")).hexdigest()[:12] == digest


def target_path(name: str) -> Path:
    """The site's data/<name>, or where a new one goes: numbered."""
    existing = site_data.data_path(name)
    if existing.exists():
        return existing
    return site_data.DATA_DIR / f"{site_data.DATA_FILES.index(name):02d}_{name}"


def floors_text(result: dict) -> str:
    settings = result["settings"]
    out = []
    for lv in result["order"]:
        spec = {k: v for k, v in (settings["levels"].get(lv) or {}).items() if k != "match"}
        entry = {"label": spec.pop("label", level_label(lv))}
        if lv not in result["meter_levels"]:
            entry["page"] = False
        if result["cores"].get(lv):
            entry["cores"] = dict(sorted(result["cores"][lv].items()))
        entry.update(spec)
        out.append(yaml.safe_dump({f"floor_{lv}": entry}, sort_keys=False, allow_unicode=True, width=120))
    return "\n".join(out)


def tenants_text(result: dict) -> str | None:
    if not result["tenants"]:
        return None
    settings = result["settings"]["tenants"]
    catalog = {}
    for short, proper in result["tenants"]:
        extra = {k: v for k, v in (settings.get(proper) or {}).items() if k != "short"}
        catalog[short] = {"name": proper, "index": {}, **extra}
    return yaml.safe_dump({"tenants": catalog}, sort_keys=False, allow_unicode=True, width=120)


def reports_text(result: dict) -> str | None:
    reports = result["reports"]
    if not reports["urls"] and not reports["placements"]:
        return None
    out = ["urls:\n"]
    out += [f"  {name}: {json.dumps(url)}\n" for name, url in reports["urls"].items()]
    out.append("\nplacements:\n")
    out += ["  - " + yaml.safe_dump(p, default_flow_style=True, allow_unicode=True, sort_keys=False, width=1000)
            for p in reports["placements"]]
    return "".join(out)


def meters_text(result: dict) -> str:
    text = meters_yaml.dump(result["rows"], result["cores"], result["order"])
    with tempfile.TemporaryDirectory() as tmp:
        check = Path(tmp) / "meters.yaml"
        check.write_text(text, encoding="utf-8")
        back = meters_yaml.read(check, site_data.UTILITIES, result["cores"])
    expected = sorted(({k: v for k, v in r.items()} for r in result["rows"]), key=lambda r: r["id"])
    if back != expected:
        ids = [a["id"] for a, b in zip(back, expected) if a != b][:12]
        raise SystemExit(f"the meters YAML wouldn't read back as built (meter ids {ids}) — nothing written")
    return text


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Prefill a site's floors, meters and tenants from its documents.")
    ap.add_argument("--site", type=Path, default=site_data.DEFAULT_SITE_ROOT, help="site directory (default: site/)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be written; write nothing")
    ap.add_argument("--replace", action="store_true", help="overwrite data files prefill didn't write, or that were edited")
    args = ap.parse_args(argv)

    site_data.configure(args.site, site_data.DEFAULT_OUT_ROOT)
    report = Report()
    result = prefill(site_data.SITE_ROOT, report)
    _check_site_utilities_first(report)
    outputs = {"floors.yaml": floors_text(result), "meters.yaml": meters_text(result),
               "tenants.yaml": tenants_text(result), "reports.yaml": reports_text(result)}

    files, blocked = [], []
    for name, body in outputs.items():
        path = target_path(name)
        if body is None:
            files.append(f"{name}: nothing to write (no " + ("tenants in the schedule)" if name == "tenants.yaml"
                                                             else "Reports sheet in the workbook)"))
            continue
        text = _with_mark(name, body)
        rel = site_data._rel(path)
        if not path.exists():
            files.append(f"{rel}: new")
        else:
            old = path.read_text(encoding="utf-8")
            if old == text:
                files.append(f"{rel}: unchanged")
                outputs[name] = None
                continue
            diff = list(difflib.unified_diff(old.splitlines(), text.splitlines(), lineterm="", n=0))
            added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
            removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
            if not _marked_intact(old) and not args.replace:
                blocked.append(f"{rel}: not written by prefill, or edited since — move the edits to "
                               f"{SOURCES}/{SETTINGS}, or pass --replace")
                outputs[name] = None
                continue
            files.append(f"{rel}: replaced, +{added} −{removed} lines")
        outputs[name] = (path, text)
    meters_csv = site_data.data_path("meters.csv")
    if meters_csv.exists() and outputs.get("meters.yaml"):
        if not args.replace:
            blocked.append(f"{site_data._rel(meters_csv)}: the site's meters are a CSV — pass --replace to write "
                           "meters.yaml, then delete the CSV (the build won't read both)")
            outputs["meters.yaml"] = None
        else:
            files.append(f"now delete {site_data._rel(meters_csv)}: the build won't read both")

    folder = site_data.SITE_ROOT / SOURCES / result["settings"]["floorplans"]
    floorplans = plan_floorplans(folder, level_finder(result["settings"]["levels"]), result["meter_levels"], report) \
        if folder.is_dir() else {}
    pending: dict[Path, Path] = {}
    for lv, src in sorted(floorplans.items(), key=lambda item: level_rank(item[0])):
        out = site_data.SITE_ROOT / "assets" / site_data.default_floorplan_image(lv)
        rel = site_data._rel(out)
        if out.exists() and not args.replace:
            files.append(f"{rel}: kept (pass --replace to make it again from {src.name})")
        else:
            files.append(f"{rel}: {'replaced' if out.exists() else 'new'}, from {src.name}")
            pending[out] = src

    print(f"Sources: " + ", ".join(f"{k} {p.name}" for k, p in result["docs"].items() if p)
          + (f"; building prefix {result['prefix']!r}" if result["prefix"] else ""))
    print(f"Meters: {len(result['rows'])}, {sum(1 for r in result['rows'] if r['floor'])} on a level page; "
          f"levels: {', '.join(result['order']) or 'none'}; tenants: {len(result['tenants'])}\n")
    files += [f"NOT WRITTEN {b}" for b in blocked]
    print(report.text(files))
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    (site_data.SITE_ROOT / SOURCES / REPORT).write_text(report.text(files, limit=None) + "\n", encoding="utf-8")
    for name, out in outputs.items():
        if out:
            path, text = out
            path.write_text(text, encoding="utf-8", newline="\n")
    for out, src in pending.items():
        if problem := make_floorplan(src, out):
            print(f"  {site_data._rel(out)}: not made from {src.name} — {problem}")
            blocked.append(f"{site_data._rel(out)}: {problem}")
    print("\nNext: build.py --check")
    return 1 if blocked else 0


def _check_site_utilities_first(report: Report) -> None:
    """Stop before writing meters that site.yaml can't read."""
    if report.notes.get("site.yaml utilities to add"):
        print(report.text([]))
        raise SystemExit(f"\nadd these to {site_data._rel(site_data.BUILDING_FILE)} `utilities:` first: "
                         + report.notes["site.yaml utilities to add"][0])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
