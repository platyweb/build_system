#!/usr/bin/env python
"""
Import a meters.csv export into the site's meters YAML: data/meters.yaml,
laid out level → core → meter (see meters_yaml.py).

Usage:
    python _build/import_meters.py EXPORT.csv               # into site/
    python _build/import_meters.py EXPORT.csv --site DIR
    python _build/import_meters.py EXPORT.csv --replace     # overwrite the existing meters YAML

The CSV has the columns README.md lists under "data/meters.csv". Fill in
floors.yaml first: the levels and cores come from there, a meter takes its
core's tenant, and the import writes `tenant:` only where the CSV says
otherwise. The YAML is read back before it's written: the import stops
rather than write a file that doesn't give the CSV's meters exactly.
Re-importing replaces the whole file, hand edits included.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import site_data
import generate_meter_registry
import meters_yaml

HEADER = """\
# ─────────────────────────────────────────────────────────────────────────────
# METERS: every meter in the building, laid out level → core → meter. Fill in
# after floors.yaml, which this file's levels, cores and tenants come from.
#
#   columns: {{<core>: <column>}}  the floor-page column each core's card sits in
#   floor_<key>:                  a level from floors.yaml
#     floor:  [ … ]               meters outside the cores (floor totals, …)
#     <core>: [ … ]               the meters on that core's card, top to bottom
#   unplaced: [ … ]               meters on no level (site totals, …)
#
# A meter is {{id, tag, base, type, daily, monthly, parent, function, utility,
# tenant, tenant_display, main_display, column, position, also_on}}. Only id
# and base are required; README.md "data/meters.yaml" gives every default. A
# meter takes its core's tenant from floors.yaml `cores:`. `tenant:` overrides
# it, and `tenant: null` means none.
#
# Imported from {source} by _build/import_meters.py. Edit it here: a
# re-import replaces the whole file.
# ─────────────────────────────────────────────────────────────────────────────

"""


def target_path() -> Path:
    """The site's meters YAML, or where a new one goes: numbered like the
    site's floors.yaml, if that is."""
    existing = site_data.data_path("meters.yaml")
    if existing.exists():
        return existing
    if site_data.data_path("floors.yaml").name != "floors.yaml":
        return site_data.DATA_DIR / f"{site_data.DATA_FILES.index('meters.yaml'):02d}_meters.yaml"
    return existing


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Import a meters.csv export into the site's meters YAML.")
    ap.add_argument("csv", type=Path, help="the exported meters.csv")
    ap.add_argument("--site", type=Path, default=site_data.DEFAULT_SITE_ROOT, help="site directory (default: site/)")
    ap.add_argument("--replace", action="store_true", help="overwrite the site's existing meters YAML")
    args = ap.parse_args(argv)

    site_data.configure(args.site, site_data.DEFAULT_OUT_ROOT)
    rows = generate_meter_registry.read_csv(args.csv, site_data.UTILITIES)
    levels = site_data.read_levels()
    cores = {lv["key"]: lv["cores"] for lv in levels}
    text = meters_yaml.dump(rows, cores, [lv["key"] for lv in levels], HEADER.format(source=args.csv.name))

    out = target_path()
    if out.exists() and not args.replace:
        raise SystemExit(f"{site_data._rel(out)} exists — pass --replace to overwrite it with this import")

    with tempfile.TemporaryDirectory() as tmp:
        check = Path(tmp) / out.name
        check.write_text(text, encoding="utf-8")
        back = meters_yaml.read(check, site_data.UTILITIES, cores)
    expected = sorted(rows, key=lambda r: r["id"])
    if back != expected:
        ids = sorted({a["id"] for a, b in zip(back, expected) if a != b} | {r["id"] for r in back[len(expected):]}
                     | {r["id"] for r in expected[len(back):]})
        raise SystemExit(f"the YAML wouldn't read back as the CSV (meter ids {ids[:12]}) — nothing written")

    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {site_data._rel(out)}: {len(rows)} meters")
    csv_in_site = site_data.data_path("meters.csv")
    if csv_in_site.exists():
        print(f"now delete {site_data._rel(csv_in_site)}: the build won't read both")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
