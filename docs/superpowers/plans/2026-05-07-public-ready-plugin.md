# `public-ready` Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `public-ready` Claude Code plugin: a pre-publication scanner that flags secrets (via gitleaks) and personal/internal info (via a Claude-driven layer) in repo content that would become visible on the next `git push`.

**Architecture:** A Claude Code plugin in the `yngvark/claude-plugins` marketplace. A `scan.py` Python wrapper invokes `gitleaks` against the "publish set" (files tracked at HEAD ∪ staged additions) and emits structured findings. A SKILL.md and `/public-ready` slash command both invoke the script, then drive Claude to perform the internal-info layer and emit a combined markdown report.

**Tech Stack:** Python 3.10+ (uv shebang scripts), `gitleaks` (system binary), pytest, GNU Make. Plugin layout mirrors the existing `gh-read` plugin.

**Spec:** [`docs/superpowers/specs/2026-05-07-public-ready-plugin-design.md`](../specs/2026-05-07-public-ready-plugin-design.md)

---

## File Structure

Files this plan creates or modifies (all paths relative to repo root):

```
plugins/public-ready/                              [new]
├── .claude-plugin/
│   └── plugin.json                                [new]
├── commands/
│   └── public-ready.md                            [new] - slash command
├── skills/
│   └── public-ready/
│       ├── SKILL.md                               [new] - skill metadata + body
│       └── scan.py                                [new] - gitleaks wrapper
├── test_public_ready.py                           [new] - pytest suite
├── Makefile                                       [new] - `make test`
└── README.md                                      [new] - user docs

.claude-plugin/marketplace.json                    [modify] - register plugin
README.md                                          [modify] - add plugin entry
```

Responsibilities:

- `scan.py` — single-file CLI. Three pure functions (`publish_set`, `parse_findings`, `format_report_section`) plus `main()` that wires them. Pure functions are unit-tested. `main()` orchestrates: check gitleaks → enumerate publish set → call gitleaks → print findings.
- `SKILL.md` — describes when the skill activates (natural-language triggers), what to do (run scan.py, then read publish-set files for internal/personal info), and how to format the final report.
- `commands/public-ready.md` — slash command body that delegates to the skill.
- `test_public_ready.py` — unit tests for pure functions; integration tests for `main()` covering the missing-gitleaks error path and a happy path with a stub gitleaks binary.

---

## Task 1: Scaffold plugin directory and register in marketplace

**Files:**
- Create: `plugins/public-ready/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Create plugin manifest**

Create `plugins/public-ready/.claude-plugin/plugin.json`:

```json
{
  "name": "public-ready",
  "version": "0.1.0",
  "description": "Pre-publication scan for the current repo. Flags secrets (via gitleaks) and personal/internal info (via Claude) in content that would become public on the next push.",
  "author": {
    "name": "Yngvar Kristiansen"
  },
  "keywords": ["security", "secrets", "gitleaks", "pre-commit", "public-repo"],
  "license": "MIT"
}
```

- [ ] **Step 2: Register the plugin in the marketplace**

Open `.claude-plugin/marketplace.json` and append a new entry to the `plugins` array (after the `gh-read` entry):

```json
{
  "name": "public-ready",
  "source": "./plugins/public-ready",
  "description": "Pre-publication scan for the current repo. Flags secrets (via gitleaks) and personal/internal info (via Claude) in content that would become public on the next push.",
  "author": {
    "name": "Yngvar Kristiansen"
  }
}
```

Make sure to add a comma after the previous entry's closing `}` so the JSON stays valid.

- [ ] **Step 3: Verify marketplace.json is valid JSON**

Run: `python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))"`
Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add plugins/public-ready/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "Scaffold public-ready plugin and register in marketplace"
```

---

## Task 2: Write failing tests for `publish_set()`

This task introduces the test file and tests for the publish-set enumeration. We do not implement `publish_set` yet — the tests must fail first.

**Files:**
- Create: `plugins/public-ready/test_public_ready.py`

- [ ] **Step 1: Write the failing tests**

Create `plugins/public-ready/test_public_ready.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py`
Expected: errors importing `scan` (file does not exist yet), or all four tests fail with `AttributeError: module 'scan' has no attribute 'publish_set'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add plugins/public-ready/test_public_ready.py
git commit -m "Add failing tests for public-ready publish_set enumeration"
```

---

## Task 3: Implement `publish_set()` and make Task 2 tests pass

**Files:**
- Create: `plugins/public-ready/skills/public-ready/scan.py`

- [ ] **Step 1: Create the scan.py skeleton with `publish_set`**

Create `plugins/public-ready/skills/public-ready/scan.py`:

```python
#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

import shutil
import subprocess
import sys
from pathlib import Path


def publish_set(repo: Path) -> list[str]:
    """Return the list of repo-relative paths that would become public on the
    next `git push`: files tracked at HEAD plus staged additions not yet
    committed. Order is deterministic (sorted), entries are unique.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    tracked_paths = [p for p in tracked.split(b"\x00") if p]

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    staged_paths = [p for p in staged.split(b"\x00") if p]

    seen: set[bytes] = set()
    out: list[str] = []
    for p in tracked_paths + staged_paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p.decode("utf-8", errors="replace"))
    return sorted(out)
```

- [ ] **Step 2: Run the tests and confirm they pass**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestPublishSet`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/skills/public-ready/scan.py
git commit -m "Implement publish_set in public-ready scan.py"
```

---

## Task 4: Write failing tests for `parse_findings()`

`parse_findings(json_text)` parses gitleaks's JSON report into a normalized list of finding dicts.

**Files:**
- Modify: `plugins/public-ready/test_public_ready.py`

- [ ] **Step 1: Append the test class**

Append to `plugins/public-ready/test_public_ready.py` (after `TestPublishSet`):

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestParseFindings`
Expected: 5 failures, each with `AttributeError: module 'scan' has no attribute 'parse_findings'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add plugins/public-ready/test_public_ready.py
git commit -m "Add failing tests for public-ready parse_findings"
```

---

## Task 5: Implement `parse_findings()` and make Task 4 tests pass

**Files:**
- Modify: `plugins/public-ready/skills/public-ready/scan.py`

- [ ] **Step 1: Add the function**

Add to `plugins/public-ready/skills/public-ready/scan.py` (top, after the imports — also add `import json`):

```python
import json
```

Then add this function (place it after `publish_set`):

```python
def parse_findings(report_json: str) -> list[dict]:
    """Parse a gitleaks JSON report into normalized finding dicts.

    Each finding has: file, line, rule, description, snippet.
    """
    text = report_json.strip()
    if not text or text == "null":
        return []
    raw = json.loads(text)
    if raw is None:
        return []
    out: list[dict] = []
    for item in raw:
        match = item.get("Match", "") or item.get("Secret", "")
        out.append(
            {
                "file": item.get("File", ""),
                "line": int(item.get("StartLine", 0) or 0),
                "rule": item.get("RuleID", ""),
                "description": item.get("Description", ""),
                "snippet": match,
            }
        )
    return out
```

- [ ] **Step 2: Run the tests and confirm they pass**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestParseFindings`
Expected: 5 passed.

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py`
Expected: 9 passed.

- [ ] **Step 4: Commit**

```bash
git add plugins/public-ready/skills/public-ready/scan.py
git commit -m "Implement parse_findings in public-ready scan.py"
```

---

## Task 6: Write failing tests for `format_report_section()`

This formats a list of finding dicts into a markdown bullet list, suitable for the "Secrets" section of the final report.

**Files:**
- Modify: `plugins/public-ready/test_public_ready.py`

- [ ] **Step 1: Append the test class**

Append to `plugins/public-ready/test_public_ready.py`:

```python
# ---------------------------------------------------------------------------
# format_report_section
# ---------------------------------------------------------------------------


class TestFormatReportSection:
    def test_empty_findings(self) -> None:
        out = scan.format_report_section([])
        assert "no secrets detected" in out.lower()

    def test_one_finding(self) -> None:
        out = scan.format_report_section(
            [
                {
                    "file": "src/config.py",
                    "line": 12,
                    "rule": "aws-access-key",
                    "description": "AWS Access Key",
                    "snippet": "AKIAIOSFODNN7EXAMPLE",
                }
            ]
        )
        assert "src/config.py:12" in out
        assert "aws-access-key" in out
        assert "AKIAIOSFODNN7EXAMPLE" in out

    def test_multiple_findings_each_appears(self) -> None:
        findings = [
            {
                "file": "a.py",
                "line": 1,
                "rule": "r1",
                "description": "d1",
                "snippet": "s1",
            },
            {
                "file": "b.py",
                "line": 2,
                "rule": "r2",
                "description": "d2",
                "snippet": "s2",
            },
        ]
        out = scan.format_report_section(findings)
        assert "a.py:1" in out
        assert "b.py:2" in out
        assert "r1" in out
        assert "r2" in out
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestFormatReportSection`
Expected: 3 failures with `AttributeError: module 'scan' has no attribute 'format_report_section'`.

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/test_public_ready.py
git commit -m "Add failing tests for public-ready format_report_section"
```

---

## Task 7: Implement `format_report_section()`

**Files:**
- Modify: `plugins/public-ready/skills/public-ready/scan.py`

- [ ] **Step 1: Add the function**

Add to `scan.py` after `parse_findings`:

```python
def format_report_section(findings: list[dict]) -> str:
    """Format a list of finding dicts as a markdown bullet list.

    Returns a single string ready to be embedded under a section heading.
    """
    if not findings:
        return "_No secrets detected by gitleaks._"
    lines: list[str] = []
    for f in findings:
        lines.append(
            f"- **{f['file']}:{f['line']}** — `{f['rule']}` "
            f"({f['description']}): `{f['snippet']}`"
        )
    return "\n".join(lines)
```

- [ ] **Step 2: Run the tests and confirm they pass**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestFormatReportSection`
Expected: 3 passed.

- [ ] **Step 3: Run the full suite**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py`
Expected: 12 passed.

- [ ] **Step 4: Commit**

```bash
git add plugins/public-ready/skills/public-ready/scan.py
git commit -m "Implement format_report_section in public-ready scan.py"
```

---

## Task 8: Write failing tests for the missing-gitleaks error path

When `gitleaks` is not on PATH, the script must exit non-zero with a clear install hint on stderr. We test this by running the script with a `PATH` that excludes any gitleaks binary.

**Files:**
- Modify: `plugins/public-ready/test_public_ready.py`

- [ ] **Step 1: Append the test class**

Append to `plugins/public-ready/test_public_ready.py`:

```python
# ---------------------------------------------------------------------------
# End-to-end: missing gitleaks
# ---------------------------------------------------------------------------


def _run_script(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


class TestMissingGitleaks:
    def test_exits_nonzero_with_install_hint(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "f.txt").write_text("hello")
        _git(tmp_path, "add", "f.txt")
        _git(tmp_path, "commit", "-q", "-m", "init")

        # PATH that contains git but not gitleaks. We point PATH at a directory
        # holding only a symlink to git.
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        os.symlink(shutil.which("git"), bin_dir / "git")

        env = {**os.environ, "PATH": str(bin_dir)}
        r = _run_script([], cwd=tmp_path, env=env)

        assert r.returncode != 0
        assert "gitleaks" in r.stderr.lower()
        # Install hint should mention at least one install method.
        assert "brew" in r.stderr.lower() or "install" in r.stderr.lower()
```

Add `import shutil` to the top of `test_public_ready.py` (alongside the existing `import os`):

```python
import shutil
```

(`os` is already imported in Task 2's test file.)

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestMissingGitleaks`
Expected: 1 failure (script does not yet have a `main()` that performs the gitleaks check).

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/test_public_ready.py
git commit -m "Add failing test for public-ready missing-gitleaks error path"
```

---

## Task 9: Implement `main()` and the gitleaks invocation

This task wires everything together. `main()`:

1. Verifies `gitleaks` is on PATH; on failure prints an install hint and exits 1.
2. Computes the publish set.
3. Invokes `gitleaks detect --no-git --source <repo> --report-format json --report-path <tmp>`. Treats exit codes 0 (clean) and 1 (findings) as success; any other code is an error.
4. Reads the report, runs `parse_findings`, filters to publish-set files, formats as markdown, prints to stdout.
5. Exits 0.

**Files:**
- Modify: `plugins/public-ready/skills/public-ready/scan.py`

- [ ] **Step 1: Replace the file with the full implementation**

Replace the contents of `plugins/public-ready/skills/public-ready/scan.py` with:

```python
#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


INSTALL_HINT = (
    "ERROR: 'gitleaks' is required but was not found on PATH.\n"
    "Install it with one of:\n"
    "  brew install gitleaks                 # macOS / Linuxbrew\n"
    "  apt-get install gitleaks              # Debian/Ubuntu (where packaged)\n"
    "  https://github.com/gitleaks/gitleaks/releases  # binary releases\n"
)


def publish_set(repo: Path) -> list[str]:
    """Return the list of repo-relative paths that would become public on the
    next `git push`: files tracked at HEAD plus staged additions not yet
    committed. Order is deterministic (sorted), entries are unique.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    tracked_paths = [p for p in tracked.split(b"\x00") if p]

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    staged_paths = [p for p in staged.split(b"\x00") if p]

    seen: set[bytes] = set()
    out: list[str] = []
    for p in tracked_paths + staged_paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p.decode("utf-8", errors="replace"))
    return sorted(out)


def parse_findings(report_json: str) -> list[dict]:
    text = report_json.strip()
    if not text or text == "null":
        return []
    raw = json.loads(text)
    if raw is None:
        return []
    out: list[dict] = []
    for item in raw:
        match = item.get("Match", "") or item.get("Secret", "")
        out.append(
            {
                "file": item.get("File", ""),
                "line": int(item.get("StartLine", 0) or 0),
                "rule": item.get("RuleID", ""),
                "description": item.get("Description", ""),
                "snippet": match,
            }
        )
    return out


def format_report_section(findings: list[dict]) -> str:
    if not findings:
        return "_No secrets detected by gitleaks._"
    lines: list[str] = []
    for f in findings:
        lines.append(
            f"- **{f['file']}:{f['line']}** — `{f['rule']}` "
            f"({f['description']}): `{f['snippet']}`"
        )
    return "\n".join(lines)


def run_gitleaks(repo: Path, report_path: Path) -> None:
    """Run gitleaks against the working directory. Treats exit codes 0 (clean)
    and 1 (findings) as success; raises on anything else.
    """
    proc = subprocess.run(
        [
            "gitleaks",
            "detect",
            "--no-git",
            "--source",
            str(repo),
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--exit-code",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"gitleaks exited with {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def filter_to_publish_set(findings: list[dict], publish: list[str]) -> list[dict]:
    publish_set_norm = set(publish)
    return [f for f in findings if f["file"] in publish_set_norm]


def main() -> int:
    if shutil.which("gitleaks") is None:
        print(INSTALL_HINT, file=sys.stderr)
        return 1

    repo = Path.cwd()
    publish = publish_set(repo)

    with tempfile.TemporaryDirectory() as td:
        report_path = Path(td) / "gitleaks.json"
        try:
            run_gitleaks(repo, report_path)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        report_text = report_path.read_text() if report_path.exists() else ""

    all_findings = parse_findings(report_text)
    findings = filter_to_publish_set(all_findings, publish)

    print("## Secrets")
    print()
    print(format_report_section(findings))
    print()
    print(f"_Scanned {len(publish)} file(s) in the publish set._")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the missing-gitleaks test**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py -k TestMissingGitleaks`
Expected: 1 passed.

- [ ] **Step 3: Run the full suite**

Run: `cd plugins/public-ready && uv run --script test_public_ready.py`
Expected: 13 passed.

- [ ] **Step 4: Commit**

```bash
git add plugins/public-ready/skills/public-ready/scan.py
git commit -m "Implement public-ready scan.py main and gitleaks invocation"
```

---

## Task 10: Add Makefile

**Files:**
- Create: `plugins/public-ready/Makefile`

- [ ] **Step 1: Create the Makefile**

Create `plugins/public-ready/Makefile`:

```makefile
.PHONY: test

test:
	uv run --script test_public_ready.py
```

(Note: the recipe line is indented with a literal TAB, not spaces. Make requires this.)

- [ ] **Step 2: Run via Make to confirm it works**

Run: `cd plugins/public-ready && make test`
Expected: 13 passed.

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/Makefile
git commit -m "Add public-ready Makefile"
```

---

## Task 11: Write SKILL.md

The skill is what activates on natural-language triggers. It tells Claude to invoke `scan.py` for the secrets pass, then read the same files for the internal-info pass, then emit the combined report.

**Files:**
- Create: `plugins/public-ready/skills/public-ready/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `plugins/public-ready/skills/public-ready/SKILL.md`:

````markdown
---
name: public-ready
description: Pre-publication scan for the current Git repo. Use when the user asks "is this safe to make public", "scan for secrets before publishing", "check for leaks", "what shouldn't be in this repo if it goes public", or otherwise wants a leak/internal-info check before opening a repo to the public.
---

# public-ready — pre-publication scan

Use this skill when the user wants to check whether the current repository is safe to make public (or to push to a public remote). It scans the **publish set** — files tracked at HEAD plus staged additions — which is what would become visible on the next `git push`.

## How to run the scan

1. **Run `scan.py` for the secrets pass.**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/skills/public-ready/scan.py
   ```

   This uses `gitleaks` under the hood and prints a markdown `## Secrets` section to stdout. If `gitleaks` is missing the script prints an install hint and exits non-zero — relay that to the user and stop.

2. **Read the publish-set files for the internal-info pass.**

   Get the list of files to inspect by running:

   ```bash
   git ls-files
   git diff --cached --name-only --diff-filter=A
   ```

   Read the union of those files (skip binaries, lockfiles, and anything obviously generated). Look for organization-specific or personal information that probably shouldn't be public:

   - **Internal hostnames / URLs** — anything pointing at infrastructure that isn't a public website (e.g., `*.internal`, `*.corp`, `*.local`, internal subdomains of an organization, `intranet.*`).
   - **RFC1918 / link-local IPs** — `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, `169.254.x.x`. (Don't flag `127.0.0.1` or `0.0.0.0`.)
   - **Real-looking email addresses** on non-generic domains (i.e., not `@example.com`, `@gmail.com`, etc.). Especially employee-shaped addresses on company domains.
   - **Personal names** that look like real employees (firstname.lastname, "Reviewed by …", changelog entries with full names, commit-author-shaped strings inside files).
   - **Internal project codenames** — strings that look like internal project names not used externally. Use repo context (README, package metadata) to judge whether a name is public or internal.
   - **Private network identifiers** — internal Slack workspace IDs, internal Jira project keys mentioned in code, internal ticket links.

   Be conservative. Prefer false negatives over false positives. Skip:

   - Placeholder names: `John Doe`, `Jane Smith`, `Foo Bar`, `Alice`, `Bob`.
   - Documentation IPs: `192.0.2.x`, `198.51.100.x`, `203.0.113.x` (RFC 5737 reserved-for-docs ranges).
   - Generic example emails: `*@example.com`, `*@test.com`.
   - The user's own commit-author email/name as visible in `git log` — that's already public on the repo's commits.
   - Strings inside vendored / generated / lockfile content.

3. **Emit the combined report.**

   Reply to the user with a single markdown report in this exact shape:

   ```markdown
   # public-ready report

   ## Secrets
   <output of scan.py's "## Secrets" section, verbatim>

   ## Possibly internal info
   - <file>:<line> — <short reason why this looks internal/personal>
   - ...
   _(or "_No internal/personal info detected._" if nothing found)_

   ## Verdict
   <one of:>
   - "Looks safe to publish."
   - "Found N issue(s) — review before publishing."
   ```

   The verdict count is the total number of items across both sections. The user's next action is on them — do not modify any files.
````

- [ ] **Step 2: Verify the file exists and has the frontmatter**

Run: `head -5 plugins/public-ready/skills/public-ready/SKILL.md`
Expected: shows `---`, `name: public-ready`, `description: ...`, `---`.

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/skills/public-ready/SKILL.md
git commit -m "Add public-ready SKILL.md"
```

---

## Task 12: Write the slash command

**Files:**
- Create: `plugins/public-ready/commands/public-ready.md`

- [ ] **Step 1: Create the command file**

Create `plugins/public-ready/commands/public-ready.md`:

```markdown
---
description: Scan the current repo for secrets and internal/personal info that shouldn't be public.
allowed-tools: ["Bash", "Read", "Skill"]
---

Run the `public-ready` skill to scan the current Git repository for content that shouldn't be in a public repo.

Invoke the skill, then return its combined markdown report (Secrets / Possibly internal info / Verdict) to the user. Do not modify any files.
```

- [ ] **Step 2: Verify the file**

Run: `head -5 plugins/public-ready/commands/public-ready.md`
Expected: shows the frontmatter.

- [ ] **Step 3: Commit**

```bash
git add plugins/public-ready/commands/public-ready.md
git commit -m "Add /public-ready slash command"
```

---

## Task 13: Write the plugin README

**Files:**
- Create: `plugins/public-ready/README.md`

- [ ] **Step 1: Create the README**

Create `plugins/public-ready/README.md`:

````markdown
# public-ready

Pre-publication scan for the current Git repository. Flags **secrets** (via [`gitleaks`](https://github.com/gitleaks/gitleaks)) and **personal / internal info** (via a Claude-driven layer) in the content that would become public on the next `git push`.

## Install

```
/plugin marketplace add yngvark/claude-plugins
/plugin install public-ready@yngvark
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (the script uses `uv run --script`)
- [`gitleaks`](https://github.com/gitleaks/gitleaks) on `PATH` — `brew install gitleaks`, `apt-get install gitleaks`, or download a binary release.

If `gitleaks` is missing the scan exits with an install hint.

## Usage

Either:

```
/public-ready
```

…or just ask Claude in plain language: "is this repo safe to make public?", "scan for leaks before publishing", "check for secrets and internal info".

The scan covers the **publish set**: files tracked at HEAD ∪ staged additions. It does not scan untracked files, gitignored files, or git history.

## Output

A single markdown report in the conversation:

- `## Secrets` — gitleaks findings (file:line, rule id, snippet).
- `## Possibly internal info` — Claude's findings with a one-line reason each (internal hostnames, RFC1918 IPs, real-looking emails or names, internal codenames, etc.).
- `## Verdict` — `Looks safe to publish.` or `Found N issue(s) — review before publishing.`

Nothing is written to disk. The user decides what to do with the findings.

## Project structure

```
.claude-plugin/
  plugin.json
commands/
  public-ready.md         /public-ready slash command
skills/public-ready/
  SKILL.md                skill metadata + scan instructions
  scan.py                 gitleaks wrapper (uv shebang)
test_public_ready.py      pytest suite
Makefile                  dev commands
```

## Running tests

```bash
make test
```

This runs `uv run --script test_public_ready.py`, which installs pytest into an isolated environment and executes all unit and integration tests. The suite stubs out the missing-gitleaks path with a controlled `PATH`; you do not need `gitleaks` installed to run tests.

## Limitations

- The internal-info pass relies on Claude reading every publish-set file. For repos with thousands of files this is slow; consider running on a subdirectory by `cd`-ing into it before invoking.
- The scan does not look at git history. If a secret was committed in the past it will only be flagged if it's still in the current HEAD or staged.
- The Claude-driven layer is conservative by design — it can miss organization-specific patterns it has no context for. If you have a recurring pattern (e.g., a specific internal codename), tell Claude about it before running the scan.
````

- [ ] **Step 2: Commit**

```bash
git add plugins/public-ready/README.md
git commit -m "Add public-ready plugin README"
```

---

## Task 14: Document the plugin in the root README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current root README structure**

Run: `cat README.md`
Confirm the format used for `gh-read` and `one-shot` entries (header line, short paragraph, install snippet, design notes link).

- [ ] **Step 2: Add a `public-ready` section**

Add a new section to `README.md` after the existing plugin sections, in the same style. Use this body:

```markdown
### public-ready

Pre-publication scan for the current Git repository. Flags secrets (via `gitleaks`) and personal/internal info (via a Claude-driven layer) in the content that would become public on the next `git push`. Invoked as the `/public-ready` slash command or by asking Claude in plain language ("is this safe to make public?").

```
/plugin install public-ready@yngvark
```

Design notes: [`docs/superpowers/specs/2026-05-07-public-ready-plugin-design.md`](docs/superpowers/specs/2026-05-07-public-ready-plugin-design.md).
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document public-ready plugin in root README"
```

---

## Task 15: End-to-end verification

This task confirms the assembled plugin actually works against a real repo with a known secret. It requires `gitleaks` installed locally.

**Files:**
- (none modified)

- [ ] **Step 1: Confirm `gitleaks` is installed**

Run: `gitleaks version`
Expected: prints a version like `v8.x.x`.
If missing, install it (`brew install gitleaks`, etc.) before continuing.

- [ ] **Step 2: Create a throwaway repo with a known fake secret**

Run:

```bash
cd /tmp
rm -rf public-ready-smoke
mkdir public-ready-smoke
cd public-ready-smoke
git init -q -b main
git config user.email t@e.com
git config user.name t
echo 'AKIAIOSFODNN7EXAMPLE' > leak.txt
echo 'just normal text' > clean.txt
git add leak.txt clean.txt
git commit -q -m init
```

- [ ] **Step 3: Run scan.py against it**

Run: `<repo-root>/plugins/public-ready/skills/public-ready/scan.py`
(Substitute `<repo-root>` with the absolute path to this checkout.)

Expected: stdout starts with `## Secrets`, contains a finding line referencing `leak.txt` and `aws-access-key`, followed by `_Scanned 2 file(s) in the publish set._`. Exit code 0.

- [ ] **Step 4: Run the scan with no findings**

Run:

```bash
cd /tmp/public-ready-smoke
rm leak.txt
git add -A
git commit -q -m clean
<repo-root>/plugins/public-ready/skills/public-ready/scan.py
```

Expected: stdout starts with `## Secrets`, then `_No secrets detected by gitleaks._`, then `_Scanned 1 file(s) in the publish set._`. Exit code 0.

- [ ] **Step 5: Clean up the throwaway repo**

Run: `rm -rf /tmp/public-ready-smoke`

- [ ] **Step 6: Run the full test suite one more time**

Run: `cd plugins/public-ready && make test`
Expected: 13 passed.

- [ ] **Step 7: No commit needed**

Step 15 is verification only. If anything failed, fix it in a focused commit before stopping.

---

## Self-review checklist (run after writing the plan)

(Already performed by the plan author — kept here for reference during execution.)

- **Spec coverage:**
  - Plugin layout mirrors gh-read → Tasks 1, 10, 11, 12, 13.
  - Slash command + skill invocation → Tasks 11, 12.
  - gitleaks required, fail-fast install hint → Tasks 8, 9.
  - Publish set = tracked ∪ staged additions → Tasks 2, 3.
  - Claude-driven internal-info layer with conservative-by-default guidance → Task 11 (SKILL.md body).
  - Markdown report streamed to chat, no file written → Task 9 (`main()` only prints) + Task 11 (SKILL.md final-report shape).
  - Tests for scan.py only; Claude layer not unit-tested → Tasks 2, 4, 6, 8 + plan note.
- **Type consistency:** Finding dict shape (`file`, `line`, `rule`, `description`, `snippet`) is identical across `parse_findings`, `format_report_section`, and `filter_to_publish_set`.
- **Placeholder scan:** No "TBD" / "implement later" / "add error handling" — all code blocks are concrete.
