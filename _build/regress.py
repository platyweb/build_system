#!/usr/bin/env python
"""
Golden-output regression harness for the build system.

Builds each site into a throwaway copy of the repo (the real project/
output directory is never touched), hashes every file the build leaves
under project/, and compares that against the sha256 manifests in the
site's golden/ directory. Any difference — changed, added or removed file —
fails.

Sites: site/ (this repo's building, if any) and every examples/<name>/ — any
directory with a site.yaml. --site DIR limits a run to one (repeatable).

Usage:
    python _build/regress.py check                     # fresh builds vs golden
    python _build/regress.py snapshot --site DIR       # first golden for a site
    python _build/regress.py snapshot --accept "why"   # deliberate re-baseline

Variants (each has its own manifest; a site is checked for every variant it
has a golden for, and a first snapshot records just `site`):
    site  — the site's own site.yaml `modules:` (what gets deployed).
    extra — every engine module except `pages`, so the modules the site
            doesn't enable (tenants, energy_flow, dials, switchboards, risers)
            are covered too. `pages` is left out because a site's frozen
            switchboard pages (swb_*.htm) would collide with the switchboards module's
            (build.py refuses two modules writing one file); the site variant
            covers it.

`snapshot` builds every variant twice under different PYTHONHASHSEEDs and
refuses to record a golden that isn't deterministic. It also keeps a full
copy of the build in _baseline/ (gitignored) so `check` can print readable
diffs instead of just hashes. Overwriting an existing golden requires
--accept "<reason>", which is appended to the site's golden/CHANGELOG — the
audit trail of every approved re-baseline.
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from build import MODULES, OUTPUT_MARKER

ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = ROOT / "_baseline"

# Engine dirs the build reads; copied wholesale into the throwaway workspace
# (the site under test is copied in as the workspace's site/).
COPY_DIRS = ("_build", "_templates", "_assets", "_components")

# variant → extra build.py arguments.
VARIANTS = {
    "site":  [],
    "extra": ["--modules", ",".join(name for name in MODULES if name != "pages")],
}

# Cap on unified-diff lines printed per changed file / per run, so one
# systematic change across 47 floor pages doesn't flood the terminal.
DIFF_LINES_PER_FILE = 40
DIFF_LINES_TOTAL = 400


# ─── Sites ───────────────────────────────────────────────────────────────────
def discover_sites() -> list[Path]:
    """site/ (if present), then every examples/<name>/ — each a directory
    holding a site.yaml."""
    sites = [ROOT / "site"] if (ROOT / "site" / "site.yaml").exists() else []
    return sites + sorted(p.parent for p in (ROOT / "examples").glob("*/site.yaml"))


def _site_slug(site: Path) -> str:
    building = yaml.safe_load((site / "site.yaml").read_text(encoding="utf-8")) or {}
    return building["slug"]


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ─── Building ────────────────────────────────────────────────────────────────
def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"regress: command failed ({proc.returncode}): {' '.join(cmd)}")


def build(site: Path, variant: str, seed: int) -> Path:
    """Build one site's variant in a fresh workspace; return the workspace root.

    build.py runs exactly as it does by hand: it stages project/ from
    _assets/ + site/assets/, regenerates METER_REGISTRY from meters.csv and
    writes every page.
    """
    workspace = Path(tempfile.mkdtemp(prefix=f"regress-{_site_slug(site)}-{variant}-"))
    ignore = shutil.ignore_patterns("__pycache__")
    for d in COPY_DIRS:
        shutil.copytree(ROOT / d, workspace / d, ignore=ignore)
    shutil.copytree(site, workspace / "site", ignore=ignore)

    env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONDONTWRITEBYTECODE": "1"}
    _run([sys.executable, "_build/build.py", *VARIANTS[variant]], workspace, env)
    return workspace


# ─── Manifests ───────────────────────────────────────────────────────────────
def manifest(workspace: Path) -> dict[str, str]:
    """{relpath: sha256} for every file under the workspace's project/ —
    except the build's own OUTPUT_MARKER, which is bookkeeping, not output."""
    out_root = workspace / "project"
    return {
        p.relative_to(out_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out_root.rglob("*"))
        if p.is_file() and p.relative_to(out_root).as_posix() != OUTPUT_MARKER
    }


def manifest_path(site: Path, variant: str) -> Path:
    return site / "golden" / f"{_site_slug(site)}.{variant}.sha256"


def golden_variants(site: Path) -> list[str]:
    """The variants this site has a golden for."""
    return [v for v in VARIANTS if manifest_path(site, v).exists()]


def write_manifest(path: Path, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for rel in sorted(entries):
            f.write(f"{entries[rel]}  {rel}\n")


def read_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        sha, rel = line.split("  ", 1)
        entries[rel] = sha
    return entries


def compare(golden: dict[str, str], fresh: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(changed, added, removed) relpaths."""
    changed = sorted(r for r in golden.keys() & fresh.keys() if golden[r] != fresh[r])
    added = sorted(fresh.keys() - golden.keys())
    removed = sorted(golden.keys() - fresh.keys())
    return changed, added, removed


# ─── Checks on a fresh build ─────────────────────────────────────────────────
def js_syntax_problems(workspace: Path) -> list[str]:
    """`node --check` every project-owned JS file (vendor bundles skipped).

    Catches a generated registry block that no longer parses — e.g. an
    unquoted value in METER_REGISTRY — which the hashes alone
    would only report as "changed".
    """
    node = shutil.which("node")
    if node is None:
        print("  (node not found — skipping JS syntax check)")
        return []
    out_root = workspace / "project"
    problems: list[str] = []
    for js in sorted(out_root.rglob("*.js")):
        rel = js.relative_to(out_root).as_posix()
        if "/bootstrap/" in f"/{rel}" or rel.endswith(".min.js"):
            continue
        proc = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        if proc.returncode != 0:
            problems.append(f"{rel}: {proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'syntax error'}")
    return problems


def print_diffs(changed: list[str], baseline_root: Path, fresh_root: Path) -> None:
    budget = DIFF_LINES_TOTAL
    for rel in changed:
        old, new = baseline_root / rel, fresh_root / rel
        if not old.exists():
            print(f"    ({rel}: no _baseline/ copy to diff against — run `snapshot` once to create it)")
            continue
        try:
            a = old.read_text(encoding="utf-8").splitlines(keepends=True)
            b = new.read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            print(f"    ({rel}: binary file differs)")
            continue
        diff = list(difflib.unified_diff(a, b, f"golden/{rel}", f"fresh/{rel}", n=1))
        shown = diff[: min(DIFF_LINES_PER_FILE, budget)]
        sys.stdout.writelines("    " + line if line.endswith("\n") else "    " + line + "\n" for line in shown)
        if len(diff) > len(shown):
            print(f"    … {len(diff) - len(shown)} more diff line(s) in {rel}")
        budget -= len(shown)
        if budget <= 0:
            print("    … diff output truncated")
            return


# ─── Commands ────────────────────────────────────────────────────────────────
def cmd_check(sites: list[Path], variants: tuple[str, ...] | None, keep: bool) -> int:
    failed = False
    for site in sites:
        slug = _site_slug(site)
        todo = list(variants) if variants else golden_variants(site)
        if not todo:
            raise SystemExit(f"regress: no golden for {_rel(site)} — run `snapshot --site {_rel(site)}` first")
        for variant in todo:
            golden_file = manifest_path(site, variant)
            if not golden_file.exists():
                raise SystemExit(f"regress: no golden for {slug}/{variant} — run `snapshot` first")
            print(f"[{slug}/{variant}] building…")
            workspace = build(site, variant, seed=0)
            fresh = manifest(workspace)
            changed, added, removed = compare(read_manifest(golden_file), fresh)
            js_problems = js_syntax_problems(workspace)

            if not (changed or added or removed or js_problems):
                print(f"[{slug}/{variant}] OK — {len(fresh)} files identical to golden")
                shutil.rmtree(workspace)
                continue

            failed = True
            print(f"[{slug}/{variant}] DIFFERS from golden: "
                  f"{len(changed)} changed, {len(added)} added, {len(removed)} removed")
            for label, rels in (("added", added), ("removed", removed)):
                for rel in rels:
                    print(f"  {label}: {rel}")
            for rel in changed:
                print(f"  changed: {rel}")
            for p in js_problems:
                print(f"  JS syntax: {p}")
            print_diffs(changed, BASELINE_DIR / slug / variant, workspace / "project")
            if keep:
                print(f"  fresh build kept at {workspace}")
            else:
                shutil.rmtree(workspace)
    return 1 if failed else 0


def cmd_snapshot(sites: list[Path], variants: tuple[str, ...] | None, accept: str | None) -> int:
    for site in sites:
        slug = _site_slug(site)
        # Default: re-record every golden the site already has, or just
        # `site` for a site's first snapshot.
        todo = list(variants) if variants else (golden_variants(site) or ["site"])
        existing = [v for v in todo if manifest_path(site, v).exists()]
        if existing and not accept:
            raise SystemExit(
                f"regress: {slug} already has a golden for {existing} — overwriting it is a re-baseline.\n"
                "  Run `check` to see what changed, then `snapshot --accept \"<reason>\"`."
            )

        summary: list[str] = []
        for variant in todo:
            print(f"[{slug}/{variant}] building twice (PYTHONHASHSEED=0, 1)…")
            ws0, ws1 = build(site, variant, seed=0), build(site, variant, seed=1)
            m0, m1 = manifest(ws0), manifest(ws1)
            if m0 != m1:
                changed, added, removed = compare(m0, m1)
                shutil.rmtree(ws1)
                raise SystemExit(
                    f"regress: {slug}/{variant} build is not deterministic across hash seeds "
                    f"({changed + added + removed}); kept seed-0 build at {ws0}"
                )
            js_problems = js_syntax_problems(ws0)
            if js_problems:
                raise SystemExit("regress: refusing to snapshot a build whose JS doesn't parse:\n  "
                                 + "\n  ".join(js_problems) + f"\n  build kept at {ws0}")

            golden_file = manifest_path(site, variant)
            if golden_file.exists():
                changed, added, removed = compare(read_manifest(golden_file), m0)
                summary.append(f"  {variant}: {len(changed)} changed, {len(added)} added, {len(removed)} removed")
            else:
                summary.append(f"  {variant}: initial golden, {len(m0)} files")
            write_manifest(golden_file, m0)

            baseline = BASELINE_DIR / slug / variant
            if baseline.exists():
                shutil.rmtree(baseline)
            baseline.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ws0 / "project", baseline, ignore=shutil.ignore_patterns(OUTPUT_MARKER))
            shutil.rmtree(ws0)
            shutil.rmtree(ws1)
            print(f"[{slug}/{variant}] golden written: {_rel(golden_file)} ({len(m0)} files)")

        reason = accept or "initial golden"
        with (site / "golden" / "CHANGELOG").open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"{datetime.date.today().isoformat()}  {slug}: {reason}\n")
            f.write("\n".join(summary) + "\n")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "snapshot"))
    parser.add_argument("--site", type=Path, action="append",
                        help="Site directory to check/snapshot (repeatable). Default: site/ + examples/*.")
    parser.add_argument("--variant", choices=tuple(VARIANTS), action="append",
                        help="Limit to one variant (repeatable). Default: every variant the site has a golden for.")
    parser.add_argument("--accept", metavar="REASON",
                        help="snapshot only: overwrite an existing golden, recording REASON in the CHANGELOG.")
    parser.add_argument("--keep", action="store_true",
                        help="check only: keep the fresh build directory when it differs, for inspection.")
    args = parser.parse_args(argv)
    sites = [s.resolve() for s in args.site] if args.site else discover_sites()
    for site in sites:
        if not (site / "site.yaml").exists():
            raise SystemExit(f"regress: {site} has no site.yaml")
    variants = tuple(args.variant) if args.variant else None

    if args.command == "check":
        return cmd_check(sites, variants, keep=args.keep)
    return cmd_snapshot(sites, variants, accept=args.accept)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
