"""
The site's meters as YAML, laid out the way the building is: level → core
→ meter. It reads into the same normalised rows as meters.csv
(generate_meter_registry.read_csv), so every page builder and the runtime's
METER_REGISTRY see no difference; dump() writes those rows back out, which is
how _build/import_meters.py turns a meters.csv export into this file.

    columns: {East: 0, North: 1, West: 2}   # floor-page column of each core's card

    floor_25th:                  # a level from floors.yaml
      floor:                     # meters outside the cores (floor totals, …)
        - {id: 561, tag: "Floor 25 - Total Electricity", base: 66000, type: Calculation,
           function: Floor Total Electricity, utility: electricity}
      West:                      # a core: the meters on its floor-page card, in order
        - {id: 301, tag: "DB/T/25/W1", base: 38000, type: Modbus, parent: 266,
           function: Lighting, utility: electricity, tenant_display: yes}

    unplaced:                    # meters on no level (site totals, gas/water incomers)
        - {id: 633, …}

Meter fields: id and base (required, whole numbers); tag; type; daily and
monthly (default 0); parent (the parent meter's id, 0 for a hierarchy root;
default: not in the hierarchy); function; utility (a site.yaml utility code
or label, optionally -virtual); tenant; tenant_display (default no);
main_display (default yes). In a core only: column (default the core's
`columns:` entry) and position (default one after the meter above it, 0 for
the first). also_on: [<level>, …] puts the meter on further levels' pages
too, in the same core and position.

A meter's tenant defaults to whoever holds its core (floors.yaml `cores:`);
a meter outside the cores defaults to the level's tenant when every core
listed on the level is one tenant's. Write `tenant: null` for none.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

import generate_meter_registry as registry

OUTSIDE = "floor"        # a level's group of meters outside its cores
UNPLACED = "unplaced"    # top-level list of meters on no level
COLUMNS = "columns"      # top-level {core: floor-page column}
LEVEL_PREFIX = "floor_"
FIELDS = ("id", "tag", "base", "type", "daily", "monthly", "parent", "function", "utility",
          "tenant", "tenant_display", "main_display", "column", "position", "also_on")
CORE_ONLY = ("column", "position")


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys, which would
    otherwise silently drop a level or core."""

    def construct_mapping(self, node, deep=False):
        seen: set = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


def _floor_tenant(cores: dict[str, str]) -> str:
    """A level's tenant: the one tenant every listed core names, else none."""
    tenants = set(cores.values())
    return tenants.pop() if len(tenants) == 1 else ""


# ─── Reading ─────────────────────────────────────────────────────────────────

def read(path: Path, utilities: dict[str, dict], cores: dict[str, dict[str, str]]) -> list[dict]:
    """The meters in `path` as normalised rows (read_csv's shape), in id
    order. `utilities` is site.yaml's catalog; `cores` is each level's
    {core: tenant short name} from floors.yaml."""
    name = path.name
    try:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader) or {}  # noqa: S506 (SafeLoader subclass)
    except yaml.YAMLError as e:
        raise SystemExit(f"{name}: {e}")
    if not isinstance(doc, dict):
        raise SystemExit(f"{name}: expected `{COLUMNS}:`, `floor_<key>:` levels and `{UNPLACED}:`")

    columns = doc.get(COLUMNS) or {}
    if not isinstance(columns, dict):
        raise SystemExit(f"{name}: `{COLUMNS}:` must map each core to its floor-page column")
    rows: list[dict] = []
    for key, value in doc.items():
        key = str(key)
        if key == COLUMNS:
            continue
        if key == UNPLACED:
            for entry in _meter_list(value, f"{name} `{UNPLACED}:`"):
                rows.append(_row(entry, f"{name} `{UNPLACED}:`", utilities, floor="", zone="",
                                 tenant="", column=None, position=None))
            continue
        if not key.startswith(LEVEL_PREFIX):
            raise SystemExit(f"{name}: '{key}' isn't a level (floor_<key>), `{COLUMNS}:` or `{UNPLACED}:`")
        level = key[len(LEVEL_PREFIX):]
        level_cores = cores.get(level, {})
        if not isinstance(value, dict):
            raise SystemExit(f"{name} '{key}': expected `{OUTSIDE}:` and/or core names, each a list of meters")
        for group, entries in value.items():
            group = str(group)
            where = f"{name} '{key}' {group}"
            if group == OUTSIDE:
                for entry in _meter_list(entries, where):
                    rows.append(_row(entry, where, utilities, floor=level, zone="",
                                     tenant=_floor_tenant(level_cores), column=None, position=None))
                continue
            position = 0
            for entry in _meter_list(entries, where):
                column = entry.get("column", columns.get(group))
                if column is None:
                    raise SystemExit(f"{where}: no column for core '{group}' — add it to `{COLUMNS}:` "
                                     f"(or give meter {entry.get('id')} a `column:`)")
                position = entry.get("position", position)
                rows.append(_row(entry, where, utilities, floor=level, zone=group,
                                 tenant=level_cores.get(group, ""), column=column, position=position))
                position = _whole(position, "position", where, entry) + 1
    rows.sort(key=lambda r: r["id"])
    return rows


def _meter_list(value, where: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(m, dict) for m in value):
        raise SystemExit(f"{where}: expected a list of meters, each {{id: …, base: …, …}}")
    return value


def _whole(value, field: str, where: str, entry: dict) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SystemExit(f"{where}: meter {entry.get('id')!r} has {field}={value!r} — expected a whole number")
    return value


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _flag(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return default if text == "" else text == "yes"


def _row(entry: dict, where: str, utilities: dict[str, dict], *, floor: str, zone: str,
         tenant: str, column: int | None, position: int | None) -> dict:
    """One meter entry as a read_csv row."""
    unknown = sorted(set(entry) - set(FIELDS))
    if unknown:
        raise SystemExit(f"{where}: meter {entry.get('id')!r} has unknown field(s) {unknown} "
                         f"(known: {', '.join(FIELDS)})")
    if not zone:
        misplaced = sorted(set(entry) & set(CORE_ONLY))
        if misplaced:
            raise SystemExit(f"{where}: meter {entry.get('id')!r} sets {misplaced}, which only a core's meters have")
    for field in ("id", "base"):
        if entry.get(field) is None:
            raise SystemExit(f"{where}: a meter has no {field}" + (f" (id {entry['id']})" if "id" in entry else ""))
    also_on = entry.get("also_on") or []
    if not isinstance(also_on, list):
        raise SystemExit(f"{where}: meter {entry['id']!r} also_on must be a list of levels")
    if also_on and not floor:
        raise SystemExit(f"{where}: meter {entry['id']!r} is on no level, so it can't be also_on others")
    function = _text(entry.get("function"))
    parent = entry.get("parent")
    return {
        "id":        _whole(entry["id"], "id", where, entry),
        "tag":       _text(entry.get("tag")),
        "base":      _whole(entry["base"], "base", where, entry),
        "type":      registry.normalise_type(_text(entry.get("type"))),
        "daily":     _whole(entry.get("daily", 0) or 0, "daily", where, entry),
        "monthly":   _whole(entry.get("monthly", 0) or 0, "monthly", where, entry),
        "parent_id": None if parent is None else _whole(parent, "parent", where, entry),
        "floor":     "/".join([floor, *(str(f) for f in also_on)]),
        "column":    None if column is None else _whole(column, "column", where, entry),
        "zone":      zone,
        "position":  None if position is None else _whole(position, "position", where, entry),
        "function":  function,
        "utility":   registry.normalise_utility(_text(entry.get("utility")), function, utilities),
        "tenant":    _text(entry["tenant"]) if "tenant" in entry else tenant,
        "tenant_display": _flag(entry.get("tenant_display"), False),
        "main_display":   _flag(entry.get("main_display"), True),
    }


# ─── Writing ─────────────────────────────────────────────────────────────────

# A string YAML reads back unchanged without quotes, inside a flow mapping:
# starts with a letter, no flow or comment characters, not a YAML keyword.
_PLAIN = re.compile(r"[A-Za-z](?:[A-Za-z0-9 ._/&()+'-]*[A-Za-z0-9._)+'])?")
_KEYWORDS = {"y", "n", "yes", "no", "true", "false", "on", "off", "null"}


def _scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_scalar(v) for v in value) + "]"
    text = str(value)
    if _PLAIN.fullmatch(text) and text.lower() not in _KEYWORDS:
        return text
    return json.dumps(text, ensure_ascii=False)


def dump(rows: list[dict], cores: dict[str, dict[str, str]], level_order: list[str], header: str = "") -> str:
    """`rows` (read_csv's shape) as meters YAML that read() turns back into
    the same rows, writing only what differs from the defaults. `cores` and
    `level_order` come from floors.yaml; a level it doesn't list goes last."""
    zone_columns: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r["floor"] and r["zone"]:
            zone_columns[r["zone"]][r["column"]] += 1
    columns = {zone: min(c, key=lambda col: (-c[col], col)) for zone, c in zone_columns.items()}

    levels: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    unplaced: list[dict] = []
    for r in rows:
        if r["floor"]:
            level = r["floor"].split("/")[0]
            levels[level][r["zone"] or OUTSIDE].append(r)
        else:
            unplaced.append(r)

    out = [header] if header else []
    if columns:
        ordered = sorted(columns, key=lambda z: (columns[z], z))
        out.append(f"{COLUMNS}: {{" + ", ".join(f"{_scalar(z)}: {columns[z]}" for z in ordered) + "}\n")
    rank = {key: i for i, key in enumerate(level_order)}
    for level in sorted(levels, key=lambda k: (k not in rank, rank.get(k, 0), k)):
        out.append(f"\n{_scalar(LEVEL_PREFIX + level)}:\n")
        level_cores = cores.get(level, {})
        groups = levels[level]
        for group in sorted(groups, key=lambda g: (g != OUTSIDE, columns.get(g, -1), g)):
            out.append(f"  {_scalar(group)}:\n")
            tenant = _floor_tenant(level_cores) if group == OUTSIDE else level_cores.get(group, "")
            # A core's meters top to bottom, those in another column (rare)
            # after the rest.
            column = columns.get(group)
            order = (lambda r: (r["column"] != column, r["column"] or 0, r["position"] or 0, r["id"])) \
                if group != OUTSIDE else (lambda r: r["id"])
            position = 0
            for r in sorted(groups[group], key=order):
                placement = {}
                if group != OUTSIDE:
                    if r["column"] != columns[group]:
                        placement["column"] = r["column"]
                    if r["position"] != position:
                        placement["position"] = r["position"]
                    position = r["position"] + 1
                out.append(_line("    ", _entry(r, tenant, placement)))
    if unplaced:
        out.append(f"\n{UNPLACED}:\n")
        for r in sorted(unplaced, key=lambda r: r["id"]):
            out.append(_line("  ", _entry(r, "", {})))
    return "".join(out)


def _line(indent: str, entry: dict) -> str:
    return indent + "- {" + ", ".join(f"{k}: {_scalar(v)}" for k, v in entry.items()) + "}\n"


def _entry(r: dict, tenant: str, placement: dict) -> dict:
    """A row's fields that differ from the defaults, in FIELDS order.
    `tenant` is the one it would inherit; `placement` its non-default
    column/position."""
    entry: dict = {"id": r["id"]}
    if r["tag"]:
        entry["tag"] = r["tag"]
    entry["base"] = r["base"]
    if r["type"]:
        entry["type"] = r["type"]
    if r["daily"]:
        entry["daily"] = r["daily"]
    if r["monthly"]:
        entry["monthly"] = r["monthly"]
    if r["parent_id"] is not None:
        entry["parent"] = r["parent_id"]
    if r["function"]:
        entry["function"] = r["function"]
    if r["utility"]:
        entry["utility"] = r["utility"]
    if r["tenant"] != tenant:
        entry["tenant"] = r["tenant"] or None
    if r["tenant_display"]:
        entry["tenant_display"] = True
    if not r["main_display"]:
        entry["main_display"] = False
    entry.update(placement)
    also_on = r["floor"].split("/")[1:]
    if also_on:
        entry["also_on"] = also_on
    return entry
