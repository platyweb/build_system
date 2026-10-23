"""site.yaml configuration: the utility catalog and the floor/tenant page
config — what they resolve to, and the errors a site author gets."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import generate_meter_registry as gmr  # noqa: E402
import site_data  # noqa: E402

CATALOG = {
    "electricity": {"label": "Electricity", "kind": "electric"},
    "solar":       {"label": "Solar PV",    "kind": "electric"},
    "lthw":        {"label": "LTHW",        "kind": "thermal"},
    "chw":         {"label": "CHW",         "kind": "thermal"},
    "water":       {"label": "Water",       "kind": "other"},
}


@pytest.fixture(autouse=True)
def site(tmp_path: Path) -> Path:
    """Configure the build on a copy of examples/minimal (error messages
    name its site.yaml)."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


@pytest.mark.parametrize("cell, function, code", [
    ("Electricity", "", "electricity"),               # label
    ("solar pv", "", "solar"),                         # label, any case
    ("LTHW", "", "lthw"),                              # code, any case
    ("Fluid energy", "HM/04/LTHW - L04 Tenants LTHW", "lthw"),   # category → thermal code in function
    ("Fluid energy", "CHW Basement Cooling", "chw"),
    ("lthw-virtual", "", "lthw-virtual"),              # virtual marker kept
    ("Steam", "", "Steam"),                            # unknown: passed through for --check to report
])
def test_utility_cells_resolve_to_catalog_codes(cell: str, function: str, code: str) -> None:
    assert gmr.normalise_utility(cell, function, CATALOG) == code


def test_zone_subtitles_follow_utility_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site_data, "UTILITIES", CATALOG, raising=False)
    assert build.derive_zone_location({"electricity", "lthw", "chw"}) == "Electrical & Heat Energy"
    assert build.derive_zone_location({"lthw"}) == "Heat Energy"
    assert build.derive_zone_location({"solar"}) == "Electricity"
    # No subtitle for this combination: the utilities' labels instead.
    assert build.derive_zone_location({"water"}) == "Water"


@pytest.mark.parametrize("utilities, message", [
    ({"Steam": {"label": "Steam", "kind": "thermal"}}, "must be lowercase"),
    ({"steam": {"label": "Steam", "kind": "hot"}}, "needs `kind:`"),
    ({}, "`utilities:` is required"),
])
def test_bad_utility_catalog(utilities: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        build.read_utilities({"utilities": utilities})


@pytest.mark.parametrize("config, message", [
    ({"floor_page": {"tabs": [{"id": "e", "label": "E", "slot": "electricity", "roles": ["nope"]}]}},
     r"lists role\(s\) \['nope'\]"),
    ({"floor_page": {"tabs": [{"id": "e", "label": "E"}]}}, "needs slot"),
    ({"floor_page": {"summary_cards": {"grand_total": "X"}}}, r"summary_cards \['grand_total'\]"),
    ({"floor_page": {"tabs": []}, "tenant_page": {"tabs": ["heat-report"]}}, r"tenant_page.tabs \['heat-report'\]"),
])
def test_bad_page_config(config: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        build.read_page_config(config)


def test_page_config_defaults() -> None:
    _roles, floor_page, tenant_page = build.read_page_config({})
    assert floor_page["tabs"] == [] and floor_page["summary_cards"] == {}
    assert floor_page["riser_card_link"] == "#" and floor_page["centre_zone"] is None
    assert floor_page["zone_suffix"] == {"centre": "", "side": ""}
    assert tenant_page == {"summary_label": "Floorplan", "tabs": []}
