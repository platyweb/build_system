"""Every engine template is rendered by at least one example site, so the
examples' goldens cover it: an engine change that breaks a page type then
shows up in `regress.py check`, not first on a building's site."""
from __future__ import annotations

import sys
from pathlib import Path

import jinja2
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import regress  # noqa: E402

TEMPLATES = ROOT / "_templates"

# Templates no example renders yet, and why. Each comes out of this list as
# soon as an example renders it.
NOT_YET = {
    # The dials and energy flow pages load d3 (js/d3/7/*), which the engine
    # doesn't ship yet (HANDOFF.md "Rest of Phase 7"); an example that
    # rendered them would reference files it doesn't ship.
    "dials.html.j2",
    "energy_flow.html.j2",
}


def _rendered_by_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """The engine template names each example's own build loads (extends,
    imports and includes too)."""
    loaded: set[str] = set()
    get_source = jinja2.FileSystemLoader.get_source

    def recording(self, environment, template):
        source, filename, uptodate = get_source(self, environment, template)
        if Path(filename).resolve().is_relative_to(TEMPLATES):
            loaded.add(Path(filename).resolve().relative_to(TEMPLATES).as_posix())
        return source, filename, uptodate

    monkeypatch.setattr(jinja2.FileSystemLoader, "get_source", recording)
    for site in regress.discover_sites():
        if site.parent.name != "examples":
            continue
        build.configure(site, tmp_path / site.name)
        build.build_site(build.resolve_modules(None))
    return loaded


def test_every_engine_template_is_rendered_by_an_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = {p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*.j2")}
    loaded = _rendered_by_examples(tmp_path, monkeypatch)
    assert sorted(engine - loaded - NOT_YET) == [], "no example renders these; give one the data for them"
    assert sorted(NOT_YET & loaded) == [], "an example renders these now; take them out of NOT_YET"
