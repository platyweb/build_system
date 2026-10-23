"""Campus sites: each building's pages in its own folder, with every link and
asset path still resolving — checked on a real build of examples/campus."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import linkcheck  # noqa: E402

SIDEBAR_BLOCK = re.compile(r"BEGIN GENERATED SIDEBAR_HTML.*?END GENERATED SIDEBAR_HTML", re.S)


@pytest.fixture(scope="module")
def site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("campus") / "project"
    subprocess.run([sys.executable, str(ROOT / "_build" / "build.py"), "--site", str(ROOT / "examples" / "campus"),
                    "--out", str(out)], check=True, capture_output=True, text=True)
    return out / "riverside-campus"


def test_building_pages_live_in_building_folders(site_dir: Path) -> None:
    assert sorted(p.relative_to(site_dir).as_posix() for p in site_dir.glob("*/*.htm")) == [
        "north/floor_n-l00.htm", "north/floor_n-l01.htm", "north/floor_n-l02.htm", "north/floor_n-l03.htm",
        "north/incomer_north_electricity.htm", "north/incomer_north_lthw.htm", "north/plant_room.htm",
        "north/riser_4.htm", "north/swb_north_mdb.htm",
        "south/floor_s-l00.htm", "south/incomer_south_electricity.htm", "south/swb_south_mdb.htm",
    ]
    assert sorted(p.name for p in site_dir.glob("*.htm")) == ["home.htm", "incomer_gas.htm", "meters_hierarchy.htm"]


def test_every_page_and_script_link_resolves(site_dir: Path) -> None:
    # Pages, and each sidebar's links as resolved on the pages that load it
    # (the root's for site-root pages, a building's copy in its folder).
    # Assets are covered by test_check's examples test.
    escaping, broken = [], []
    for source, url, target in linkcheck.references(site_dir.parent):
        if not target.is_relative_to(site_dir.resolve()):
            escaping.append(f"{source.relative_to(site_dir)}: {url}")
        elif target.suffix in (".htm", ".js") and not target.exists():
            broken.append(f"{source.relative_to(site_dir)}: {url}")
    assert not escaping, escaping
    assert not broken, broken


def test_building_page_uses_its_folders_sidebar_and_prefixed_assets(site_dir: Path) -> None:
    page = (site_dir / "north" / "floor_n-l01.htm").read_text(encoding="utf-8")
    assert '<script src="sidebar-template.js"></script>' in page
    assert 'src="../js/project/2.0/meter-templates.js"' in page
    assert 'href="../css/project/2.0/style.css"' in page
    assert 'src="../img/floors/floor_n-l01.png"' in page
    assert 'src="../img/north_riser.png"' in page           # an extra's image (data/extras.yaml)


def test_sidebars_rewritten_per_folder(site_dir: Path) -> None:
    root = (site_dir / "js/project/2.0/sidebar-template.js").read_text(encoding="utf-8")
    north = (site_dir / "north" / "sidebar-template.js").read_text(encoding="utf-8")
    assert 'href="north/floor_n-l03.htm"' in root and 'href="home.htm"' in root
    assert 'href="floor_n-l03.htm"' in north and 'href="../home.htm"' in north
    assert 'href="../south/floor_s-l00.htm"' in north and 'src="../img/sidebar-bg.png"' in north
    # The runtime's own URL: up a level from a building folder.
    assert 'const SIDEBAR_RUNTIME_SRC = "js/project/2.0/sidebar.js";' in root
    assert 'const SIDEBAR_RUNTIME_SRC = "../js/project/2.0/sidebar.js";' in north
    assert "script.src = SIDEBAR_RUNTIME_SRC;" in north
    # Building sub-menus: floors top first, then the building's incomers and switchboards.
    labels = re.findall(r'menu-title">([^<]+)<', SIDEBAR_BLOCK.search(north).group(0))
    assert labels[labels.index("North Tower"):labels.index("South Annex")] == [
        "North Tower", "Level 3", "Level 2", "Level 1", "Ground Floor", "Electricity", "LTHW", "Main Distribution Board"]


def test_switchboard_links_cross_building_folders(site_dir: Path) -> None:
    south = (site_dir / "south" / "swb_south_mdb.htm").read_text(encoding="utf-8")
    assert 'href="../north/swb_north_mdb.htm"' in south     # bus tie to the other building's board
    riser = (site_dir / "north" / "riser_4.htm").read_text(encoding="utf-8")
    assert 'href="swb_north_mdb.htm">Fed from Main Distribution Board</a>' in riser   # same building


@pytest.mark.parametrize("url, folder, expected", [
    ("home.htm", None, "home.htm"),                      # site root: unchanged
    ("home.htm", "north", "../home.htm"),
    ("north/floor_n-l01.htm", "north", "floor_n-l01.htm"),
    ("south/floor_s-l00.htm", "north", "../south/floor_s-l00.htm"),
    ("/Login.html?logout", "north", "/Login.html?logout"),  # absolute / external / in-page: unchanged
    ("https://example.com/x", "north", "https://example.com/x"),
    ("#", "north", "#"),
])
def test_relative_url(url: str, folder: str | None, expected: str) -> None:
    assert build.relative_url(url, folder) == expected


def test_campus_levels_need_a_known_building(tmp_path: Path) -> None:
    import shutil
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "campus", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    floors = build.data_path("floors.yaml")
    floors.write_text(floors.read_text(encoding="utf-8") + "floor_x-l00: {label: X}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="'floor_x-l00': needs `building:`"):
        build.read_levels()
    floors.write_text(floors.read_text(encoding="utf-8").replace("{label: X}", "{building: east, label: X}"),
                      encoding="utf-8")
    with pytest.raises(SystemExit, match="building 'east' isn't in site.yaml"):
        build.read_levels()
    floors.write_text(floors.read_text(encoding="utf-8") + "floor_s-l00: {building: south}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="duplicate key 'floor_s-l00'"):
        build.read_levels()
