#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import os
import subprocess
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

_mod_path = str(Path(__file__).parent / "skills" / "session-review" / "find_transcript.py")
find_transcript = SourceFileLoader("find_transcript", _mod_path).load_module()

SCRIPT = _mod_path


def test_encode_cwd_replaces_slashes():
    assert find_transcript.encode_cwd("/Users/x/y") == "-Users-x-y"


def test_encode_cwd_handles_root():
    assert find_transcript.encode_cwd("/") == "-"


def test_find_latest_transcript_picks_most_recent(tmp_path: Path):
    cwd = "/Users/test/proj"
    transcript_dir = tmp_path / find_transcript.encode_cwd(cwd)
    transcript_dir.mkdir()

    older = transcript_dir / "older.jsonl"
    newer = transcript_dir / "newer.jsonl"
    older.write_text("{}\n")
    time.sleep(0.05)
    newer.write_text("{}\n")

    found = find_transcript.find_latest_transcript(tmp_path, cwd)
    assert found == newer


def test_find_latest_transcript_returns_none_when_dir_missing(tmp_path: Path):
    assert find_transcript.find_latest_transcript(tmp_path, "/does/not/exist") is None


def test_find_latest_transcript_returns_none_when_dir_empty(tmp_path: Path):
    cwd = "/Users/test/empty"
    (tmp_path / find_transcript.encode_cwd(cwd)).mkdir()
    assert find_transcript.find_latest_transcript(tmp_path, cwd) is None


def test_find_latest_transcript_ignores_non_jsonl(tmp_path: Path):
    cwd = "/Users/test/proj"
    d = tmp_path / find_transcript.encode_cwd(cwd)
    d.mkdir()
    (d / "notes.txt").write_text("hello")
    assert find_transcript.find_latest_transcript(tmp_path, cwd) is None


def test_script_prints_path_and_exits_zero(tmp_path: Path):
    cwd = "/Users/test/proj"
    d = tmp_path / find_transcript.encode_cwd(cwd)
    d.mkdir()
    target = d / "session.jsonl"
    target.write_text("{}\n")

    result = subprocess.run(
        [sys.executable, SCRIPT, "--cwd", cwd, "--projects-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(target)


def test_script_exits_nonzero_when_missing(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, SCRIPT, "--cwd", "/no/such/dir", "--projects-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "No transcript found" in result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
