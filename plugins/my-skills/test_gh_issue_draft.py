#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "skills" / "gh-issue-draft" / "issue-draft.py"
idr = SourceFileLoader("idr", str(SCRIPT)).load_module()

# Stands in for `gh`. It keeps issues in a JSON file and stores bodies the way GitHub returns
# them after a web edit: CRLF line endings and no trailing newline.
FAKE_GH = """
import json, os, sys

state_path = os.environ["FAKE_GH_STATE"]
with open(state_path) as f:
    state = json.load(f)
args = sys.argv[1:]

def opt(name):
    return args[args.index(name) + 1] if name in args else None

def stored(path):
    with open(path) as f:
        return f.read().rstrip("\\n").replace("\\n", "\\r\\n")

repo = opt("-R")
if args[:2] == ["issue", "create"]:
    number = str(len(state) + 1)
    state[number] = {"title": opt("--title"), "body": stored(opt("--body-file"))}
    print(f"https://github.com/{repo}/issues/{number}")
elif args[:2] == ["issue", "view"]:
    print(json.dumps(state[args[2]]))
elif args[:2] == ["issue", "edit"]:
    state[args[2]]["body"] = stored(opt("--body-file"))
    if opt("--title"):
        state[args[2]]["title"] = opt("--title")
    print(f"https://github.com/{repo}/issues/{args[2]}")
else:
    sys.exit("unexpected gh call: " + " ".join(args))

with open(state_path, "w") as f:
    json.dump(state, f)
"""


@pytest.fixture
def github(tmp_path, monkeypatch):
    fake = tmp_path / "gh"
    fake.write_text(f"#!{sys.executable}\n{FAKE_GH}")
    fake.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text("{}")
    monkeypatch.setenv("ISSUE_DRAFT_GH", str(fake))
    monkeypatch.setenv("FAKE_GH_STATE", str(state))

    class GitHub:
        def issues(self):
            return json.loads(state.read_text())

        def set_body(self, number, body):
            issues = self.issues()
            issues[number]["body"] = body
            state.write_text(json.dumps(issues))

    return GitHub()


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=os.environ)


def test_normalize_ignores_crlf_and_trailing_newlines():
    assert idr.normalize("a\r\nb\r\n\n") == idr.normalize("a\nb")


def test_create_publishes_the_draft_and_saves_the_base(tmp_path, github):
    draft = tmp_path / "issue.md"
    draft.write_text("# Beskrivelse\n\nBroken.\n")

    result = run("create", "o/r", str(draft), "--title", "Broken thing")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://github.com/o/r/issues/1"
    assert github.issues()["1"]["title"] == "Broken thing"
    assert idr.normalize(github.issues()["1"]["body"]) == "# Beskrivelse\n\nBroken."
    assert (tmp_path / "issue.md.base").exists()


def test_edit_replaces_the_body_when_nobody_else_changed_it(tmp_path, github):
    draft = tmp_path / "issue.md"
    draft.write_text("first\n")
    run("create", "o/r", str(draft), "--title", "t")
    draft.write_text("second\n")

    result = run("edit", "o/r", "1", str(draft), "--title", "new title")

    assert result.returncode == 0, result.stderr
    assert idr.normalize(github.issues()["1"]["body"]) == "second"
    assert github.issues()["1"]["title"] == "new title"


def test_edit_refuses_when_the_issue_changed_on_github(tmp_path, github):
    draft = tmp_path / "issue.md"
    draft.write_text("first\n")
    run("create", "o/r", str(draft), "--title", "t")
    github.set_body("1", "first\r\nplus a teammate's line")
    draft.write_text("second\n")

    result = run("edit", "o/r", "1", str(draft))

    assert result.returncode == 2
    assert "+plus a teammate's line" in result.stdout
    assert github.issues()["1"]["body"] == "first\r\nplus a teammate's line"
    assert (tmp_path / "issue.md.live").read_bytes() == b"first\r\nplus a teammate's line"


def test_pull_then_edit(tmp_path, github):
    draft = tmp_path / "issue.md"
    draft.write_text("first\n")
    run("create", "o/r", str(draft), "--title", "t")
    pulled = tmp_path / "pulled.md"

    result = run("pull", "o/r", "1", str(pulled))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "t"
    assert pulled.read_text() == "first\n"
    pulled.write_text("edited\n")
    assert run("edit", "o/r", "1", str(pulled)).returncode == 0
    assert idr.normalize(github.issues()["1"]["body"]) == "edited"


@pytest.mark.usefixtures("github")
def test_pull_never_overwrites_a_draft(tmp_path):
    draft = tmp_path / "issue.md"
    draft.write_text("first\n")
    run("create", "o/r", str(draft), "--title", "t")

    result = run("pull", "o/r", "1", str(draft))

    assert result.returncode == 1
    assert "already exists" in result.stderr


@pytest.mark.usefixtures("github")
def test_edit_without_a_base_fails(tmp_path):
    draft = tmp_path / "issue.md"
    draft.write_text("body\n")

    result = run("edit", "o/r", "1", str(draft))

    assert result.returncode == 1
    assert "Run `pull` first" in result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
