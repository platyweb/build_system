"""Every class a project stylesheet styles is one the engine can produce: a
word in a template, component, project script or build module (or in a
site's data and pages), or a family built from data at runtime
(`meter-<utility>`, …). And every project stylesheet is one a template
links. Stops dead CSS creeping back."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "_assets" / "css" / "project" / "2.0"
# The stylesheets the engine's templates link (font.css comes in through
# style.css's @import). tenant-accordion.css goes with tenant-accordion.js,
# which no template loads yet.
STYLESHEETS = [CSS_DIR / name for name in ("style.css", "meters-hierarchy.css", "switchboard-widget.css",
                                           "dials.css", "sankey.css")]
UNLINKED = {"font.css", "tenant-accordion.css"}
SOURCES = ("_templates/**/*", "_components/**/*", "_assets/js/project/2.0/*.js", "_build/*.py",
           "examples/minimal/**/*", "examples/campus/**/*", "site/**/*")
SOURCE_SUFFIXES = {".j2", ".html", ".htm", ".js", ".py", ".yaml", ".yml", ".csv", ".svg"}
# Classes put together from data at runtime: meter-<utility code>,
# text-<size>, grid-cols-<n>, floor-grid-cols-<n>, swb-tie-<side>, status-<state>.
RUNTIME_PREFIXES = ("meter-", "text-", "grid-cols-", "floor-grid-cols-", "swb-tie-", "status-")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _engine_words() -> set[str]:
    words: set[str] = set()
    for pattern in SOURCES:
        for path in ROOT.glob(pattern):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES and "golden" not in path.parts:
                words |= set(TOKEN.findall(path.read_text(encoding="utf-8", errors="replace")))
    return words


def _selectors(css: str) -> list[str]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@(?:-webkit-)?keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    selectors = []
    for prelude in re.findall(r"([^{};]+)\{", css):
        prelude = prelude.strip()
        if not prelude.startswith("@"):
            selectors += [" ".join(s.split()) for s in re.split(r",(?![^(]*\))", prelude)]
    return selectors


def _required_classes(selector: str) -> list[str]:
    # A class inside :not() / :is() / :where() / :has() needn't exist.
    bare = re.sub(r":(not|is|where|has)\((?:[^()]|\([^()]*\))*\)", "", selector)
    bare = re.sub(r"\[[^\]]*\]", "", bare)
    return re.findall(r"\.([A-Za-z_][\w-]*)", bare)


def test_every_styled_class_is_one_the_engine_can_produce() -> None:
    words = _engine_words()
    dead = sorted({f"{sheet.name}: {selector}"
                   for sheet in STYLESHEETS
                   for selector in _selectors(sheet.read_text(encoding="utf-8"))
                   if any(c not in words and not c.startswith(RUNTIME_PREFIXES) for c in _required_classes(selector))})
    assert not dead, "selectors no template, script or data can match:\n" + "\n".join(dead)


def test_the_check_knows_a_dead_selector() -> None:
    assert _required_classes(".tree li:not(.collapsed) > .meter") == ["tree", "meter"]
    assert _selectors("@media (max-width: 1px) { .a, .b .c { x: y } }\n@keyframes k { 0% { x: y } }") == [".a", ".b .c"]


def test_every_project_stylesheet_is_linked() -> None:
    templates = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "_templates").rglob("*.j2"))
    linked = {name for name in re.findall(r"css/project/2\.0/([\w.-]+\.css)", templates)}
    assert linked == {p.name for p in STYLESHEETS}
    assert {p.name for p in CSS_DIR.glob("*.css")} == linked | UNLINKED
