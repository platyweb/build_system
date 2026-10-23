"""regress.py's own plumbing: the stale-_baseline guard on `check`'s diffs,
and `diff --against`, which builds the site data with an older engine."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import regress  # noqa: E402


def _files(root: Path, text: str) -> Path:
    (root / "css").mkdir(parents=True)
    (root / "css" / "a.css").write_text(text, encoding="utf-8")
    return root


def test_a_stale_baseline_copy_is_reported_not_diffed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    baseline, fresh = _files(tmp_path / "base", "old\n"), _files(tmp_path / "fresh", "new\n")
    golden = {"css/a.css": hashlib.sha256(b"golden\n").hexdigest()}
    regress.print_diffs(["css/a.css"], baseline, fresh, golden=golden)
    out = capsys.readouterr().out
    assert "stale" in out and "-old" not in out


def test_a_current_baseline_copy_is_diffed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    baseline, fresh = _files(tmp_path / "base", "old\n"), _files(tmp_path / "fresh", "new\n")
    golden = {"css/a.css": hashlib.sha256(b"old\n").hexdigest()}
    regress.print_diffs(["css/a.css"], baseline, fresh, golden=golden)
    out = capsys.readouterr().out
    assert "-old" in out and "+new" in out


def test_engine_at_extracts_the_committed_engine(tmp_path: Path) -> None:
    engine = regress.engine_at("HEAD", tmp_path)
    assert (engine / "_build" / "build.py").is_file()
    assert not (engine / "site").exists()


def test_diff_finds_no_change_between_identical_engines(monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(regress, "engine_at", lambda ref, dest: regress.ROOT)
    assert regress.cmd_diff([ROOT / "examples" / "minimal"], None, "REF", keep=False) == 0
    assert "[acme-depot/site] identical" in capsys.readouterr().out
