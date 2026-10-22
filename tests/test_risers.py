"""The risers module: a riser is a meter with `function: Riser-meter`, its
floor tap-offs are its child meters, and the sidebar's `auto: risers` links
each riser's first page."""
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
  floors_per_page: {floors_per_page}
  layout:
    box: {{w: 190, h: 54}}
    floor_gap: 16
    gap: 30
    tap_offset: 70
    depth_step: 220
    tap_stagger: 10
    margin: 80
    incomer_gap: 70
    lane_pitch_target: 14
    busbar: {{color: "#6d28d9", width: 6}}
    conn: {{color: "#6d28d9", width: 3}}
    tie_arrow_len: 70
    tie_arrow_head: 26
overrides: {overrides}
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


def _risers(site: Path, floors_per_page: int = 20, overrides: str = "{}") -> None:
    (site / "data" / "10_risers.yaml").write_text(
        RISERS.format(floors_per_page=floors_per_page, overrides=overrides), encoding="utf-8")


def _sidebar() -> list[dict]:
    return [build._public(it) for it in build._auto_risers()]


def test_auto_risers_links_each_risers_page(site: Path) -> None:
    _risers(site)
    assert _sidebar() == [{"label": "Rising BusBar West", "href": "riser_1.htm"}]   # LV01 prefix dropped


def test_a_split_riser_links_its_first_page(site: Path, tmp_path: Path) -> None:
    _risers(site, floors_per_page=1, overrides="{1: {nav_label: West riser}}")
    assert _sidebar() == [{"label": "West riser", "href": "riser_1_p1.htm"}]
    build.build_site(["risers"])
    built = sorted(p.name for p in (tmp_path / "project" / "acme-depot").glob("riser_*.htm"))
    assert built == ["riser_1_p1.htm", "riser_1_p2.htm"]


def test_a_site_without_risers_lists_none(site: Path) -> None:
    build.data_path("meters.yaml").write_text(METERS.replace("Riser-meter", "SWB-meter"), encoding="utf-8")
    assert _sidebar() == []       # with no risers.yaml either
    _risers(site)
    assert _sidebar() == []
