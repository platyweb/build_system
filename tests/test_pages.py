"""data/pages.yaml as the menu: it lists every page the site builds, the
sidebar is generated from it, and a page of the site's own renders from its
site template, else as an empty page with the header and scripts. An older
site's frozen-page list, sidebar.yaml and site.yaml `modules:` still work."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402

LANDLORDS = '''
      - label: Services
        icon: bx-podcast
        children:
          - { label: "Landlord Services", page: landlords }
          - { label: "Tariffs", page: tariffs, heading: "Tariff Calculation", page_title: "Tariffs · AD" }
  - header: SETTINGS'''


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, whose pages.yaml is the menu."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _edit_pages(old: str, new: str) -> None:
    path = build.data_path("pages.yaml")
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def _out(tmp_path: Path) -> Path:
    return tmp_path / "project" / "acme-depot"


def test_the_menu_decides_the_modules(site: Path) -> None:
    assert build.resolve_modules(None) == ["floors", "incomers", "home", "meters_hierarchy",
                                           "building_performance", "sidebar"]
    _edit_pages("  - { label: Home, icon: bxs-home, page: home }\n", "")
    _edit_pages("  - header: SETTINGS", LANDLORDS.removeprefix("\n").removesuffix("\n  - header: SETTINGS")
                + "\n  - header: SETTINGS")
    assert build.resolve_modules(None) == ["floors", "incomers", "meters_hierarchy",
                                           "building_performance", "pages", "sidebar"]


def test_an_own_page_without_a_template_is_an_empty_page(site: Path, tmp_path: Path) -> None:
    _edit_pages("\n  - header: SETTINGS", LANDLORDS)
    build.build_site(build.resolve_modules(None))
    page = (_out(tmp_path) / "landlords.htm").read_text(encoding="utf-8")
    assert "<title>Landlord Services · AD EMS</title>" in page            # label → heading, + ems_name
    assert "<h1>Landlord Services</h1>" in page
    for script in ("/js/liveDisplayAndDashboard.js", "js/project/2.0/live-points.js",
                   "js/project/2.0/sidebar-template.js", 'css/project/2.0/style.css'):
        assert script in page
    body = page.split('<div class="title-bar">')[1].split("</main>")[0]
    assert body.split("</div>", 1)[1].strip().removesuffix("</div>").strip() == ""   # nothing below the title
    tariffs = (_out(tmp_path) / "tariffs.htm").read_text(encoding="utf-8")
    assert "<title>Tariffs · AD</title>" in tariffs and "<h1>Tariff Calculation</h1>" in tariffs
    sidebar = (_out(tmp_path) / "js" / "project" / "2.0" / "sidebar-template.js").read_text(encoding="utf-8")
    assert '<a href="landlords.htm">' in sidebar and '<a href="tariffs.htm">' in sidebar


def test_an_own_page_renders_its_site_template(site: Path, tmp_path: Path) -> None:
    _edit_pages("\n  - header: SETTINGS", LANDLORDS)
    (site / "templates").mkdir(exist_ok=True)
    (site / "templates" / "landlords.html.j2").write_text(
        "{% extends 'base.html.j2' %}{% block content %}<p>Landlords of {{ building.name }}</p>{% endblock %}",
        encoding="utf-8")
    build.build_site(build.resolve_modules(None))
    page = (_out(tmp_path) / "landlords.htm").read_text(encoding="utf-8")
    assert "<p>Landlords of Acme Depot</p>" in page and "<h1>Landlord Services</h1>" in page


def test_an_unlisted_page_is_built_but_not_in_the_menu(site: Path, tmp_path: Path) -> None:
    _edit_pages("  - { label: Home, icon: bxs-home, page: home }\n", "")
    build.data_path("pages.yaml").write_text(
        build.data_path("pages.yaml").read_text(encoding="utf-8") + "\nunlisted:\n  - { page: home }\n",
        encoding="utf-8")
    build.build_site(build.resolve_modules(None))
    assert (_out(tmp_path) / "home.htm").exists()
    sidebar = (_out(tmp_path) / "js" / "project" / "2.0" / "sidebar-template.js").read_text(encoding="utf-8")
    assert sidebar.count('href="home.htm"') == 1        # just the brand logo's link


@pytest.mark.parametrize(("change", "error"), [
    (("pages: floors }", "pages: lifts }"), "`pages: lifts` isn't a page family"),
    (("pages: floors }", "auto: floors }"), r"`auto: floors` — in pages.yaml a family is `pages: floors`"),
    (("page: meters_hierarchy }", "page: meters_hierarchy, heading: Tree }"), "built by the meters_hierarchy module"),
    (("top_items:", "nav:\ntop_items:"), r"unknown key\(s\) \['nav'\]"),
    (("top_items:", "pages: []\ntop_items:"), "a `pages:` list .* or the menu"),
])
def test_a_bad_menu_stops_the_build(site: Path, change: tuple[str, str], error: str) -> None:
    _edit_pages(*change)
    with pytest.raises(SystemExit, match=error):
        build.resolve_modules(None)


def test_the_menu_replaces_sidebar_yaml_and_modules(site: Path) -> None:
    (site / "data" / "16_sidebar.yaml").write_text("sections: []\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="isn't read — delete it"):
        build.resolve_modules(None)
    (site / "data" / "16_sidebar.yaml").unlink()
    build.BUILDING_FILE.write_text(build.BUILDING_FILE.read_text(encoding="utf-8") + "modules: [floors]\n",
                                   encoding="utf-8")
    with pytest.raises(SystemExit, match="decides what's built now; delete `modules:`"):
        build.resolve_modules(None)


def test_an_older_site_still_uses_sidebar_yaml_and_modules(tmp_path: Path) -> None:
    build.configure(ROOT / "examples" / "campus", tmp_path / "project")
    assert build.read_menu() is None
    assert build.resolve_modules(None) == ["floors", "incomers", "home", "meters_hierarchy", "pages",
                                           "switchboards", "sidebar"]
    assert [pg["key"] for pg in build.own_pages()] == ["north_plant"]
