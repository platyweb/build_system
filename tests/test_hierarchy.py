"""The meters hierarchy page walks each meter's parent. meters_hierarchy.yaml
is optional: without it the page has default texts, and its trees start at
the meters marked `parent: 0`, and those with no parent that feed another."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402


@pytest.fixture
def site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _page(tmp_path: Path) -> str:
    build.build_site(["meters_hierarchy"])
    return (tmp_path / "project" / "acme-depot" / "meters_hierarchy.htm").read_text(encoding="utf-8")


def test_without_its_file_the_page_starts_at_the_marked_roots(site: Path, tmp_path: Path) -> None:
    listed = build.data_path("meters_hierarchy.yaml")
    with_file = _page(tmp_path)
    listed.unlink()
    rows = build.read_meter_rows()
    assert sorted(r["id"] for r in rows if r["parent_id"] == 0) == [1, 10, 11]   # the roots its file lists
    page = _page(tmp_path)
    assert "<h1>Meters Hierarchy</h1>" in page and "Click on meters to expand/collapse child connections" in page
    assert page.replace("Search for a meter...", "Search for a meter (e.g., Lighting, Plant)...") == with_file


def test_an_unmarked_meter_that_feeds_others_is_a_root(site: Path, tmp_path: Path) -> None:
    build.data_path("meters_hierarchy.yaml").unlink()
    meters = build.data_path("meters.yaml")
    meters.write_text(meters.read_text(encoding="utf-8").replace("parent: 0, ", ""), encoding="utf-8")
    page = _page(tmp_path)
    assert "meter.id=1" in page and "meter.id=10\"" not in page   # 1 feeds others; gas (10) feeds nothing
