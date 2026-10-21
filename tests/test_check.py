"""build.py --check: the data checks, then a trial build in a temporary
directory whose rendered pages are checked — an unknown point or meter id is
an error, a referenced file the build doesn't produce is a warning."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import linkcheck  # noqa: E402


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A copy of examples/minimal, configured as the build's site."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def _warnings(out: str) -> list[str]:
    return [line.strip().removeprefix("[!] ") for line in out.splitlines() if line.strip().startswith("[!]")]


def test_check_builds_only_into_a_temporary_directory(site: Path, tmp_path: Path) -> None:
    assert build.validate() == 0
    assert not (tmp_path / "project").exists()
    assert build.OUT_ROOT == (tmp_path / "project").resolve()   # configure() restored


@pytest.mark.parametrize("example", ["minimal", "campus"])
def test_examples_reference_only_files_they_ship(example: str, tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    build.configure(ROOT / "examples" / example, tmp_path / "project")
    assert build.validate() == 0
    # The engine's project CSS isn't in _assets/ yet (HANDOFF.md open items)
    # — drop this exemption once it is.
    assert [w for w in _warnings(capsys.readouterr().out) if not w.startswith("css/project/")] == []


def test_unknown_point_on_a_rendered_page_is_an_error(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _edit(build.data_path("points.yaml"), "  nabers_rating:", "  nabers_score:")
    assert build.validate() == 1
    assert "data-point 'nabers_rating' (on building_performance.htm) isn't in points.yaml" in capsys.readouterr().out


def test_a_template_the_site_doesnt_render_isnt_checked(site: Path) -> None:
    # Without the building_performance module (and the extra that shows a
    # named point), its points needn't exist.
    _edit(build.BUILDING_FILE, "building_performance, ", "")
    _edit(build.data_path("sidebar.yaml"),
          '      - label: Performance\n        icon: bx-star\n        children:\n'
          '          - { label: "Building Performance", href: building_performance.htm }\n', "")
    extras = build.data_path("extras.yaml")
    extras.write_text(extras.read_text(encoding="utf-8").split("  # A live value card from a named point")[0],
                      encoding="utf-8")
    build.data_path("points.yaml").unlink()
    assert build.validate() == 0


def test_missing_pages_and_assets_are_warnings(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _edit(build.data_path("sidebar.yaml"), '{ label: "Hierarchy tree", href: meters_hierarchy.htm }',
          '{ label: "Hierarchy tree", href: meters_hierarchy.htm }\n          - { label: "Gone", href: gone.htm }')
    _edit(build.BUILDING_FILE, 'riser_card_link: "#"', 'riser_card_link: "/docs/other-site/risers.htm"')
    (site / "assets" / "img" / "floors" / "floor_L00.png").unlink()
    assert build.validate() == 0
    warnings = _warnings(capsys.readouterr().out)
    assert "gone.htm — not in the build; referenced by 1 file(s), e.g. js/project/2.0/sidebar-template.js" in warnings
    assert "img/floors/: floor_L00.png — not in the build; referenced by 1 file(s), e.g. floor_L00.htm" in warnings
    assert any(w.startswith("/docs/other-site/: risers.htm — not in the build") for w in warnings), warnings


def test_a_build_failure_is_an_error(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _edit(build.BUILDING_FILE, 'postcode: "AB1 2CD"\n', "")   # building_performance shows it
    assert build.validate() == 1
    assert "the build fails: UndefinedError" in capsys.readouterr().out


@pytest.mark.parametrize("url, expected", [
    ("img/x.png", "site/img/x.png"),
    ("../img/x.png?v=2#top", "img/x.png"),
    ("/docs/other/page.htm", "other/page.htm"),     # the output root is served at /docs/
    ("/Login.html?logout", None),                    # the controller's own
    ("https://example.com/x", None),
    ("//cdn.example.com/x.js", None),
    ("mailto:a@example.com", None),
    ("javascript:void(0)", None),
    ("#", None),
])
def test_resolve(url: str, expected: str | None, tmp_path: Path) -> None:
    out = tmp_path / "out"
    target = linkcheck.resolve(url, out / "site", out)
    assert (target.relative_to(out.resolve()).as_posix() if target else None) == expected
