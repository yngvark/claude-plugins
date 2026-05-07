#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

_mod_path = str(Path(__file__).parent / "skills" / "public-ready" / "scan.py")
scan = SourceFileLoader("scan", _mod_path).load_module()

SCRIPT = _mod_path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


# ---------------------------------------------------------------------------
# publish_set
# ---------------------------------------------------------------------------


class TestPublishSet:
    def test_includes_tracked_file(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "tracked.txt").write_text("hello")
        _git(tmp_path, "add", "tracked.txt")
        _git(tmp_path, "commit", "-q", "-m", "init")

        files = scan.publish_set(tmp_path)

        assert "tracked.txt" in files

    def test_excludes_untracked_file(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "tracked.txt").write_text("hello")
        _git(tmp_path, "add", "tracked.txt")
        _git(tmp_path, "commit", "-q", "-m", "init")
        (tmp_path / "untracked.txt").write_text("nope")

        files = scan.publish_set(tmp_path)

        assert "tracked.txt" in files
        assert "untracked.txt" not in files

    def test_includes_staged_addition(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "first.txt").write_text("a")
        _git(tmp_path, "add", "first.txt")
        _git(tmp_path, "commit", "-q", "-m", "init")
        (tmp_path / "newly_staged.txt").write_text("b")
        _git(tmp_path, "add", "newly_staged.txt")

        files = scan.publish_set(tmp_path)

        assert "newly_staged.txt" in files

    def test_dedupes_when_file_is_both_tracked_and_staged(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "f.txt").write_text("a")
        _git(tmp_path, "add", "f.txt")
        _git(tmp_path, "commit", "-q", "-m", "init")
        (tmp_path / "f.txt").write_text("b")
        _git(tmp_path, "add", "f.txt")

        files = scan.publish_set(tmp_path)

        assert files.count("f.txt") == 1


# ---------------------------------------------------------------------------
# parse_findings
# ---------------------------------------------------------------------------


GITLEAKS_SAMPLE_JSON = """[
  {
    "RuleID": "aws-access-key",
    "Description": "AWS Access Key",
    "File": "src/config.py",
    "StartLine": 12,
    "Match": "AKIAIOSFODNN7EXAMPLE",
    "Secret": "AKIAIOSFODNN7EXAMPLE",
    "Tags": ["key", "AWS"]
  },
  {
    "RuleID": "generic-api-key",
    "Description": "Generic API Key",
    "File": "scripts/deploy.sh",
    "StartLine": 3,
    "Match": "api_key=\\"deadbeef\\"",
    "Secret": "deadbeef",
    "Tags": []
  }
]"""


class TestParseFindings:
    def test_parses_two_findings(self) -> None:
        findings = scan.parse_findings(GITLEAKS_SAMPLE_JSON)
        assert len(findings) == 2

    def test_finding_fields(self) -> None:
        findings = scan.parse_findings(GITLEAKS_SAMPLE_JSON)
        first = findings[0]
        assert first["file"] == "src/config.py"
        assert first["line"] == 12
        assert first["rule"] == "aws-access-key"
        assert first["description"] == "AWS Access Key"
        # Snippet should contain the match but should be safe to display
        assert "AKIA" in first["snippet"]

    def test_empty_array(self) -> None:
        assert scan.parse_findings("[]") == []

    def test_empty_string(self) -> None:
        # gitleaks may produce an empty file when there are no findings
        assert scan.parse_findings("") == []

    def test_null_value(self) -> None:
        # gitleaks emits "null" (not "[]") when no findings are written
        assert scan.parse_findings("null") == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))
