"""
Reference checks on a built output root: what the deployed pages point at.

`build.py --check` builds the site into a throwaway output root and runs
these over it, so only what the site actually renders is checked (a
template for a module the site doesn't enable, or one its own override
replaces, never is):
  - every data-point / data-meter-id names a known point / meter;
  - every local URL a page uses — src/href attributes, the links in the
    sidebar it loads, a stylesheet's url()s — exists in the build;
  - every page loads the runtime scripts its markup needs (data-meter-id
    needs meter-templates.js, …).

Stdlib only; nothing here reads build.py's globals.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

# Optergy serves the output root (project/) at /docs/, so a root-absolute
# /docs/<path> link resolves to <output root>/<path> — another page of this
# build, a tenant page, or a file deployed outside it (another site's
# /docs/<slug>/…, a manual). Every other root-absolute URL (/Login.html,
# /js/…, /meters/…) is the controller's own and isn't checked.
DEPLOY_ROOT = "/docs/"

URL_ATTR = re.compile(r'(?:src|href)="([^"]*)"')
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)""")
SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc="([^"]+)"')
# A sidebar script's markup: the main sidebar-template.js (between its
# GENERATED markers) and each tenant's sidebar both declare it this way.
SIDEBAR_HTML = re.compile(r"const SIDEBAR_HTML = `(.*?)`;", re.S)
DATA_POINT = re.compile(r'data-point="([^"]+)"')
DATA_METER_ID = re.compile(r'data-(?:meter-id|swb-meter)="(\d+)"')
DATA_REPORT = re.compile(r'data-report="([^"]+)"')
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")   # http:, mailto:, javascript:, data:, …

# The attributes the runtime scripts act on: attribute → (the script, what the
# elements carrying it miss on a page that doesn't load that script).
RUNTIME_SCRIPTS = {
    "data-meter-id":    ("meter-templates.js",  "never get a live value"),
    "data-point":       ("meter-templates.js",  "never get a live value"),
    "data-floor-meter": ("meter-templates.js",  "are never built"),
    "data-floor-stats": ("meter-templates.js",  "are never built"),
    "data-swb-meter":   ("meter-templates.js",  "are never built"),
    "data-bacnet":      ("live-points.js",      "never get a live value"),
    "data-report":      ("reports.js",          "never become report cards"),
    "data-position":    ("position-handler.js", "are never positioned"),
    "data-dial-bacnet": ("energy-dials.js",     "never become dials"),
}


def resolve(url: str, base: Path, out_root: Path) -> Path | None:
    """The file `url` names when written in a page served from `base`, or
    None if it isn't the build's to check (external, in-page, or served by
    the controller)."""
    url = url.split("#")[0].split("?")[0]
    if not url or "{{" in url or url.startswith("//") or SCHEME.match(url):
        return None
    if url.startswith("/"):
        return (out_root / url[len(DEPLOY_ROOT):]).resolve() if url.startswith(DEPLOY_ROOT) else None
    return (base / url).resolve()


def references(out_root: Path) -> Iterator[tuple[Path, str, Path]]:
    """(referencing file, URL as written, file it resolves to) for every
    checkable URL in the build, each once:
      - a page's src/href attributes, against the page's folder;
      - the links in each sidebar script a page loads, against that page's
        folder (the sidebar's markup is injected into the page);
      - a stylesheet's url()s, against the stylesheet's folder."""
    out_root = out_root.resolve()
    sidebars: dict[Path, str] = {}
    seen: set[tuple[Path, str, Path]] = set()

    def refs(source: Path, base: Path, urls: Iterable[str]) -> Iterator[tuple[Path, str, Path]]:
        for url in urls:
            target = resolve(url, base, out_root)
            if target is not None and (source, url, target) not in seen:
                seen.add((source, url, target))
                yield source, url, target

    for page in sorted(out_root.rglob("*.htm")):
        text = page.read_text(encoding="utf-8")
        yield from refs(page, page.parent, URL_ATTR.findall(text))
        for src in SCRIPT_SRC.findall(text):
            script = resolve(src, page.parent, out_root)
            if script is None or not script.is_file():
                continue
            if script not in sidebars:
                m = SIDEBAR_HTML.search(script.read_text(encoding="utf-8"))
                sidebars[script] = m.group(1) if m else ""
            yield from refs(script, page.parent, URL_ATTR.findall(sidebars[script]))
    for css in sorted(out_root.rglob("*.css")):
        yield from refs(css, css.parent, CSS_URL.findall(css.read_text(encoding="utf-8", errors="replace")))


def _shown(path: Path, out_root: Path, site_dir: Path) -> str:
    """`path` as a site author reads it: relative to the site, or as its
    deployed /docs/ URL if it's elsewhere in the output root."""
    if path.is_relative_to(site_dir):
        return path.relative_to(site_dir).as_posix()
    return (DEPLOY_ROOT + path.relative_to(out_root).as_posix()).removesuffix("/.")


def missing_references(out_root: Path, site_dir: Path) -> list[str]:
    """One line per group of referenced-but-missing files, grouped under the
    outermost missing directory (or the existing folder they'd sit in), so a
    whole absent directory — another site's /docs/<slug>/, an unshipped
    css/project/ — reads as one line listing what's missing from it."""
    out_root, site_dir = out_root.resolve(), site_dir.resolve()
    groups: dict[Path, dict[Path, set[Path]]] = defaultdict(lambda: defaultdict(set))
    escaping: dict[str, set[Path]] = defaultdict(set)
    for source, url, target in references(out_root):
        if not target.is_relative_to(out_root):
            escaping[url].add(source)
            continue
        if target.exists():
            continue
        folder = target.parent
        while not folder.parent.exists():   # out_root exists, so this stops below it
            folder = folder.parent
        groups[folder][target].add(source)

    lines = []
    # This site's own files first, then the rest of /docs/.
    for folder in sorted(groups, key=lambda f: (not f.is_relative_to(site_dir), f)):
        targets = groups[folder]
        sources = sorted({s for refs in targets.values() for s in refs})
        names = ", ".join(sorted(t.relative_to(folder).as_posix() for t in targets))
        where = "" if folder == site_dir else _shown(folder, out_root, site_dir) + "/: "
        lines.append(f"{where}{names} — not in the build; referenced by "
                     f"{len(sources)} file(s), e.g. {_shown(sources[0], out_root, site_dir)}")
    for url in sorted(escaping):
        sources = sorted(escaping[url])
        lines.append(f"'{url}' climbs out of the output root; written in "
                     f"{len(sources)} file(s), e.g. {_shown(sources[0], out_root, site_dir)}")
    return lines


def _pages_shown(pages: set[Path], out_root: Path, site_dir: Path) -> str:
    """Up to three of `pages`, as a site author reads them, and how many more."""
    shown = [_shown(p, out_root, site_dir) for p in sorted(pages)]
    return ", ".join(shown[:3]) + (f" (+{len(shown) - 3} more)" if len(shown) > 3 else "")


def unloaded_scripts(out_root: Path, site_dir: Path) -> list[str]:
    """One line per runtime script that pages need but don't load: an element
    with data-meter-id, data-report, … (RUNTIME_SCRIPTS) does nothing unless
    its page loads the script that acts on it. A site template override that
    leaves the script out would otherwise fail silently, on the controller."""
    out_root, site_dir = out_root.resolve(), site_dir.resolve()
    missing: dict[tuple[str, str], set[Path]] = defaultdict(set)
    for page in sorted(out_root.rglob("*.htm")):
        text = page.read_text(encoding="utf-8")
        loaded = {src.split("?")[0].rsplit("/", 1)[-1] for src in SCRIPT_SRC.findall(text)}
        for attr, (script, _effect) in RUNTIME_SCRIPTS.items():
            if script not in loaded and re.search(rf'(?<![\w-]){attr}="', text):
                missing[(attr, script)].add(page)
    return [f"{_pages_shown(pages, out_root, site_dir)}: {attr} elements, but the page doesn't load "
            f"{script}, so they {RUNTIME_SCRIPTS[attr][1]}"
            for (attr, script), pages in sorted(missing.items())]


def unknown_names(out_root: Path, site_dir: Path, points: Iterable[str], meter_ids: Iterable[int],
                  report_urls: Iterable[str] = ()) -> list[str]:
    """One line per data-point / data-meter-id (or data-swb-meter) /
    data-report on a built page that names no point in points.yaml / meter
    in meters.csv / chart URL in reports.yaml `urls:`."""
    out_root, site_dir = out_root.resolve(), site_dir.resolve()
    points, meter_ids, report_urls = set(points), set(meter_ids), set(report_urls)
    bad_points: dict[str, set[Path]] = defaultdict(set)
    bad_meters: dict[int, set[Path]] = defaultdict(set)
    bad_reports: dict[str, set[Path]] = defaultdict(set)
    for page in sorted(out_root.rglob("*.htm")):
        text = page.read_text(encoding="utf-8")
        for name in set(DATA_POINT.findall(text)) - points:
            bad_points[name].add(page)
        for mid in {int(m) for m in DATA_METER_ID.findall(text)} - meter_ids:
            bad_meters[mid].add(page)
        for name in set(DATA_REPORT.findall(text)) - report_urls:
            bad_reports[name].add(page)

    def used_by(pages: set[Path]) -> str:
        return _pages_shown(pages, out_root, site_dir)

    return ([f"data-point '{n}' (on {used_by(bad_points[n])}) isn't in points.yaml" for n in sorted(bad_points)]
            + [f"meter id {m} (on {used_by(bad_meters[m])}) isn't a meter in the meters file" for m in sorted(bad_meters)]
            + [f"data-report '{n}' (on {used_by(bad_reports[n])}) has no chart URL in reports.yaml `urls:`"
               for n in sorted(bad_reports)])
