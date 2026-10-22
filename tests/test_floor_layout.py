"""Floor page layout: site.yaml floor_page `floorplan`, `meter_columns` and
`summary_layout`, which a floors.yaml level may override. Their defaults
write the page as it always was (the goldens hold that); these tests cover
each other choice on a copy of examples/minimal, whose one level has cards
in 3 columns and a total summary card."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402

MINIMAL = ROOT / "examples" / "minimal"


@pytest.fixture(autouse=True)
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, configured as the build's site (error
    messages name its files)."""
    site = tmp_path / "site"
    shutil.copytree(MINIMAL, site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _configure(site: Path, floor_page: dict | None = None, level: dict | None = None) -> None:
    """Add these keys to site.yaml `floor_page:` and to level L00, then
    configure the build on the site again."""
    config = yaml.safe_load(build.BUILDING_FILE.read_text(encoding="utf-8"))
    config["floor_page"].update(floor_page or {})
    build.BUILDING_FILE.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    floors = build.data_path("floors.yaml")
    levels = yaml.safe_load(floors.read_text(encoding="utf-8"))
    levels["floor_L00"].update(level or {})
    floors.write_text(yaml.safe_dump(levels, sort_keys=False), encoding="utf-8")
    build.configure(site, build.OUT_ROOT)


def _floor_page(site: Path, floor_page: dict | None = None, level: dict | None = None) -> str:
    _configure(site, floor_page, level)
    build.build_site(["floors"])
    return (build.SITE_DIR / "floor_L00.htm").read_text(encoding="utf-8")


def test_defaults_are_the_page_as_it_was() -> None:
    _roles, floor_page, _tenant_page = build.read_page_config({})
    assert floor_page["layout"] == {"floorplan": "right", "meter_columns": 3, "summary_layout": "split"}


@pytest.mark.parametrize("floor_page, message", [
    ({"floorplan": "left"}, r"floor_page: `floorplan: left` isn't one of: right, top, none"),
    ({"meter_columns": 5}, r"`meter_columns: 5` isn't one of: 3, 1, 2, 4, auto"),
    ({"meter_columns": True}, r"`meter_columns: True` isn't one of"),   # True == 1 in Python
    ({"summary_layout": "grid"}, r"`summary_layout: grid` isn't one of: split, row"),
])
def test_bad_layout_stops_the_build(floor_page: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        build.read_page_config({"floor_page": floor_page})


def test_a_level_override_is_checked_and_not_page_data(site: Path) -> None:
    build.data_path("floors.yaml").write_text("floor_L00: {floorplan: top, meter_columns: auto}\n", encoding="utf-8")
    [level] = build.read_levels()
    assert level["layout"] == {"floorplan": "top", "meter_columns": "auto"}
    assert level["data"] == {}
    build.data_path("floors.yaml").write_text("floor_L00: {meter_columns: 0}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"'floor_L00': `meter_columns: 0` isn't one of"):
        build.read_levels()


def test_floorplan_none_drops_the_image(site: Path) -> None:
    page = _floor_page(site, {"floorplan": "none"})
    assert "Floor Plan" not in page and "floor-summary-image" not in page
    assert "floor-summary-center-block floor-card" in page        # the total card stays
    # With no summary cards either, the summary section goes.
    page = _floor_page(site, {"floorplan": "none", "summary_cards": {}})
    assert "Section 1: Floor Summary" not in page and "floor-section-summary" not in page


def test_floorplan_top_sits_above_the_cards(site: Path) -> None:
    page = _floor_page(site, {"floorplan": "top"})
    assert "floor-summary-image" not in page
    assert '<img src="img/floors/floor_L00.png" alt="Floor Plan" class="floor-summary-plan-img img-fluid rounded">' in page
    assert page.index("floor-summary-plan-img") < page.index("floor-summary-center-block")


def test_a_level_overrides_the_site(site: Path) -> None:
    page = _floor_page(site, {"floorplan": "none"}, {"floorplan": "top"})
    assert "floor-summary-plan-img" in page


@pytest.mark.parametrize("columns", [1, 2, 4])
def test_meter_columns_sets_the_grid_width(site: Path, columns: int) -> None:
    page = _floor_page(site, {"meter_columns": columns})
    assert f'<div class="floor-three-column-grid floor-grid-cols-{columns}">' in page
    assert f"<!-- {columns} Column Layout -->" in page


def test_auto_columns_follow_the_cards(site: Path, tmp_path: Path) -> None:
    default = _floor_page(site)
    assert _floor_page(site, {"meter_columns": "auto"}) == default    # its cards use 3 columns
    level = build.read_levels()[0]
    cards = {"type": "cards", "cards": []}
    assert build.floor_layout(level, [cards] * 2)["columns"] == 2
    assert build.floor_layout(level, [cards] * 6)["columns"] == build.MAX_METER_COLUMNS
    assert build.floor_layout(level, [])["columns"] == 1               # no cards (a tenant's extra floor)


def test_summary_row_puts_every_card_in_one_row(site: Path) -> None:
    tenants, landlords = "Floor Tenants Electricity", "Floor Landlords Electricity"
    page = _floor_page(site, {"summary_layout": "row", "summary_cards": {
        "total": "Floor Total Electricity", "tenants": tenants, "landlords": landlords}})
    row = page.split('<div class="floor-summary-dual-block">')[1].split("floor-summary-image")[0]
    assert [t for t in ("Floor Total Electricity", tenants, landlords) if t in row] == [
        "Floor Total Electricity", tenants, landlords]
    assert "floor-summary-center-block" not in page                    # the total card is one of the row
    assert "Line 2" not in page


def test_tenant_pages_follow_their_level(site: Path) -> None:
    build.data_path("tenants.yaml").write_text("tenants:\n  Acme: {extra_floors: [L00]}\n", encoding="utf-8")
    _configure(site, {"floorplan": "right"}, {"floorplan": "none", "meter_columns": 2})
    build.build_site(["tenants"])
    page = (build.TENANTS_DIR / "acme" / "floor_L00.htm").read_text(encoding="utf-8")
    assert "Floor Plan" not in page
    assert '<div class="floor-section floor-section-summary">' in page   # --single-row's min-height holds the image
    assert "floor-grid-cols-2" in page


def test_check_warns_when_cards_outgrow_the_grid(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _configure(site, {"meter_columns": 2})
    assert build.validate(["floors"]) == 0
    assert ("floors.yaml: 'floor_L00' has cards in 3 columns (03_meters.yaml `column`) "
            "but its grid has 2 (meter_columns: 2): the rest wrap onto a new row") in capsys.readouterr().out
