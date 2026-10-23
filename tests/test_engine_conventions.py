"""Conventions engine code and templates keep, checked so a slip fails here
rather than on one site (HANDOFF.md "Things that will bite you"):
- data files are found through build.data_path(), which knows their
  numbered names;
- every page renders through render_page(), which gives it `path_prefix`
  and stops a page field from hiding a template global;
- template URLs carry the path prefix, so they resolve from a building's
  folder too;
- the site's state lives in site_data, which the module files import
  instead of build, so there's one configured site however build.py runs."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402

ENGINE_CODE = sorted((ROOT / "_build").glob("*.py"))


# ─── Data files ──────────────────────────────────────────────────────────────
# (file, function) allowed to join a name onto the data directory: the
# helpers that find a data file, and one that names a new numbered file.
DATA_PATH_HELPERS = {
    ("site_data.py", "data_path"),
    ("site_data.py", "site_file"),
    ("import_meters.py", "target_path"),
    ("prefill.py", "target_path"),
}


def _joins_onto_data_dir(node: ast.BinOp) -> bool:
    """`DATA_DIR / "<name>"`, or `… / "data" / "<name>"`."""
    if not (isinstance(node.op, ast.Div) and isinstance(node.right, (ast.Constant, ast.JoinedStr))):
        return False
    left = node.left
    named = left.id if isinstance(left, ast.Name) else left.attr if isinstance(left, ast.Attribute) else None
    return named == "DATA_DIR" or (isinstance(left, ast.BinOp) and isinstance(left.right, ast.Constant)
                                   and left.right.value == "data")


def _data_dir_joins(path: Path):
    """(function, line) of each join onto the data directory in `path`."""
    def visit(node: ast.AST, function: str | None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield from visit(child, child.name)
                continue
            if isinstance(child, ast.BinOp) and _joins_onto_data_dir(child):
                yield function, child.lineno
            yield from visit(child, function)
    yield from visit(ast.parse(path.read_text(encoding="utf-8")), None)


@pytest.mark.parametrize("path", ENGINE_CODE, ids=lambda p: p.name)
def test_data_files_are_found_through_data_path(path: Path) -> None:
    # A site's data file may be numbered (04_points.yaml) or not (points.yaml):
    # build.data_path("points.yaml") finds either.
    if path.name == "migrate_js_data.py":
        pytest.skip("one-off Phase 2 migration; deleted once committed")
    hits = [f"{path.name}:{line} (in {function or 'module'})" for function, line in _data_dir_joins(path)
            if (path.name, function) not in DATA_PATH_HELPERS]
    assert not hits, "open data files with build.data_path(\"<name>.yaml\"): " + ", ".join(hits)


# ─── Rendering ───────────────────────────────────────────────────────────────
def _env() -> Environment:
    env = Environment(loader=DictLoader({"page.html.j2": "[{{ path_prefix }}img/x.png]"}),
                      undefined=StrictUndefined)
    env.globals["building"] = {"name": "Site"}
    return env


def test_every_page_gets_a_path_prefix() -> None:
    template = _env().get_template("page.html.j2")
    assert build.render_page(template, {}) == "[img/x.png]"
    assert build.render_page(template, {"path_prefix": "../"}) == "[../img/x.png]"


def test_a_page_field_named_like_a_template_global_stops_the_build() -> None:
    with pytest.raises(SystemExit, match="building, which would hide the template global"):
        build.render_page(_env().get_template("page.html.j2"), {"building": "north"})


@pytest.mark.parametrize("path", ENGINE_CODE, ids=lambda p: p.name)
def test_pages_render_through_render_page(path: Path) -> None:
    # A component renders its own options, not a page's context.
    if path.name in ("components.py", "migrate_js_data.py"):
        pytest.skip("not a page builder")
    hits = [f"{path.name}:{n}" for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"\.render\(\s*\*\*", line)]
    assert not hits, "render pages with render_page(template, ctx): " + ", ".join(hits)


# ─── URLs ────────────────────────────────────────────────────────────────────
# A relative src/href in a template resolves from the page's folder, so it
# starts with the path prefix ({{ _pp }} in templates extending base.html.j2,
# {{ path_prefix }} elsewhere) or is built from data ({{ … }}).
RELATIVE_URL = re.compile(r'\b(?:src|href)\s*=\s*["\'](?!\{\{|\{%|/|#|[a-z]+:|\.\./)([^"\']+)')
# (template, url): a relative URL that is right as it is.
SAME_FOLDER_LINKS = {
    ("_templates/tenant_sidebar.js.j2", "index.htm"),   # the tenant's own index, in its folder
}


def test_template_urls_carry_the_path_prefix() -> None:
    hits = [f"{rel}:{n}: {url}"
            for root in (ROOT / "_templates", ROOT / "_components")
            for path in sorted(root.rglob("*.j2"))
            for rel in [path.relative_to(ROOT).as_posix()]
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            for url in RELATIVE_URL.findall(line)
            if (rel, url) not in SAME_FOLDER_LINKS]
    assert not hits, "write these as {{ _pp }}<url> or {{ path_prefix }}<url>:\n" + "\n".join(hits)


# ─── Imports ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["site_data.py", "build_switchboards.py", "build_risers.py", "components.py",
                                  "jsblocks.py", "linkcheck.py", "meters_yaml.py", "generate_meter_registry.py"])
def test_only_scripts_import_build(name: str) -> None:
    # build.py imports these at the top. One that imported build back would
    # need a lazy import, and run as `python _build/build.py` it would get a
    # second, unconfigured copy of build; site_data has what they need.
    tree = ast.parse((ROOT / "_build" / name).read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "build" not in imported
