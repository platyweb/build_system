"""The risers module: a riser is a meter with `function: Riser-meter`, its
floor tap-offs are its child meters, its page is one diagram of meter cards,
and the sidebar's `auto: risers` links each riser's page."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import build_risers  # noqa: E402

FLOORS = "floor_L00: {}\nfloor_L01: {}\n"
METERS = """
columns: {West: 0}
floor_L00:
  floor:
    - {id: 1, tag: LV01 - Rising BusBar West, base: 100, type: Modbus, function: Riser-meter, utility: electricity}
  West:
    - {id: 2, tag: T/West L00, base: 200, type: Modbus, parent: 1, utility: electricity}
floor_L01:
  West:
    - {id: 3, tag: T/West L01, base: 300, type: Modbus, parent: 1, utility: electricity}
"""
RISERS = """
defaults:
  default_rating: 60
overrides: {overrides}
"""
# What a site written for the SVG diagrams still has: settings that do nothing now.
RETIRED_RISERS = """
defaults:
  default_rating: 60
  floors_per_page: 1
  layout: {box: {w: 190, h: 54}, margin: 80}
overrides: {}
"""


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal with one two-floor riser."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    build.data_path("floors.yaml").write_text(FLOORS, encoding="utf-8")
    build.data_path("meters.yaml").write_text(METERS, encoding="utf-8")
    return site


def _risers(site: Path, overrides: str = "{}") -> None:
    (site / "data" / "10_risers.yaml").write_text(RISERS.format(overrides=overrides), encoding="utf-8")


def _sidebar() -> list[dict]:
    return [build._public(it) for it in build._auto_risers()]


def test_auto_risers_links_each_risers_page(site: Path) -> None:
    _risers(site)
    assert _sidebar() == [{"label": "Rising BusBar West", "href": "riser_1.htm"}]   # LV01 prefix dropped


def test_a_riser_is_one_page_top_floor_first(site: Path, tmp_path: Path) -> None:
    _risers(site, overrides="{1: {nav_label: West riser}}")
    assert _sidebar() == [{"label": "West riser", "href": "riser_1.htm"}]
    build.build_site(["risers"])
    out = tmp_path / "project" / "acme-depot"
    assert sorted(p.name for p in out.glob("riser_*.htm")) == ["riser_1.htm"]
    assert not list(out.glob("img/riser_*.svg"))
    page = (out / "riser_1.htm").read_text(encoding="utf-8")
    # Each floor's row holds its taps, top floor first; the riser's own meter is the source.
    assert page.index('data-meter-card="3"') < page.index('data-meter-card="2"') < page.index('data-meter-card="1"')
    assert '<div data-meter-card="1" data-label="Rising BusBar West" data-rating="60" data-variant="incomer"></div>' in page
    assert 'data-position' not in page


def test_a_riser_links_the_board_that_feeds_it(site: Path, tmp_path: Path) -> None:
    _risers(site)
    meters = build.data_path("meters.yaml")
    meters.write_text(METERS.replace("function: Riser-meter,", "parent: 9, function: Riser-meter,")
                      + "unplaced:\n  - {id: 9, tag: LV01 - Incomer, base: 900, type: Modbus, utility: electricity}\n",
                      encoding="utf-8")
    (site / "data" / "09_switchboards.yaml").write_text(
        "boards:\n  swb_lv01: {incomer_id: 9, heading: LV-01 Switchboard}\n", encoding="utf-8")
    build.build_site(["risers"])
    page = (tmp_path / "project" / "acme-depot" / "riser_1.htm").read_text(encoding="utf-8")
    assert '<a class="swb-tie sld-tie" href="swb_lv01.htm">Fed from LV-01 Switchboard</a>' in page


def test_the_svg_diagrams_settings_still_build_and_check_warns(site: Path, tmp_path: Path) -> None:
    (site / "data" / "10_risers.yaml").write_text(RETIRED_RISERS, encoding="utf-8")
    build.build_site(["risers"])
    assert (tmp_path / "project" / "acme-depot" / "riser_1.htm").exists()
    assert build_risers.retired_settings() == [
        "10_risers.yaml defaults: `layout` is no longer used (the diagram lays itself out); delete it",
        "10_risers.yaml defaults: `floors_per_page` is no longer used (the diagram lays itself out); delete it",
    ]


def test_a_site_without_risers_lists_none(site: Path) -> None:
    build.data_path("meters.yaml").write_text(METERS.replace("Riser-meter", "SWB-meter"), encoding="utf-8")
    assert _sidebar() == []       # with no risers.yaml either
    _risers(site)
    assert _sidebar() == []
