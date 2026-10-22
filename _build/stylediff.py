#!/usr/bin/env python3
"""
Compare what two builds look like: every element's computed style.

    _build/stylediff.py OLD_ROOT NEW_ROOT [--widths 480,1024,1920] [--themes light,dark] [--jobs 8]
                        [--pages REGEX]

OLD_ROOT and NEW_ROOT are two build output roots (`build.py --out DIR`) of
the same site, e.g. one built by the engine before a CSS change and one
after. Each page of NEW_ROOT is opened in headless Chromium at each width
and theme, next to its OLD_ROOT copy. Once the page's own scripts have run,
every element's computed style, its ::before and ::after, and its box are
compared. Exits 1 when anything differs, and prints what.

The pages are served from a local web server that adds two scripts as it
sends them: one sets the theme (localStorage "theme", as the sidebar's
toggle does), one records the styles. Nothing on disk changes. A first pass
compares one fingerprint per element; the elements that differ are fetched
again in full. Elements are matched by document order, so a markup change
that adds or removes elements shows as a count mismatch.

What it can't see: :hover and :focus styles, anything that needs the
controller's live data, and custom properties (--x) themselves, only what
they feed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import functools
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

# Runs in the page: fingerprint (or, for the indices in __detail, describe)
# every element once the page has settled.
RECORDER = r"""<script>
(function () {
  function hash(str) {
    var h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }
  // URLs resolve under each build's own folder (/old/…, /new/…): drop it.
  var root = location.origin + '/' + location.pathname.split('/')[1] + '/';
  function styles(el, pseudo) {
    var cs = getComputedStyle(el, pseudo), out = {};
    if (pseudo && (cs.content === 'none' || cs.content === 'normal')) return null;
    // Custom properties (--x) are left out: they draw nothing themselves, and
    // what they feed shows in the real properties. Sorted, as each browser
    // process lists properties in its own order.
    var names = [];
    for (var i = 0; i < cs.length; i++) if (cs[i].slice(0, 2) !== '--') names.push(cs[i]);
    names.sort().forEach(function (name) { out[name] = cs.getPropertyValue(name).split(root).join('/'); });
    return out;
  }
  function describe(el) {
    var r = el.getBoundingClientRect();
    return {tag: el.tagName.toLowerCase(), cls: el.getAttribute('class') || '',
            box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
            style: styles(el), before: styles(el, '::before'), after: styles(el, '::after')};
  }
  function record() {
    // Freeze every animation and transition at its start, so two renders agree.
    document.getAnimations().forEach(function (anim) { anim.pause(); anim.currentTime = 0; });
    var detail = new URLSearchParams(location.search).get('__detail');
    var want = detail === null ? null : detail.split(',').map(Number);
    // Elements that draw nothing are left out: a page script may add a
    // <script> late (a lazily loaded library), and that's no style change.
    var els = Array.prototype.slice.call(document.querySelectorAll('body *')).filter(function (el) {
      return !/^(SCRIPT|STYLE|LINK|TEMPLATE|NOSCRIPT)$/.test(el.tagName);
    });
    var out;
    if (want === null) {
      out = els.map(function (el) { var d = describe(el); return [d.tag, hash(JSON.stringify(d))]; });
    } else {
      out = {};
      want.forEach(function (i) { if (els[i]) out[i] = describe(els[i]); });
    }
    window.parent.__stylediffDone(out);
  }
  window.addEventListener('load', function () {
    setTimeout(function () { document.fonts.ready.then(record); }, 300);
  });
})();
</script>"""

# Each page starts from empty storage (a page may keep state there, e.g. which
# tree branches are open), then gets the theme.
THEME = ('<script>localStorage.clear(); sessionStorage.clear(); '
         'localStorage.setItem("theme", "{theme}");</script>')

# Loads each job's page in a frame of the job's width, one after another, and
# collects what the recorder reports. A page that never reports is skipped.
HARNESS = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><script>
var jobs = %s, results = {}, i = -1, frame = null, timer = null;
window.__stylediffDone = function (out) { finish(out); };
function finish(out) {
  clearTimeout(timer);
  if (i >= 0) { results[jobs[i].key] = out; }
  if (frame) { frame.remove(); frame = null; }
  i++;
  if (i >= jobs.length) {
    var holder = document.createElement('script');
    holder.type = 'application/json'; holder.id = '__results';
    holder.textContent = JSON.stringify(results).replace(/</g, '\\u003c');
    document.body.appendChild(holder);
    return;
  }
  frame = document.createElement('iframe');
  frame.style.width = jobs[i].width + 'px'; frame.style.height = '1000px'; frame.style.border = '0';
  frame.src = jobs[i].url;
  document.body.appendChild(frame);
  timer = setTimeout(function () { finish(null); }, 20000);
}
finish(undefined);
</script></body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the two roots, adding the theme and recorder scripts to .htm pages."""

    def log_message(self, *args) -> None:
        pass

    jobs: dict[str, list] = {}

    def do_GET(self) -> None:
        url = urllib.parse.urlsplit(self.path)
        if url.path.startswith("/__harness/"):
            body = (HARNESS % json.dumps(self.jobs[url.path.rsplit("/", 1)[1]])).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not url.path.endswith(".htm"):
            return super().do_GET()
        path = Path(self.translate_path(url.path))
        if not path.is_file():
            return super().do_GET()
        theme = urllib.parse.parse_qs(url.query).get("__theme", ["light"])[0]
        html = path.read_text(encoding="utf-8")
        html = re.sub(r"<head>", lambda m: m.group(0) + THEME.format(theme=theme), html, count=1)
        html = html.replace("</body>", RECORDER + "</body>", 1)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def chromium() -> str:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if shutil.which(name):
            return name
    raise SystemExit("stylediff: no chromium / google-chrome on PATH")


def profile_parent(browser: str) -> str | None:
    """Where a browser profile can live: a snap browser only reaches its own
    ~/snap/<name>/common, not /tmp or hidden home folders."""
    path = shutil.which(browser) or ""
    if path.startswith("/snap/"):
        common = Path.home() / "snap" / Path(path).name / "common"
        common.mkdir(parents=True, exist_ok=True)
        return str(common)
    return None


def render_batch(browser: str, base: str, name: str, jobs: list[dict]) -> dict:
    """Run one harness page over `jobs` ({key, url, width}); {key: record or None}."""
    Handler.jobs[name] = jobs
    # Each browser run gets its own profile: runs side by side would otherwise
    # share localStorage, and so one page's theme.
    with tempfile.TemporaryDirectory(prefix="stylediff-", dir=profile_parent(browser),
                                     ignore_cleanup_errors=True) as profile:
        proc = subprocess.run([browser, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                               f"--user-data-dir={profile}", "--window-size=2000,1100",
                               f"--virtual-time-budget={4000 * len(jobs)}", "--dump-dom", f"{base}/__harness/{name}"],
                              capture_output=True, text=True, timeout=120 + 30 * len(jobs))
    m = re.search(r'<script type="application/json" id="__results">(.*?)</script>', proc.stdout, re.S)
    if not m:
        raise RuntimeError(f"stylediff: the harness for {name} didn't finish:\n{proc.stderr[-2000:]}")
    return json.loads(m.group(1))


def diff_detail(a: dict, b: dict) -> list[str]:
    lines = []
    if a["cls"] != b["cls"]:
        lines.append(f"class: {a['cls']!r} → {b['cls']!r}")
    if a["box"] != b["box"]:
        lines.append(f"box: {a['box']} → {b['box']}")
    for part in ("style", "before", "after"):
        pa, pb = a[part] or {}, b[part] or {}
        if (a[part] is None) != (b[part] is None):
            gone = b[part] is None
            box = {k: (a if gone else b)[part].get(k) for k in ("content", "position", "width", "height", "transform")}
            lines.append(f"::{part} {'removed' if gone else 'added'} ({', '.join(f'{k} {v}' for k, v in box.items())})")
            continue
        for prop in sorted(set(pa) | set(pb)):
            if pa.get(prop) != pb.get(prop):
                where = "" if part == "style" else f"::{part} "
                lines.append(f"{where}{prop}: {pa.get(prop)!r} → {pb.get(prop)!r}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--widths", default="480,1024,1920")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--show", type=int, default=12, help="differing elements shown per page (default 12)")
    parser.add_argument("--pages", metavar="REGEX", help="only the pages whose path (under the root) matches")
    args = parser.parse_args(argv)
    widths = [int(w) for w in args.widths.split(",")]
    themes = args.themes.split(",")
    browser = chromium()

    serve_root = Path(args.old).resolve().parent
    if Path(args.new).resolve().parent != serve_root:
        raise SystemExit("stylediff: OLD_ROOT and NEW_ROOT must sit in the same folder")
    old_name, new_name = Path(args.old).resolve().name, Path(args.new).resolve().name
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(serve_root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    wanted = re.compile(args.pages) if args.pages else None
    old_pages = {p.relative_to(args.old).as_posix() for p in Path(args.old).rglob("*.htm")}
    new_pages = {p.relative_to(args.new).as_posix() for p in Path(args.new).rglob("*.htm")}
    if wanted:
        old_pages = {p for p in old_pages if wanted.search(p)}
        new_pages = {p for p in new_pages if wanted.search(p)}
    problems = 0
    for page in sorted(old_pages ^ new_pages):
        print(f"ONLY IN {'OLD' if page in old_pages else 'NEW'}  {page}")
        problems += 1

    def url(root: str, page: str, theme: str, detail: tuple[int, ...] | None = None) -> str:
        q = {"__theme": theme}
        if detail is not None:
            q["__detail"] = ",".join(map(str, detail))
        return f"{base}/{root}/{urllib.parse.quote(page)}?{urllib.parse.urlencode(q)}"

    jobs = [(page, w, t) for page in sorted(old_pages & new_pages) for w in widths for t in themes]

    def run(entries: list[tuple[str, str, int, str, list[int] | None]]) -> dict:
        """entries: (root, page, width, theme, detail) → {entry: record}, over --jobs browsers."""
        keyed = [{"key": str(n), "url": url(root, page, theme, detail), "width": width}
                 for n, (root, page, width, theme, detail) in enumerate(entries)]
        chunks = [keyed[k::args.jobs] for k in range(args.jobs) if keyed[k::args.jobs]]
        results: dict = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as pool:
            for part in pool.map(lambda c: render_batch(browser, base, f"b{id(c)}", c), chunks):
                results.update(part)
        return {entry: results.get(str(n)) for n, entry in enumerate(entries)}

    first = run([(root, page, w, t, None) for page, w, t in jobs for root in (old_name, new_name)])
    # A page script that runs late can make one render differ from the next.
    # A real difference shows every time, so render a differing page again,
    # up to twice, and keep only what repeats.
    for _attempt in range(2):
        flaky = [(page, w, t) for page, w, t in jobs
                 if first[(old_name, page, w, t, None)] != first[(new_name, page, w, t, None)]]
        if not flaky:
            break
        again = run([(root, page, w, t, None) for page, w, t in flaky for root in (old_name, new_name)])
        for page, w, t in flaky:
            if again[(old_name, page, w, t, None)] == again[(new_name, page, w, t, None)] or \
                    first[(old_name, page, w, t, None)] is None or first[(new_name, page, w, t, None)] is None:
                first[(old_name, page, w, t, None)] = again[(old_name, page, w, t, None)]
                first[(new_name, page, w, t, None)] = again[(new_name, page, w, t, None)]
    differing: dict[tuple[str, int, str], list[int] | str] = {}
    for page, w, t in jobs:
        a, b = first[(old_name, page, w, t, None)], first[(new_name, page, w, t, None)]
        if a is None or b is None:
            differing[(page, w, t)] = "the page didn't finish rendering"
        elif len(a) != len(b):
            tags_a, tags_b = [x[0] for x in a], [x[0] for x in b]
            at = next((i for i, (x, y) in enumerate(zip(tags_a, tags_b)) if x != y), min(len(a), len(b)))
            differing[(page, w, t)] = (f"{len(a)} elements → {len(b)} (from #{at}: "
                                       f"{tags_a[at:at + 4]} → {tags_b[at:at + 4]})")
        elif a != b:
            differing[(page, w, t)] = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]

    shown = {job: idx[:args.show] for job, idx in differing.items() if isinstance(idx, list)}
    detail = run([(root, page, w, t, tuple(idx)) for (page, w, t), idx in shown.items()
                  for root in (old_name, new_name)]) if shown else {}
    for (page, w, t), idx in sorted(differing.items()):
        problems += 1
        if isinstance(idx, str):
            print(f"DIFFERS  {page}  @{w}px {t}: {idx}")
            continue
        print(f"DIFFERS  {page}  @{w}px {t}: {len(idx)} element(s) differ")
        da = detail.get((old_name, page, w, t, tuple(shown[(page, w, t)]))) or {}
        db = detail.get((new_name, page, w, t, tuple(shown[(page, w, t)]))) or {}
        for i in shown[(page, w, t)]:
            ea, eb = da.get(str(i)), db.get(str(i))
            if ea is None or eb is None:
                continue
            print(f"  #{i} <{eb['tag']} class={eb['cls']!r}>")
            for line in diff_detail(ea, eb) or ["(the full styles agree: the page renders differently each time)"]:
                print(f"      {line}")
    server.shutdown()
    print(f"{len(jobs)} renders compared ({len(old_pages & new_pages)} pages × {len(widths)} widths × "
          f"{len(themes)} themes): {'no differences' if not problems else f'{problems} differ'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
