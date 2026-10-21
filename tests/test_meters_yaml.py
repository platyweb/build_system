"""The meters YAML (level → core → meter) reads into the same rows as
meters.csv, inheriting each core's tenant; data files, site.yaml among them,
may carry a fill-order number; and import_meters.py turns a meters.csv export
into the YAML."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import generate_meter_registry  # noqa: E402
import import_meters  # noqa: E402
import meters_yaml  # noqa: E402

SITES = [ROOT / "site", ROOT / "examples" / "minimal", ROOT / "examples" / "campus"]

FLOORS = """
tenants:
  Fern & Co: {}
  Quill: {}
floor_L00:
  cores: {West: Fern & Co}
floor_L01:
  cores: {West: Quill, East: Quill}
floor_L02:
  cores: {West: Fern & Co, East: Quill}
"""


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, configured as the build's site."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _read(site: Path, meters: str, floors: str = FLOORS) -> dict[int, dict]:
    build.data_path("floors.yaml").write_text(floors, encoding="utf-8")
    build.data_path("meters.yaml").write_text(meters, encoding="utf-8")
    return {r["id"]: r for r in build.read_meter_rows()}


@pytest.mark.parametrize("site_dir", SITES, ids=lambda p: p.name)
def test_every_sites_meters_survive_a_round_trip(site_dir: Path, tmp_path: Path) -> None:
    build.configure(site_dir, tmp_path / "project")
    rows = build.read_meter_rows()
    levels = build.read_levels()
    cores = {lv["key"]: lv["cores"] for lv in levels}
    path = tmp_path / "meters.yaml"
    path.write_text(meters_yaml.dump(rows, cores, [lv["key"] for lv in levels]), encoding="utf-8")
    assert meters_yaml.read(path, build.UTILITIES, cores) == sorted(rows, key=lambda r: r["id"])


def test_a_meter_takes_its_cores_tenant(site: Path) -> None:
    rows = _read(site, """
columns: {West: 0, North: 1}
floor_L00:
  West:
    - {id: 1, base: 1}
    - {id: 2, base: 2, tenant: null}
    - {id: 3, base: 3, tenant: "Quill, Fern & Co"}
  North:
    - {id: 4, base: 4}
floor_L01:
  floor:
    - {id: 5, base: 5}
floor_L02:
  floor:
    - {id: 6, base: 6}
unplaced:
  - {id: 7, base: 7}
""")
    assert {i: r["tenant"] for i, r in rows.items()} == {
        1: "Fern & Co",           # West core is Fern & Co's
        2: "",                    # tenant: null overrides
        3: "Quill, Fern & Co",    # a shared meter, spelled out
        4: "",                    # North isn't a tenant's core
        5: "Quill",               # outside the cores of a one-tenant level
        6: "",                    # … but not of a level split between two
        7: "",
    }


def test_column_position_and_also_on_defaults(site: Path) -> None:
    rows = _read(site, """
columns: {West: 0, East: 2}
floor_L00:
  floor:
    - {id: 9, base: 9}
  West:
    - {id: 1, base: 1}
    - {id: 2, base: 2}
    - {id: 3, base: 3, position: 5}
    - {id: 4, base: 4}
  East:
    - {id: 5, base: 5, column: 1, also_on: [L01, L02]}
""")
    placed = {i: (r["floor"], r["column"], r["zone"], r["position"]) for i, r in rows.items()}
    assert placed == {
        1: ("L00", 0, "West", 0), 2: ("L00", 0, "West", 1),
        3: ("L00", 0, "West", 5), 4: ("L00", 0, "West", 6),      # counting on from an explicit position
        5: ("L00/L01/L02", 1, "East", 0),
        9: ("L00", None, "", None),
    }
    assert list(rows) == [1, 2, 3, 4, 5, 9]                        # id order, as METER_REGISTRY lists them


def test_fields_default_like_blank_csv_cells(site: Path) -> None:
    [row] = _read(site, "unplaced:\n  - {id: 1, base: 100, type: calc, utility: Electricity}\n").values()
    assert row == {
        "id": 1, "tag": "", "base": 100, "type": "Calculation", "daily": 0, "monthly": 0, "parent_id": None,
        "floor": "", "column": None, "zone": "", "position": None, "function": "", "utility": "electricity",
        "tenant": "", "tenant_display": False, "main_display": True,
    }


@pytest.mark.parametrize(("meters", "error"), [
    ("floor_L00:\n  West:\n    - {id: 1, base: 1, colour: red}\n", r"unknown field\(s\) \['colour'\]"),
    ("floor_L00:\n  floor:\n    - {id: 1, base: 1, position: 2}\n", r"sets \['position'\], which only a core's"),
    ("floor_L00:\n  Atrium:\n    - {id: 1, base: 1}\n", "no column for core 'Atrium'"),
    ("floor_L00:\n  West:\n    - {id: 1}\n", "a meter has no base"),
    ("level_L00:\n  West: []\n", "'level_L00' isn't a level"),
    ("floor_L00: {}\nfloor_L00: {}\n", "duplicate key 'floor_L00'"),
    ("unplaced:\n  - {id: 1, base: 1, also_on: [L01]}\n", "is on no level"),
])
def test_bad_meters_stop_the_build(site: Path, meters: str, error: str) -> None:
    with pytest.raises(SystemExit, match=error):
        _read(site, "columns: {West: 0}\n" + meters)


def test_a_site_cant_have_both_meters_files(site: Path) -> None:
    (site / "data" / "meters.csv").write_text("id,tag,base\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="both 03_meters.yaml and meters.csv"):
        build.read_meter_rows()


def test_data_files_are_found_with_or_without_their_number(site: Path) -> None:
    assert build.data_path("floors.yaml").name == "02_floors.yaml"
    assert build.data_path("dials.yaml") == site / "data" / "dials.yaml"     # absent: the plain name
    (site / "data" / "floors.yaml").write_text("floor_L00: {}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="02_floors.yaml, floors.yaml are all floors.yaml"):
        build.data_path("floors.yaml")


def test_site_yaml_is_data_file_00_or_at_an_older_sites_root(site: Path, tmp_path: Path) -> None:
    assert build.BUILDING_FILE == site / "data" / "00_site.yaml"
    slug = build.read_building()["slug"]
    build.BUILDING_FILE.rename(site / "site.yaml")                           # an older site's layout
    build.configure(site, tmp_path / "project")
    assert (build.BUILDING_FILE, build.read_building()["slug"]) == (site / "site.yaml", slug)
    shutil.copy(site / "site.yaml", site / "data" / "00_site.yaml")
    with pytest.raises(SystemExit, match="both data/00_site.yaml and site.yaml"):
        build.configure(site, tmp_path / "project")
    (site / "site.yaml").unlink()
    (site / "data" / "00_site.yaml").unlink()
    with pytest.raises(SystemExit, match="is .* a site directory"):
        build.configure(site, tmp_path / "project")


def test_check_warns_about_a_data_file_it_doesnt_read(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build.data_path("bms_bindings.yaml").rename(site / "data" / "05_bms_binding.yaml")
    build.validate()
    assert "05_bms_binding.yaml: the build doesn't read this file" in capsys.readouterr().out


def test_import_turns_an_export_into_the_meters_yaml(tmp_path: Path) -> None:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "campus", site, ignore=shutil.ignore_patterns("golden"))
    export = tmp_path / "export.csv"
    shutil.move(site / "data" / "meters.csv", export)
    build.configure(site, tmp_path / "project")
    expected = generate_meter_registry.read_csv(export, build.UTILITIES)

    assert import_meters.main([str(export), "--site", str(site)]) == 0
    assert build.meters_file() == site / "data" / "meters.yaml"   # unnumbered, like this site's floors.yaml
    assert build.read_meter_rows() == sorted(expected, key=lambda r: r["id"])
    with pytest.raises(SystemExit, match="exists — pass --replace"):
        import_meters.main([str(export), "--site", str(site)])
    assert import_meters.main([str(export), "--site", str(site), "--replace"]) == 0
