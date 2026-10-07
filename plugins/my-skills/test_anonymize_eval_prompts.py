#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import json
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "skills" / "anonymize-eval-prompts" / "check-rewrites.py"
cr = SourceFileLoader("cr", str(SCRIPT)).load_module()


def test_longest_shared_run_ignores_case_and_punctuation():
    a = cr.words("Can you deploy the billing service, please?")
    b = cr.words("please DEPLOY the billing service now")
    assert cr.longest_shared_run(a, b) == ["deploy", "the", "billing", "service"]


def test_words_keep_file_names_and_flags_whole():
    assert cr.words("edit packages.yml with --dry-run") == ["edit", "packages.yml", "with", "dry-run"]


def test_leaked_terms_are_case_insensitive():
    assert cr.leaked_terms("ask alice about it", ["Alice", "Bob", ""]) == ["Alice"]


def test_check_passes_a_real_rewrite():
    lines, ok = cr.check(
        [{
            "original": "Hey, can you look at why Alice's PR on acme-billing fails the terraform plan step?",
            "rewrite": "Why does the terraform plan fail on my teammate's PR?",
            "private": ["Alice", "acme-billing"],
        }],
        max_run=4,
    )
    assert ok, lines


def test_check_fails_on_long_copied_run():
    lines, ok = cr.check(
        [{"original": "why does the terraform plan step fail", "rewrite": "tell me why does the terraform plan step fail"}],
        max_run=4,
    )
    assert not ok
    assert "7 words" in lines[0]


def test_check_fails_on_leaked_term():
    lines, ok = cr.check(
        [{"original": "ping Alice", "rewrite": "ask alice", "private": ["Alice"]}],
        max_run=4,
    )
    assert not ok
    assert "private term still present: 'Alice'" in lines[1]


def test_cli_exit_code(tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"original": "a b c d e f", "rewrite": "a b c d e f"}]))
    fail = subprocess.run([sys.executable, str(SCRIPT), str(cases)], capture_output=True, text=True)
    assert fail.returncode == 1
    ok = subprocess.run([sys.executable, str(SCRIPT), str(cases), "--max-run", "6"], capture_output=True, text=True)
    assert ok.returncode == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
