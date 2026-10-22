"""Tenants: a `tenants:` catalog keyed by short name (the spelling a meter's
`tenant` uses), in tenants.yaml (or, before it had its own file, floors.yaml),
and each level's `cores:` in floors.yaml naming who holds each core. An older
site's slug-keyed tenants.yaml still builds the same pages, and --check holds
the cores against the catalog and the meters' tenant tags."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import meters_yaml  # noqa: E402

MINIMAL = ROOT / "examples" / "minimal"

# The same two tenants written both ways. Fern & Co holds the West core
# (meters 2, 3), Northwind the East one (meters 6, 7).
CATALOG = """
tenants:
  Fern & Co:
    name: "Fern and Company Ltd"
    index: {}
  NW/2:
    name: "Northwind"
    slug: northwind
    floors:
      L00: {heading: "Northwind Ground"}

floor_L00:
  label: "Ground Floor"
  cores:
    West: Fern & Co
    East: NW/2
"""
LEGACY_FLOORS = """
floor_L00:
  label: "Ground Floor"
"""
LEGACY_TENANTS = """
fern-co:
  display_name: "Fern and Company Ltd"
  registry_tenant: "Fern & Co"
  index: {}
northwind:
  display_name: "Northwind"
  registry_tenant: ["NW/2"]
  floors:
    L00: {heading: "Northwind Ground"}
"""
TAGS = {"2": "Fern & Co", "3": "Fern & Co", "6": "NW/2", "7": "NW/2"}


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal with meters tagged to two tenants."""
    site = tmp_path / "site"
    shutil.copytree(MINIMAL, site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    _tag_meters(TAGS)
    return site


def _tag_meters(tags: dict[str, str]) -> None:
    """Give the meters with these ids an explicit `tenant:` (and
    tenant_display: yes), rewriting the site's meters YAML."""
    rows = build.read_meter_rows()
    for r in rows:
        if str(r["id"]) in tags:
            r["tenant"], r["tenant_display"] = tags[str(r["id"])], True
    levels = build.read_levels()
    build.data_path("meters.yaml").write_text(
        meters_yaml.dump(rows, {lv["key"]: lv["cores"] for lv in levels}, [lv["key"] for lv in levels]),
        encoding="utf-8")


def _write(site: Path, floors: str, tenants: str | None = None) -> None:
    build.data_path("floors.yaml").write_text(floors, encoding="utf-8")
    if tenants is not None:
        build.data_path("tenants.yaml").write_text(tenants, encoding="utf-8")


def _warnings(out: str) -> list[str]:
    return [line.strip().removeprefix("[!] ") for line in out.splitlines() if line.strip().startswith("[!]")]


def test_catalog_names_slugs_and_order(site: Path) -> None:
    _write(site, CATALOG)
    tenants = build.read_tenants()
    assert [(t["slug"], t["name"], t["short_names"]) for t in tenants] == [
        ("fern-co", "Fern and Company Ltd", ["Fern & Co"]),   # slug from the short name
        ("northwind", "Northwind", ["NW/2"]),                 # `slug:` where that wouldn't do
    ]
    assert tenants[0]["data"] == {"index": {}}


def test_name_defaults_to_the_short_name(site: Path) -> None:
    _write(site, "tenants:\n  Fern & Co: {}\n" + LEGACY_FLOORS)
    assert [(t["slug"], t["name"]) for t in build.read_tenants()] == [("fern-co", "Fern & Co")]


def test_cores_are_roster_fields_not_page_data(site: Path) -> None:
    _write(site, CATALOG)
    [level] = build.read_levels()   # `tenants:` isn't a level
    assert level["cores"] == {"West": "Fern & Co", "East": "NW/2"}
    assert "cores" not in level["data"]


def test_legacy_tenants_yaml_builds_the_same_pages(site: Path, tmp_path: Path) -> None:
    def tenant_pages() -> dict[str, bytes]:
        out = tmp_path / "project" / "tenants"
        shutil.rmtree(out, ignore_errors=True)
        build.build_site(["tenants"])
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}

    _write(site, CATALOG)
    catalog_pages, catalog_menu = tenant_pages(), build._auto_tenants(build.read_meters())
    _write(site, LEGACY_FLOORS, LEGACY_TENANTS)
    assert tenant_pages() == catalog_pages
    assert build._auto_tenants(build.read_meters()) == catalog_menu
    assert sorted(catalog_pages) == ["fern-co/floor_L00.htm", "fern-co/index.htm", "fern-co/sidebar-template.js",
                                     "northwind/floor_L00.htm", "northwind/sidebar-template.js"]
    assert b"Fern and Company Ltd" in catalog_pages["fern-co/index.htm"]
    assert b"Northwind Ground" in catalog_pages["northwind/floor_L00.htm"]


@pytest.mark.parametrize(("floors", "tenants", "error"), [
    (CATALOG, LEGACY_TENANTS, "tenants are in floors.yaml `tenants:` now"),
    ("tenants:\n  Fern & Co: {display_name: Fern}\n" + LEGACY_FLOORS, None, r"unknown field\(s\) \['display_name'\]"),
    ("tenants:\n  Fern Co: {}\n  Fern & Co: {}\n" + LEGACY_FLOORS, None, "slug 'fern-co' is also"),
    ("tenants:\n  '&&': {}\n" + LEGACY_FLOORS, None, "slug '' can't be a folder name"),
])
def test_bad_catalog_stops_the_build(site: Path, floors: str, tenants: str | None, error: str) -> None:
    _write(site, floors, tenants)
    with pytest.raises(SystemExit, match=error):
        build.read_tenants()


@pytest.mark.parametrize("cores", ["[West, East]", "{West: }", "{West: [Fern & Co, NW/2]}"])
def test_a_core_names_exactly_one_tenant(site: Path, cores: str) -> None:
    _write(site, f"floor_L00:\n  cores: {cores}\n")
    with pytest.raises(SystemExit, match=r"`cores:` must map each core|core 'West' must name one tenant"):
        build.read_levels()


def test_check_accepts_matching_cores(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(site, CATALOG)
    assert build.validate() == 0
    assert not [w for w in _warnings(capsys.readouterr().out) if "core" in w]


def test_check_rejects_a_core_held_by_no_tenant(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(site, CATALOG.replace("East: NW/2", "East: NW2"))
    assert build.validate() == 1
    assert "floors.yaml 'floor_L00': core 'East' is 'NW2', which isn't in `tenants:`" in capsys.readouterr().out


def test_check_warns_when_a_tag_disagrees_with_the_cores(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Meter 7 sits in Northwind's East core but is tagged Fern & Co; meter 8
    # (a floor total, outside the cores) is tagged to a tenant with no core.
    _write(site, CATALOG.replace("tenants:\n", "tenants:\n  Quill: {}\n"))
    _tag_meters({"7": "Fern & Co", "8": "Quill"})
    assert build.validate() == 0
    warnings = _warnings(capsys.readouterr().out)
    assert ("03_meters.yaml: meter(s) [7] on 'L00' are tagged 'Fern & Co' but sit in core 'East', "
            "which floors.yaml gives to 'NW/2'") in warnings
    assert "03_meters.yaml: meter(s) [8] tag 'Quill' on 'L00', but floors.yaml gives them no core there" in warnings
    assert any(w.endswith("tenant 'Quill': holds no core on any floor (floors.yaml `cores:`)") for w in warnings)


def test_a_site_without_cores_isnt_checked_for_them(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(site, LEGACY_FLOORS, LEGACY_TENANTS)
    assert build.validate() == 0
    assert not [w for w in _warnings(capsys.readouterr().out) if "core" in w]


def _split_catalog() -> tuple[str, str]:
    """CATALOG as its own tenants.yaml: (floors.yaml, tenants.yaml)."""
    tenants, floors = CATALOG.split("\nfloor_L00:", 1)
    return "floor_L00:" + floors, tenants


def test_the_catalog_in_its_own_file_builds_the_same_pages(site: Path, tmp_path: Path) -> None:
    def tenant_pages() -> dict[str, bytes]:
        out = tmp_path / "project" / "tenants"
        shutil.rmtree(out, ignore_errors=True)
        build.build_site(["tenants"])
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}

    _write(site, CATALOG)
    in_floors = tenant_pages(), build.read_tenants()
    floors, tenants = _split_catalog()
    _write(site, floors, tenants)
    assert build.data_path("tenants.yaml").read_text(encoding="utf-8").startswith("\ntenants:")
    assert [{**t, "where": None} for t in build.read_tenants()] == [{**t, "where": None} for t in in_floors[1]]
    assert build.read_tenants()[0]["where"].endswith("tenants.yaml tenant 'Fern & Co'")
    assert tenant_pages() == in_floors[0]
    assert build.validate() == 0


@pytest.mark.parametrize(("floors", "tenants", "error"), [
    (CATALOG, _split_catalog()[1], "`tenants:` is in .*tenants.yaml now"),
    (_split_catalog()[0], _split_catalog()[1] + "\nnotes: {}\n", r"unknown key\(s\) \['notes'\]"),
])
def test_the_catalog_lives_in_one_place(site: Path, floors: str, tenants: str, error: str) -> None:
    _write(site, floors, tenants)
    with pytest.raises(SystemExit, match=error):
        build.read_tenants()
