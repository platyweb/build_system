"""A page writes a report card as one line, <div data-report="<name>"></div>,
and reports.js builds the card from REPORT_CARDS: each report's title, alt
text and library item id, which the build writes from reports.yaml."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import jsblocks  # noqa: E402
import linkcheck  # noqa: E402


@pytest.fixture
def site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _reports() -> dict:
    return yaml.safe_load(build.data_path("reports.yaml").read_text(encoding="utf-8"))


def _write_reports(data: dict) -> None:
    build.data_path("reports.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                                               encoding="utf-8")


def test_a_floor_tab_names_its_cards_and_reports_js_holds_them(site: Path, tmp_path: Path) -> None:
    build.build_site(["floors"])
    out = tmp_path / "project" / "acme-depot"
    page = (out / "floor_L00.htm").read_text(encoding="utf-8")
    assert '<div data-report="floor_l00_electricity_demand"></div>\n' \
           '                        <div data-report="floor_l00_electricity_consumption"></div>' in page
    assert 'class="floor-card"><div' not in page and "data-image-ref=\"reports." not in page
    js = (out / "js" / "project" / "2.0" / "reports.js").read_text(encoding="utf-8")
    # Untitled floor placements are titled by their order (floor_page.report_titles).
    assert '    floor_l00_electricity_demand: { title: "Demand", alt: "📊 Electricity Demand", libraryItemId: 2 },' in js
    assert '    floor_l00_solar_generation: { title: "Generation", alt: "📊 Solar Generation", libraryItemId: 4 },' in js


def test_an_untitled_card_off_a_floor_page_has_no_title(site: Path) -> None:
    data = _reports()
    data["placements"][0].pop("title")                       # home_elec_demand, page: home
    data["placements"][1].pop("id")
    _write_reports(data)
    cards, warnings = build.report_cards()
    assert cards["home_elec_demand"] == {"kind": "headed", "alt": "📊 Electricity Demand", "library_item_id": 1}
    assert cards["floor_l00_electricity_demand"] == {"alt": "📊 Electricity Demand", "title": "Demand"}
    assert warnings == []


def test_check_warns_when_a_name_has_two_different_cards(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = _reports()
    data["placements"].append(dict(data["placements"][1], floor="L00", slot="solar", position=1))
    _write_reports(data)
    assert build.validate() == 0
    assert "report 'floor_l00_electricity_demand' differs from its card" in capsys.readouterr().out


def test_check_finds_a_data_report_with_no_chart_url(tmp_path: Path) -> None:
    out = tmp_path / "project" / "site"
    out.mkdir(parents=True)
    (out / "page.htm").write_text('<div data-report="known"></div><div data-report="typo"></div>', encoding="utf-8")
    assert linkcheck.unknown_names(tmp_path / "project", out, [], [], {"known"}) == [
        "data-report 'typo' (on page.htm) has no chart URL in reports.yaml `urls:`"]


def test_the_block_leaves_out_unset_fields() -> None:
    assert jsblocks.render_report_cards({}) == "const REPORT_CARDS = {};"
    assert jsblocks.render_report_cards({"a": {"alt": "A"}, "b": {"title": "B \"1\"", "alt": "B", "library_item_id": 7}}) == (
        'const REPORT_CARDS = {\n'
        '    a: { alt: "A" },\n'
        '    b: { title: "B \\"1\\"", alt: "B", libraryItemId: 7 }\n'
        '};')


def test_home_and_building_performance_cards_are_one_line_with_their_style(site: Path, tmp_path: Path) -> None:
    build.build_site(["home", "building_performance"])
    out = tmp_path / "project" / "acme-depot"
    assert '                        <div data-report="home_elec_demand"></div>' in (out / "home.htm").read_text(encoding="utf-8")
    assert '                            <div data-report="performance_energy_split"></div>' in \
        (out / "building_performance.htm").read_text(encoding="utf-8")
    js = (out / "js" / "project" / "2.0" / "reports.js").read_text(encoding="utf-8")
    assert '    home_elec_demand: { kind: "headed", title: "Electricity Demand", ' in js
    assert '    performance_energy_split: { kind: "titled", title: "Energy Split", subtitle: "Last 12 months by utility", ' in js


def test_a_placements_kind_sets_its_style(site: Path) -> None:
    data = _reports()
    data["placements"][1]["kind"] = "headed"                 # a floor card with a header band
    data["placements"][0]["kind"] = "plain"                  # home, overriding its default
    _write_reports(data)
    cards, _warnings = build.report_cards()
    assert cards["floor_l00_electricity_demand"]["kind"] == "headed"
    assert cards["home_elec_demand"]["kind"] == "plain"
