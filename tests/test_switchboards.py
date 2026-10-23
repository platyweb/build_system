"""The switchboards module: a board is its incomer meter and every meter it
feeds (its ways), drawn as a single-line diagram of meter cards. A bus tie
is a coupler drawn on both boards it joins; a board fed from another, and
a way that is a riser, link to each other."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import build_switchboards  # noqa: E402

FLOORS = "floor_L00: {}\nfloor_L01: {}\n"
# LV01 feeds seven ways: LV02's incomer (9), a riser (5) and five more; the
# riser feeds a meter on each level; LV02 feeds one way.
METERS = """
columns: {West: 0}
floor_L00:
  floor:
    - {id: 5, tag: LV01 - Rising Busbar, base: 500, type: Modbus, parent: 1, function: Riser-meter, utility: electricity}
  West:
    - {id: 6, tag: T/West L00, base: 600, type: Modbus, parent: 5, utility: electricity}
floor_L01:
  West:
    - {id: 7, tag: T/West L01, base: 700, type: Modbus, parent: 5, utility: electricity}
unplaced:
  - {id: 1, tag: LV01 - Incomer, base: 100, type: Modbus, utility: electricity}
  - {id: 2, tag: LV01 - Chiller 1, base: 200, type: Modbus, parent: 1, utility: electricity}
  - {id: 3, tag: LV01 - Chiller 2, base: 300, type: Modbus, parent: 1, utility: electricity}
  - {id: 4, tag: LV01 - AHU 1, base: 400, type: Modbus, parent: 1, utility: electricity}
  - {id: 8, tag: LV01 - Lifts, base: 800, type: Modbus, parent: 1, utility: electricity}
  - {id: 10, tag: LV01 - Car Park, base: 1000, type: Modbus, parent: 1, utility: electricity}
  - {id: 9, tag: LV02 - Incomer, base: 900, type: Modbus, parent: 1, utility: electricity}
  - {id: 11, tag: LV02 - Pumps, base: 1100, type: Modbus, parent: 9, utility: electricity}
  - {id: 12, tag: Bus Coupler, base: 1200, type: Modbus, utility: electricity}
"""
BOARDS = """
defaults: {{default_rating: 150}}
boards:
  swb_lv01:
    heading: LV-01 Switchboard
    incomer_id: 1
    columns: 3
    ways: {{2: {{rating: 400, ct: "800/5"}}}}
    {tie}
  swb_lv02:
    heading: LV-02 Switchboard
    incomer_id: 9
"""


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal with two boards and a riser."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    build.data_path("floors.yaml").write_text(FLOORS, encoding="utf-8")
    build.data_path("meters.yaml").write_text(METERS, encoding="utf-8")
    (site / "data" / "10_risers.yaml").write_text("defaults: {default_rating: 60}\n", encoding="utf-8")
    return site


def _boards(site: Path, tie: str = "") -> dict[str, str]:
    """Build the boards; their pages by key."""
    (site / "data" / "09_switchboards.yaml").write_text(BOARDS.format(tie=tie), encoding="utf-8")
    build.build_site(["switchboards"])
    return {key: (build.SITE_DIR / f"{key}.htm").read_text(encoding="utf-8") for key in ("swb_lv01", "swb_lv02")}


def _cards(page: str) -> list[str]:
    return re.findall(r'<div data-meter-card="[^"]*"[^>]*></div>', page)


def test_a_board_is_its_incomer_and_its_ways_as_meter_cards(site: Path) -> None:
    lv01 = _boards(site)["swb_lv01"]
    cards = _cards(lv01)
    assert cards[0] == '<div data-meter-card="1" data-label="Incomer" data-rating="1500" data-variant="incomer"></div>'
    assert cards[1] == '<div data-meter-card="2" data-label="Chiller 1" data-rating="400" data-ct="800/5"></div>'
    assert [re.search(r'"(\d+)"', c).group(1) for c in cards[1:]] == ["2", "3", "4", "5", "8", "9", "10"]
    # Three to a busbar row: the 4th and 7th ways start a row.
    ways = re.findall(r'<li class="sld-way">(<span class="sld-wrap"></span>)?\s*<div data-meter-card="(\d+)"', lv01)
    assert [meter for wrap, meter in ways if wrap] == ["5", "10"]
    assert "--sld-columns: 3;" in lv01
    assert "data-position" not in lv01 and not list(build.SITE_DIR.glob("img/swb_*.svg"))


def test_boards_and_risers_link_from_the_hierarchy(site: Path) -> None:
    pages = _boards(site)
    assert '<a class="swb-tie" href="swb_lv02.htm">→ LV-02 Switchboard</a>' in pages["swb_lv01"]   # way 9 is its incomer
    assert '<a class="swb-tie" href="riser_5.htm">→ Riser</a>' in pages["swb_lv01"]
    assert '<a class="swb-tie" href="swb_lv01.htm">Fed from LV-01 Switchboard</a>' in pages["swb_lv02"]
    assert "Fed from" not in pages["swb_lv01"]


def test_a_bus_coupler_is_drawn_on_both_boards(site: Path) -> None:
    pages = _boards(site, tie="bus_tie: {side: right, to: swb_lv02, label: To LV-02, meter: 12}")
    lv01, lv02 = pages["swb_lv01"], pages["swb_lv02"]
    assert '<div class="sld-coupler sld-coupler-right">' in lv01
    assert '<a class="swb-tie" href="swb_lv02.htm">To LV-02</a>' in lv01
    assert '<span class="sld-coupler-note">N/O</span>' in lv01
    assert '<div data-meter-card="12" data-label="Bus Coupler" data-rating="150"></div>' in lv01
    # Mirrored: on the left of the other board, back to this one, with the same coupler.
    assert '<div class="sld-coupler sld-coupler-left">' in lv02
    assert '<a class="swb-tie" href="swb_lv01.htm">LV-01 Switchboard</a>' in lv02
    assert '<div data-meter-card="12" data-label="Bus Coupler" data-rating="150"></div>' in lv02


def test_a_closed_coupler(site: Path) -> None:
    lv01 = _boards(site, tie="bus_tie: {side: left, to: swb_lv02, normally: closed}")["swb_lv01"]
    assert '<div class="sld-coupler sld-coupler-left sld-coupler-closed">' in lv01
    assert '<span class="sld-coupler-note">N/C</span>' in lv01


@pytest.mark.parametrize("tie, message", [
    ("bus_tie: {side: up, to: swb_lv02}", "bus_tie.side must be 'left' or 'right'"),
    ("bus_tie: {side: left, to: swb_lv09}", "bus_tie.to='swb_lv09' is not a known board key"),
    ("bus_tie: {side: left, to: swb_lv02, normally: ajar}", "bus_tie.normally must be 'open' or 'closed'"),
    ("bus_tie: {side: left, to: swb_lv02, meter: 99}", "bus_tie.meter=99 not in METER_REGISTRY"),
])
def test_a_bad_bus_tie_stops_the_build(site: Path, tie: str, message: str) -> None:
    with pytest.raises(SystemExit, match=re.escape(message)):
        _boards(site, tie=tie)


def test_the_svg_diagrams_layout_still_builds_and_check_warns(site: Path) -> None:
    pages = _boards(site, tie="layout: {rows: 4, box: {w: 190, h: 64}}")
    assert "swb_lv01" in pages
    assert build_switchboards.retired_settings() == [
        "09_switchboards.yaml boards.swb_lv01: `layout` is no longer used (the diagram lays itself out); delete it"]
