"""data/points.yaml holds every BMS point the pages show, grouped by page:
named points, the floor summary cards, the incomer pages and the home page.
An older site's points.yaml `points:`, bms_bindings.yaml, incomers.yaml and
home.yaml build the same pages."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, whose points.yaml is grouped by page."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _grouped() -> dict:
    return yaml.safe_load(build.data_path("points.yaml").read_text(encoding="utf-8"))


def _write_grouped(data: dict) -> None:
    build.data_path("points.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _pages(tmp_path: Path) -> dict[str, bytes]:
    out = tmp_path / "project"
    shutil.rmtree(out, ignore_errors=True)
    build.build_site(build.resolve_modules(None))
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def test_the_sections_read_as_the_separate_files_did(site: Path) -> None:
    grouped = _grouped()
    assert build.read_points() == grouped["named"]
    assert build.read_incomers() == grouped["incomers"] and build.read_home() == grouped["home"]
    assert build.read_bms_bindings()[("floor_solar_demand", "L00")] == {
        "role": "floor_solar_demand", "floor": "L00", "id": "live-l00-solar-demand", "bacnet": "300|0|10740|85|-1"}


def test_an_older_sites_separate_files_build_the_same_pages(site: Path, tmp_path: Path) -> None:
    grouped_pages = _pages(tmp_path)
    grouped = _grouped()
    data = site / "data"
    (data / "04_points.yaml").write_text(yaml.safe_dump({"points": grouped["named"]}, sort_keys=False), encoding="utf-8")
    rows = [{"role": role, "floor": fk.removeprefix("floor_"), **b}
            for fk, roles in grouped["floors"].items() for role, b in roles.items()]
    (data / "05_bms_bindings.yaml").write_text(yaml.safe_dump({"bindings": rows}, sort_keys=False), encoding="utf-8")
    (data / "06_incomers.yaml").write_text(yaml.safe_dump(grouped["incomers"], sort_keys=False), encoding="utf-8")
    (data / "07_home.yaml").write_text(yaml.safe_dump(grouped["home"], sort_keys=False), encoding="utf-8")
    assert build.point_source("floors") == "bms_bindings.yaml"
    assert _pages(tmp_path) == grouped_pages


@pytest.mark.parametrize(("change", "error"), [
    (lambda d: d.update(points={}), "`points:` is the older spelling of `named:`"),
    (lambda d: d.update(sensors={}), r"unknown section\(s\) \['sensors'\]"),
    (lambda d: d["floors"].update(L01={}), "'L01' must be written floor_<key>"),
    (lambda d: d["floors"]["floor_L00"]["floor_today_solar"].update(format="energy"), "expected {id, bacnet}"),
])
def test_a_bad_points_file_stops_the_build(site: Path, change, error: str) -> None:
    grouped = _grouped()
    change(grouped)
    _write_grouped(grouped)
    with pytest.raises(SystemExit, match=error):
        build.read_bms_bindings()
        build.read_points()


def test_a_section_cant_also_be_its_older_file(site: Path) -> None:
    (site / "data" / "06_incomers.yaml").write_text("incomer_gas: {heading: Gas}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="its contents are points.yaml `incomers:` now"):
        build.read_incomers()


def test_check_names_the_section_a_floor_card_comes_from(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    grouped = _grouped()
    grouped["floors"]["floor_L0O"] = grouped["floors"].pop("floor_L00")      # letter O for zero
    _write_grouped(grouped)
    assert build.validate() == 1
    assert "points.yaml floors: floor 'L0O'" in capsys.readouterr().out
