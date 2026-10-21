"""The floors.yaml level roster: order is physical order, labels default
sensibly, and --check catches a floor key that isn't a level."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402

MINIMAL = ROOT / "examples" / "minimal"

# Deliberately not alphabetical or numeric: only the file order says where
# each level sits.
ROSTER = """
floor_B1:   {label: "Basement", page: false}
floor_L00:  {label: "Ground Floor"}
floor_Mezz: {label: "Mezzanine", nav_label: "Mezz", heading: "Mezzanine Plant Deck"}
floor_L01: {}
floor_Roof: {page: false}
"""


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, configured as the build's site."""
    site = tmp_path / "site"
    shutil.copytree(MINIMAL, site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def test_roster_order_and_defaults(site: Path) -> None:
    build.data_path("floors.yaml").write_text(ROSTER, encoding="utf-8")
    levels = build.read_levels()
    assert [lv["key"] for lv in levels] == ["B1", "L00", "Mezz", "L01", "Roof"]
    by_key = {lv["key"]: lv for lv in levels}
    assert by_key["L01"]["label"] == "L01"                       # default: the key
    assert by_key["L00"]["nav_label"] == "Ground Floor"          # default: label
    assert by_key["L00"]["heading"] == "Ground Floor Overview"   # default: "<label> Overview"
    assert by_key["Mezz"]["heading"] == "Mezzanine Plant Deck"
    assert [lv["page"] for lv in levels] == [False, True, True, True, False]
    assert build.level_rank() == {"B1": 0, "L00": 1, "Mezz": 2, "L01": 3, "Roof": 4}


def test_sidebar_lists_page_levels_top_first(site: Path) -> None:
    build.data_path("floors.yaml").write_text(ROSTER, encoding="utf-8")
    assert [(i["_key"], i["label"]) for i in build._auto_floors()] == [
        ("L01", "L01"), ("Mezz", "Mezz"), ("L00", "Ground Floor"),
    ]


def test_sort_floors_follows_roster_not_spelling(site: Path) -> None:
    build.data_path("floors.yaml").write_text(ROSTER, encoding="utf-8")
    rank = build.level_rank()
    assert build.sort_floors({"Roof", "L00", "B1", "Mezz"}, rank, "test") == ["B1", "L00", "Mezz", "Roof"]
    assert build.sort_floors({"L00", "L01"}, rank, "test", top_first=True) == ["L01", "L00"]
    with pytest.raises(SystemExit, match=r"floor\(s\) \['L02'\] aren't levels"):
        build.sort_floors({"L00", "L02"}, rank, "test")


def test_check_catches_a_mistyped_floor(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert build.validate() == 0
    meters = build.data_path("meters.yaml")
    # "L0O" — letter O for zero — holding an otherwise valid meter.
    meters.write_text(meters.read_text(encoding="utf-8")
                      + "\nfloor_L0O:\n  West:\n    - {id: 99, tag: Typo Meter, base: 30000, type: Modbus}\n",
                      encoding="utf-8")
    assert build.validate() == 1
    assert "03_meters.yaml: floor 'L0O' (meter ids [99])" in capsys.readouterr().out


def test_level_keys_must_be_floor_prefixed(site: Path) -> None:
    build.data_path("floors.yaml").write_text("lobby: {}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="must be written floor_<key>"):
        build.read_levels()
