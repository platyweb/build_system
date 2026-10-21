"""Components and extras: the published API stays backward compatible (an
older site's extras.yaml keeps building on a newer engine), placements are
checked against each component's declared options, and a site can add its
own components."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import components  # noqa: E402

PUBLISHED = yaml.safe_load((ROOT / "_components" / "published.yaml").read_text(encoding="utf-8"))
ENGINE = components.load_catalog(ROOT / "_components")
TEMPLATES = {"floor": "floor.html.j2", "incomer": "incomer.html.j2", "home": "home.html.j2"}


# ─── The published API: backward compatibility ───────────────────────────────

def test_published_slots_still_exist_and_every_slot_is_published() -> None:
    published = {kind: list(slots) for kind, slots in PUBLISHED["slots"].items()}
    for kind, slots in published.items():
        missing = [s for s in slots if s not in components.SLOTS.get(kind, ())]
        assert not missing, f"published {kind} slot(s) {missing} were removed or renamed — sites may use them"
    assert {k: list(v) for k, v in components.SLOTS.items()} == published, \
        "a new slot must be added to _components/published.yaml"


@pytest.mark.parametrize("name", sorted(PUBLISHED["components"]))
def test_published_component_keeps_its_options(name: str) -> None:
    contract = PUBLISHED["components"][name]
    assert name in ENGINE, f"published component '{name}' was removed — sites may use it"
    spec = ENGINE[name]
    required = sorted(o for o, s in spec["options"].items() if s["required"])
    assert required == sorted(contract["required"]), \
        f"{name}: required options changed — a new option needs a default that keeps today's output"
    accepted = set(spec["options"]) | set(spec["aliases"]) | set(spec["retired"])
    gone = sorted(set(contract["options"]) - accepted)
    assert not gone, f"{name}: published option(s) {gone} removed — keep them as `aliases:` or `retired:`"
    unpublished = sorted(set(spec["options"]) - set(contract["options"]))
    assert not unpublished, f"{name}: new option(s) {unpublished} must be added to _components/published.yaml"
    assert sorted(map(sorted, spec["one_of"])) == sorted(map(sorted, contract.get("one_of") or [])), \
        f"{name}: one_of groups changed — placements that satisfied them would break"
    for option, choices in (contract.get("choices") or {}).items():
        dropped = sorted(set(choices) - set(spec["options"].get(option, {}).get("choices") or []))
        assert not dropped, f"{name}: {option} no longer accepts {dropped} — choices only grow"
    unpinned = sorted(o for o, s in spec["options"].items()
                      if s["choices"] is not None and o not in (contract.get("choices") or {}))
    assert not unpinned, f"{name}: choices of {unpinned} must be added to _components/published.yaml"


def test_every_engine_component_is_published() -> None:
    assert sorted(ENGINE) == sorted(PUBLISHED["components"])


@pytest.mark.parametrize("kind", sorted(components.SLOTS))
def test_each_template_renders_its_slots_once_in_order(kind: str) -> None:
    text = (ROOT / "_templates" / TEMPLATES[kind]).read_text(encoding="utf-8")
    assert re.findall(r"slot\('([a-z_]+)'\)", text) == list(components.SLOTS[kind])


def test_every_engine_component_has_a_minimal_example_placement() -> None:
    # The examples stand in for older sites: each engine component is placed
    # somewhere with only its required options, and the goldens freeze what
    # that renders. A new required option, or a default that changes the
    # output, fails here or in the golden check.
    placements = [p for f in sorted((ROOT / "examples").glob("*/data/*extras.yaml"))
                  for p in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("extras") or []]
    def minimal(p: dict, spec: dict) -> bool:
        """Only the required options, plus one option from each one_of group."""
        given = set(p) - set(components.PLACEMENT_KEYS)
        required = {o for o, s in spec["options"].items() if s["required"]}
        rest = given - required
        return required <= given and all(len(rest & set(g)) == 1 for g in spec["one_of"]) \
            and rest <= {o for g in spec["one_of"] for o in g}

    for name, spec in ENGINE.items():
        assert any(p.get("component") == name and minimal(p, spec) for p in placements), \
            f"no example places '{name}' with just its required options (and one of each one_of group)"


# ─── Checking placements ─────────────────────────────────────────────────────

CATALOG = {"photo": {
    "dir": Path("."), "description": "test",
    "options": {"src":   {"required": True, "default": None, "doc": ".", "choices": None},
                "label": {"required": False, "default": "", "doc": ".", "choices": None}},
    "one_of": [], "aliases": {"caption": "label"}, "retired": ["border"],
}, "reading": {
    "dir": Path("."), "description": "test",
    "options": {"meter": {"required": False, "default": None, "doc": ".", "choices": None},
                "point": {"required": False, "default": "", "doc": ".", "choices": None},
                "field": {"required": False, "default": "demand", "doc": ".", "choices": ["demand", "daily"]}},
    "one_of": [["meter", "point"]], "aliases": {}, "retired": [],
}}
PAGES = {"floor_L00": "floor", "incomer_gas": "incomer", "home": "home"}


def _resolve(*placements: dict) -> tuple[list[dict], list[str], list[str]]:
    problems, warnings = [], []
    return components.resolve(list(placements), CATALOG, PAGES, problems, warnings), problems, warnings


def test_defaults_fill_in_and_kinds_or_keys_target_pages() -> None:
    resolved, problems, _ = _resolve({"component": "photo", "pages": ["floor", "home"], "slot": "top", "src": "a.png"})
    assert not problems
    assert resolved == [{"number": 1, "component": "photo", "slot": "top", "pages": {"floor", "home"},
                         "options": {"src": "a.png", "label": ""}}]


def test_old_option_names_keep_working() -> None:
    resolved, problems, warnings = _resolve(
        {"component": "photo", "pages": "floor_L00", "slot": "top", "src": "a.png", "caption": "Hi", "border": 2})
    assert not problems and resolved[0]["options"] == {"src": "a.png", "label": "Hi"}
    assert any("'caption' is now called 'label'" in w for w in warnings)
    assert any("'border' is retired" in w for w in warnings)


@pytest.mark.parametrize("placement, message", [
    ({"component": "video", "pages": ["home"], "slot": "top"}, "unknown component"),
    ({"component": "photo", "pages": ["floor_L99"], "slot": "top", "src": "a"}, "unknown page(s) ['floor_L99']"),
    ({"component": "photo", "pages": ["home"], "slot": "after_summary", "src": "a"}, "slot 'after_summary' isn't on home"),
    ({"component": "photo", "pages": ["home"], "slot": "top", "src": "a", "colour": "red"}, "unknown option 'colour'"),
    ({"component": "photo", "pages": ["home"], "slot": "top"}, "missing required option(s) ['src']"),
    ({"component": "photo", "slot": "top", "src": "a"}, "needs `pages:`"),
    ({"component": "reading", "pages": ["home"], "slot": "top"}, "give exactly one of meter, point"),
    ({"component": "reading", "pages": ["home"], "slot": "top", "meter": 1, "point": "x"},
     "give exactly one of meter, point (got meter, point)"),
    ({"component": "reading", "pages": ["home"], "slot": "top", "meter": 1, "field": "monthly"},
     "field: 'monthly' isn't one of demand, daily"),
])
def test_placement_problems(placement: dict, message: str) -> None:
    resolved, problems, _ = _resolve(placement)
    assert not resolved and len(problems) == 1 and message in problems[0], problems


def test_component_spec_needs_required_or_default(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "component.html.j2").write_text("", encoding="utf-8")
    (tmp_path / "x" / "component.yaml").write_text(
        "description: x\noptions:\n  a: {required: true, default: 1, doc: d}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="exactly one of `required: true` or `default:`"):
        components.load_catalog(tmp_path)


# ─── A site's own components, and --check ────────────────────────────────────

@pytest.fixture
def site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    build.configure(site, tmp_path / "project")
    return site


def test_a_site_component_is_placed_like_an_engine_one(site: Path, tmp_path: Path) -> None:
    badge = site / "components" / "badge"
    badge.mkdir(parents=True)
    (badge / "component.yaml").write_text(
        "description: A coloured badge.\noptions:\n  text: {required: true, doc: Badge text}\n", encoding="utf-8")
    (badge / "component.html.j2").write_text('<span class="badge">{{ text|e }}</span>\n', encoding="utf-8")
    extras = build.data_path("extras.yaml")
    extras.write_text(extras.read_text(encoding="utf-8")
                      + "  - {component: badge, pages: [floor], slot: top, text: Pilot site}\n", encoding="utf-8")
    assert build.validate() == 0
    build.build_site(["floors"])
    page = (tmp_path / "project" / "acme-depot" / "floor_L00.htm").read_text(encoding="utf-8")
    assert '<span class="badge">Pilot site</span>' in page


def test_check_warns_when_a_placement_never_renders(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    yaml_file = build.BUILDING_FILE
    yaml_file.write_text(yaml_file.read_text(encoding="utf-8").replace("home, ", ""), encoding="utf-8")
    assert build.validate() == 0
    assert "placement 3 (html) doesn't appear on home — its module is off" in capsys.readouterr().out


def test_check_reports_a_bad_placement(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    extras = build.data_path("extras.yaml")
    extras.write_text(extras.read_text(encoding="utf-8").replace("width: 480px", "widht: 480px"), encoding="utf-8")
    assert build.validate() == 1
    assert "extras.yaml placement 2 (image): unknown option 'widht'" in capsys.readouterr().out


def test_check_catches_a_live_value_with_an_unknown_point(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    extras = build.data_path("extras.yaml")
    extras.write_text(extras.read_text(encoding="utf-8").replace("point: energy_intensity", "point: energy_intensty"),
                      encoding="utf-8")
    assert build.validate() == 1
    assert "data-point 'energy_intensty' (on floor_L00.htm) isn't in points.yaml" in capsys.readouterr().out
