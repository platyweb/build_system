"""
Components: small reusable pieces of page markup (an image, an HTML fragment,
…) that a site adds to engine pages without overriding their templates.

    _components/<name>/component.yaml     what it is and its options (the engine's catalog)
    _components/<name>/component.html.j2  its markup
    site/components/<name>/…               the site's own components, same format; one
                                           with an engine component's name replaces it
    site/data/extras.yaml                  placements: which component, on which pages,
                                           in which slot, with which option values

Engine page templates call slot("<name>") at fixed points (SLOTS). A slot
with nothing placed in it renders nothing at all, so a site without extras
builds byte-identically.

Backward compatibility: _components/published.yaml records every slot,
component and option a site may already use, and tests/test_components.py
holds the engine to it — an older site's extras.yaml keeps building, with
the same output, on a newer engine.

Stdlib + PyYAML + Jinja only; nothing here reads build.py's globals.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml
from jinja2 import Environment, pass_context

# Where each engine page kind takes extras, in page order. Published (see
# _components/published.yaml): add slots freely, never rename or remove one.
SLOTS: dict[str, tuple[str, ...]] = {
    "floor":   ("top", "after_summary", "after_risers", "bottom"),
    "incomer": ("top", "after_cards", "bottom"),
    "home":    ("top", "after_info_bar", "bottom"),
}
# A placement's own keys; every other key in it is a component option.
PLACEMENT_KEYS = ("component", "pages", "slot")


def load_catalog(*roots: Path) -> dict[str, dict]:
    """{name: spec} from every <root>/<name>/component.yaml. A later root
    replaces an earlier one's component of the same name (the site's
    components are passed after the engine's)."""
    catalog: dict[str, dict] = {}
    for root in roots:
        for spec_file in sorted(root.glob("*/component.yaml")) if root.is_dir() else []:
            catalog[spec_file.parent.name] = read_spec(spec_file)
    return catalog


def read_spec(spec_file: Path) -> dict:
    """A component.yaml, checked:
        description: one line — what it is
        options:     {<name>: {required: true, doc} | {default: <value>, doc}}
                     + optional `choices: [<value>, …]` — the values it accepts
        one_of:      [[<option>, …], …]   each group: a placement gives exactly one
        aliases:     {<old option name>: <current name>}   (renamed options)
        retired:     [<old option name>, …]                 (removed options, now ignored)
    Every option is either required or has a default; aliases and retired
    keep placements written for an older version of the component valid."""
    where = spec_file.as_posix()
    raw = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
    if not raw.get("description"):
        raise SystemExit(f"{where}: needs a one-line `description:`")
    if not (spec_file.parent / "component.html.j2").is_file():
        raise SystemExit(f"{where}: no component.html.j2 beside it")
    options: dict[str, dict] = {}
    for name, opt in (raw.get("options") or {}).items():
        opt = opt or {}
        if name in PLACEMENT_KEYS:
            raise SystemExit(f"{where}: option '{name}' clashes with a placement key ({', '.join(PLACEMENT_KEYS)})")
        if bool(opt.get("required")) == ("default" in opt):
            raise SystemExit(f"{where}: option '{name}' needs exactly one of `required: true` or `default:`")
        if not opt.get("doc"):
            raise SystemExit(f"{where}: option '{name}' needs a `doc:`")
        options[name] = {"required": bool(opt.get("required")), "default": opt.get("default"), "doc": opt["doc"],
                         "choices": list(opt["choices"]) if "choices" in opt else None}
    one_of = [[str(o) for o in group] for group in raw.get("one_of") or []]
    for group in one_of:
        bad = [o for o in group if o not in options or options[o]["required"]]
        if len(group) < 2 or bad:
            raise SystemExit(f"{where}: one_of group {group} needs two or more options that have defaults"
                             + (f" ({bad} don't)" if bad else ""))
    aliases = {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}
    for old, new in aliases.items():
        if new not in options:
            raise SystemExit(f"{where}: alias '{old}' → '{new}', which isn't an option")
    return {
        "dir": spec_file.parent,
        "description": str(raw["description"]),
        "options": options,
        "one_of": one_of,
        "aliases": aliases,
        "retired": [str(r) for r in raw.get("retired") or []],
    }


def resolve(placements: list[dict], catalog: dict[str, dict], pages: dict[str, str],
            problems: list[str], warnings: list[str]) -> list[dict]:
    """Check extras.yaml placements against the catalog and the site's pages
    ({page key: page kind}), and fill in option defaults. Returns the valid
    placements as {number (1-based, in file order), component, slot, pages
    (set of page keys and kinds), options}; reports the rest in `problems`."""
    resolved = []
    for i, raw in enumerate(placements or [], 1):
        raw = raw or {}
        name = raw.get("component")
        where = f"extras.yaml placement {i}" + (f" ({name})" if name else "")
        spec = catalog.get(name)
        if spec is None:
            problems.append(f"{where}: unknown component — available: {', '.join(sorted(catalog)) or 'none'}")
            continue

        targets = raw.get("pages")
        targets = [targets] if isinstance(targets, str) else [str(t) for t in targets or []]
        if not targets:
            problems.append(f"{where}: needs `pages:` — page keys (e.g. floor_L00) and/or kinds ({', '.join(SLOTS)})")
            continue
        unknown = [t for t in targets if t not in SLOTS and t not in pages]
        if unknown:
            problems.append(f"{where}: unknown page(s) {unknown} — a page key this site builds, or a kind: "
                            f"{', '.join(SLOTS)}")
            continue
        slot = raw.get("slot")
        kinds = sorted({t if t in SLOTS else pages[t] for t in targets})
        bad = [k for k in kinds if slot not in SLOTS[k]]
        if bad:
            problems.append(f"{where}: slot {slot!r} isn't on {'/'.join(bad)} pages — slots: "
                            + "; ".join(f"{k}: {', '.join(SLOTS[k])}" for k in bad))
            continue

        options = {}
        ok = True
        for key, value in raw.items():
            if key in PLACEMENT_KEYS:
                continue
            if key in spec["aliases"]:
                warnings.append(f"{where}: option '{key}' is now called '{spec['aliases'][key]}' — still works")
                key = spec["aliases"][key]
            elif key in spec["retired"]:
                warnings.append(f"{where}: option '{key}' is retired and ignored")
                continue
            elif key not in spec["options"]:
                problems.append(f"{where}: unknown option '{key}' — options: {', '.join(spec['options']) or 'none'}")
                ok = False
                continue
            choices = spec["options"][key]["choices"]
            if choices is not None and value not in choices:
                problems.append(f"{where}: {key}: {value!r} isn't one of {', '.join(map(str, choices))}")
                ok = False
                continue
            options[key] = value
        missing = [o for o, s in spec["options"].items() if s["required"] and o not in options]
        if missing:
            problems.append(f"{where}: missing required option(s) {missing}")
            ok = False
        for group in spec["one_of"]:
            given = [o for o in group if o in options]
            if len(given) != 1:
                problems.append(f"{where}: give exactly one of {', '.join(group)}"
                                + (f" (got {', '.join(given)})" if given else ""))
                ok = False
        if ok:
            for o, s in spec["options"].items():
                options.setdefault(o, s["default"])
            resolved.append({"number": i, "component": name, "slot": slot, "pages": set(targets),
                             "options": options})
    return resolved


def slot_renderer(env: Environment, catalog: dict[str, dict], placements: list[dict],
                  rendered: set[tuple[str, str]]) -> Callable:
    """The `slot` template global. slot("<name>") renders, in extras.yaml
    order, every placement for this page (by its page key or kind) in that
    slot — each as "\\n" + its markup, so an empty slot adds nothing. The
    page's context supplies page_kind / page_key (set by its builder) and
    path_prefix. A component also gets extra_id, "extra-<page key>-<placement
    number>": unique on the page, for DOM ids. Records (page key, slot) in
    `rendered`."""
    templates: dict[str, object] = {}

    @pass_context
    def slot(ctx, name: str) -> str:
        kind, key = ctx.get("page_kind"), ctx.get("page_key")
        if kind not in SLOTS or name not in SLOTS[kind]:
            raise SystemExit(f"template {ctx.name}: slot({name!r}) isn't in components.SLOTS[{kind!r}] "
                             "(and the page context needs page_kind + page_key)")
        rendered.add((key, name))
        out = []
        for p in placements:
            if p["slot"] == name and (kind in p["pages"] or key in p["pages"]):
                if p["component"] not in templates:
                    source = (catalog[p["component"]]["dir"] / "component.html.j2").read_text(encoding="utf-8")
                    templates[p["component"]] = env.from_string(source)
                html = templates[p["component"]].render(
                    **p["options"], page_kind=kind, page_key=key, path_prefix=ctx.get("path_prefix") or "",
                    extra_id=f"extra-{key}-{p['number']}")
                out.append("\n" + html.strip("\n"))
        return "".join(out)

    return slot
