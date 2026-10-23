"""The engine — everything a new site gets from the template — carries no
client's data: the runtime skeleton's generated blocks are empty, and no
client name or BACnet address is written into engine code. A site's data
lives in its site/ directory, which the template doesn't ship."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import jsblocks  # noqa: E402

SKELETON_JS = ROOT / "_assets" / "js" / "project" / "2.0"

# Names from the sites this engine was built on — none belongs in it.
CLIENT_NAMES = re.compile(r"\baon\b|st[ .'-]*peter|leadenhall|knight|carpmael|sodexo|/tlb/|/1sr/", re.I)
# A literal point address, "<device>|<object type>|<instance>|85|-1" — except
# a widget's own usage text (`?doipa=…`), which shows an example one.
BACNET_LITERAL = re.compile(r"(?<!doipa=)\b\d+\|\d+\|\d+\|85\|-1\b")

# The owner's examples in the old building.yaml layout, kept for now
# (2026-10-23): exactly these lines may name a client, and nothing else in
# them. examples/ ships with the template, so drop this before the template
# split (HANDOFF.md "Next steps").
KNOWN_CLIENT_LINES = {
    f"examples/{example}/building.yaml: {line}"
    for example in ("1lb", "2ml", "4ml", "6hl")
    for line in ("logo: img/knight_logo.svg", "email: service@knightcontrols.co.uk")
}

TEXT_SUFFIXES = {".js", ".css", ".j2", ".py", ".yaml", ".yml", ".html", ".htm", ".csv", ".md", ".txt", ".svg"}
SKIP = {
    Path(__file__).resolve(),                       # names the clients, to look for them
    ROOT / "_build" / "migrate_js_data.py",         # one-off Phase 2 migration; deleted once committed
}


def _files(*roots: Path):
    """The text files under each root directory, or a root that's a file
    itself (whatever its suffix)."""
    for root in roots:
        paths = [root] if root.is_file() else [p for p in sorted(root.rglob("*"))
                                               if p.is_file() and p.suffix in TEXT_SUFFIXES]
        for path in paths:
            if path.resolve() not in SKIP and "golden" not in path.parts and "__pycache__" not in path.parts:
                yield path


def _code(path: Path) -> str:
    """The file's text with its comments removed."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".j2":
        text = re.sub(r"\{#.*?#\}|<!--.*?-->", "", text, flags=re.S)
    elif path.suffix == ".js":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"(^|\s)//.*", r"\1", text)
    elif path.suffix == ".py":
        text = re.sub(r"#.*", "", text)
    return text


def test_no_client_names_in_the_engine_or_examples() -> None:
    hits = [f"{p.relative_to(ROOT)}:{n}: {line.strip()[:120]}"
            for p in _files(ROOT / "_assets", ROOT / "_templates", ROOT / "_build", ROOT / "_components",
                            ROOT / "examples", ROOT / "tests", *sorted((ROOT / ".githooks").iterdir()),
                            ROOT / "README.md", ROOT / "requirements.txt", ROOT / ".gitignore")
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
            if CLIENT_NAMES.search(line)
            and f"{p.relative_to(ROOT).as_posix()}: {line.strip()}" not in KNOWN_CLIENT_LINES]
    assert not hits, "\n".join(hits)


def test_the_known_client_lines_are_still_there() -> None:
    # A line in KNOWN_CLIENT_LINES that's gone (fixed, or the example deleted)
    # comes out of the list, so it can't excuse a new one.
    present = {f"{p.relative_to(ROOT).as_posix()}: {line.strip()}"
               for p in _files(ROOT / "examples")
               for line in p.read_text(encoding="utf-8", errors="replace").splitlines()}
    assert KNOWN_CLIENT_LINES <= present, sorted(KNOWN_CLIENT_LINES - present)


def test_no_bacnet_addresses_in_engine_code() -> None:
    # Example sites' data (examples/) holds addresses by design; the engine's
    # comments may show one as an illustration.
    hits = [f"{p.relative_to(ROOT)}: {m}"
            for p in _files(ROOT / "_assets" / "js" / "project", ROOT / "_templates", ROOT / "_build",
                            ROOT / "_components")
            for m in BACNET_LITERAL.findall(_code(p))]
    assert not hits, "\n".join(hits)


@pytest.mark.parametrize("js, markers, body", [
    ("meter-templates.js", jsblocks.METER_REGISTRY, "const METER_REGISTRY = [];"),
    ("meter-templates.js", jsblocks.POINTS, "const POINTS = {};"),
    ("meter-templates.js", jsblocks.BACNET_CONFIG, "const BACNET_CONFIG = { device: null, powerOffset: {} };"),
    ("reports.js", jsblocks.REPORT_URLS, "const ReportUrls = { reports: {} };"),
    ("reports.js", jsblocks.REPORT_CARDS, "const REPORT_CARDS = {};"),
    ("sidebar-template.js", jsblocks.SIDEBAR_HTML, "const SIDEBAR_HTML = ``;"),
    ("sidebar-template.js", jsblocks.SIDEBAR_RUNTIME, 'const SIDEBAR_RUNTIME_SRC = "js/project/2.0/sidebar.js";'),
    ("live-points.js", jsblocks.OVERRIDE_FILE, 'const LIVE_POINTS_OVERRIDE_FILE = "";'),
])
def test_skeleton_generated_blocks_are_empty(js: str, markers: tuple[str, str], body: str) -> None:
    # The build fills these in its staged copy only — a built block pasted
    # back into _assets/ would ship one site's data to every other.
    begin, end = markers
    assert f"{begin}\n{body}\n{end}" in (SKELETON_JS / js).read_text(encoding="utf-8")
