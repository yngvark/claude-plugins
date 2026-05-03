# gh-read plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing personal `gh-read` skill (`~/.claude/skills/gh-read/`) as a plugin in this marketplace, alongside `one-shot`.

**Architecture:** New plugin at `plugins/gh-read/` containing a single skill (`skills/gh-read/`) plus dev artifacts (tests, Makefile, README) at plugin root. The python script is unchanged; only path references switch from `~/.claude/skills/gh-read/...` to `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/...`. The `allowed-tools` frontmatter is dropped (the script itself is the security boundary). The user's local `~/.claude/skills/gh-read/` and global `CLAUDE.md` reference are left untouched — manual cleanup is documented in `docs/gh-read.md`.

**Tech Stack:** Python 3.10+, `uv` for script execution, `pytest` for tests, Claude Code plugin manifest format. Spec: [`docs/gh-read.md`](../../gh-read.md).

---

## File Map

Files to create:

```
plugins/gh-read/
├── .claude-plugin/plugin.json     plugin manifest
├── skills/gh-read/
│   ├── SKILL.md                    skill activation
│   └── gh-read.py                  proxy script (byte-for-byte from source)
├── test_gh_read.py                 pytest suite (one line changed vs. source)
├── Makefile                        `make test` target (byte-for-byte from source)
└── README.md                       install + dev docs
```

Files to modify:

- `.claude-plugin/marketplace.json` — append `gh-read` entry
- `README.md` (repo root) — add `### gh-read` section under `## Plugins`

---

### Task 1: Plugin scaffolding + manifest

**Files:**
- Create: `plugins/gh-read/.claude-plugin/plugin.json`

- [ ] **Step 1: Create the plugin manifest**

Create `plugins/gh-read/.claude-plugin/plugin.json` with this exact content:

```json
{
  "name": "gh-read",
  "version": "0.1.0",
  "description": "Read-only GitHub API proxy. Forces GET and an endpoint allowlist so Claude Code cannot mutate GitHub state.",
  "author": {
    "name": "Yngvar Kristiansen"
  },
  "keywords": ["github", "api", "read-only", "security"],
  "license": "MIT"
}
```

- [ ] **Step 2: Verify JSON parses**

Run: `python3 -c "import json; json.load(open('plugins/gh-read/.claude-plugin/plugin.json'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/gh-read/.claude-plugin/plugin.json
git commit -m "Scaffold gh-read plugin manifest"
```

---

### Task 2: Skill — gh-read.py (byte-for-byte from source)

**Files:**
- Create: `plugins/gh-read/skills/gh-read/gh-read.py`

- [ ] **Step 1: Copy the source script**

Run:
```bash
cp ~/.claude/skills/gh-read/gh-read.py plugins/gh-read/skills/gh-read/gh-read.py
chmod +x plugins/gh-read/skills/gh-read/gh-read.py
```

- [ ] **Step 2: Verify byte-identical copy**

Run: `diff ~/.claude/skills/gh-read/gh-read.py plugins/gh-read/skills/gh-read/gh-read.py && echo OK`
Expected: `OK` (no diff output)

- [ ] **Step 3: Smoke-test the script**

Run: `plugins/gh-read/skills/gh-read/gh-read.py --help | head -3`
Expected: First line starts with `Usage: gh-read.py <api-path>`.

- [ ] **Step 4: Commit**

```bash
git add plugins/gh-read/skills/gh-read/gh-read.py
git commit -m "Copy gh-read.py into plugin skill folder"
```

---

### Task 3: Skill — SKILL.md (path references switched, allowed-tools dropped)

**Files:**
- Create: `plugins/gh-read/skills/gh-read/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Create `plugins/gh-read/skills/gh-read/SKILL.md` with this exact content:

````markdown
---
name: gh-read
description: Read-only GitHub API access. Use when fetching data from GitHub — listing issues, viewing pull requests, checking CI/workflow run status, reading file contents, comparing branches, listing releases, getting commit details, or viewing git refs and comments.
---

# gh-read — Read-only GitHub API

**NEVER use `gh api` directly.** Always use `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py` instead. It enforces GET-only access and an endpoint allowlist.

## Usage

```bash
# Print usage / allowed paths / allowed flags
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py --help

# List issues
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues

# Get a specific PR
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls/42

# List workflow runs
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/actions/runs

# Get commit details
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/commits/SHA

# View git refs
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/git/refs

# List comments
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/comments

# Filter with jq
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls --jq '.[].title'

# Paginate results
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues --paginate

# Read file contents
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/contents/path/to/file

# Compare branches
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/compare/main...feature

# List releases
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/releases

# Query parameters via path
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues?state=open

# Use --preview for API previews
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls --preview mercy

# Search across GitHub (issues, repos, code, commits, users, labels, topics)
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py 'search/issues?q=repo:OWNER/REPO+is:open+freeze'
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py 'search/repositories?q=language:rust+stars:>1000'
```

## Allowed paths

- `repos/{owner}/{repo}/` followed by: `issues`, `pulls`, `commits`, `git/refs`, `actions/runs`, `actions/workflows`, `contents`, `compare`, `releases`, `comments` (plus any sub-paths).
- `search/{type}` where `{type}` is one of: `issues`, `repositories`, `code`, `commits`, `users`, `labels`, `topics`.

## What's blocked

- Any write flags: `-X`, `--method`, `-f`, `--field`, `--raw-field`, `-F`, `--input`
- Any API path not in the allowlist above (e.g., `/user`, `/repos/o/r/actions/secrets`)
````

- [ ] **Step 2: Verify no remaining `~/.claude/skills/gh-read/` references**

Run: `grep -n '~/.claude/skills/gh-read' plugins/gh-read/skills/gh-read/SKILL.md && echo FAIL || echo OK`
Expected: `OK`

- [ ] **Step 3: Verify CLAUDE_PLUGIN_ROOT references are present**

Run: `grep -c 'CLAUDE_PLUGIN_ROOT' plugins/gh-read/skills/gh-read/SKILL.md`
Expected: a number ≥ 18 (one per usage example + one in lead paragraph).

- [ ] **Step 4: Verify no `allowed-tools` frontmatter**

Run: `grep -n 'allowed-tools' plugins/gh-read/skills/gh-read/SKILL.md && echo FAIL || echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add plugins/gh-read/skills/gh-read/SKILL.md
git commit -m "Add gh-read SKILL.md with CLAUDE_PLUGIN_ROOT paths"
```

---

### Task 4: Tests + Makefile at plugin root

**Files:**
- Create: `plugins/gh-read/test_gh_read.py`
- Create: `plugins/gh-read/Makefile`

- [ ] **Step 1: Copy the test file**

Run: `cp ~/.claude/skills/gh-read/test_gh_read.py plugins/gh-read/test_gh_read.py`

- [ ] **Step 2: Update `_mod_path` to point into `skills/gh-read/`**

Edit `plugins/gh-read/test_gh_read.py`. Replace the line:

```python
_mod_path = str(Path(__file__).parent / "gh-read.py")
```

with:

```python
_mod_path = str(Path(__file__).parent / "skills" / "gh-read" / "gh-read.py")
```

- [ ] **Step 3: Verify the change**

Run: `grep -n '_mod_path' plugins/gh-read/test_gh_read.py`
Expected: one line containing `"skills" / "gh-read" / "gh-read.py"`.

- [ ] **Step 4: Copy the Makefile**

Run: `cp ~/.claude/skills/gh-read/Makefile plugins/gh-read/Makefile`

- [ ] **Step 5: Verify Makefile is byte-identical**

Run: `diff ~/.claude/skills/gh-read/Makefile plugins/gh-read/Makefile && echo OK`
Expected: `OK`

- [ ] **Step 6: Run the test suite**

Run: `cd plugins/gh-read && make test`
Expected: pytest output ending in a summary line like `XX passed in YYs` and exit code 0.

- [ ] **Step 7: Commit**

```bash
git add plugins/gh-read/test_gh_read.py plugins/gh-read/Makefile
git commit -m "Add gh-read test suite and Makefile at plugin root"
```

---

### Task 5: Plugin README

**Files:**
- Create: `plugins/gh-read/README.md`

- [ ] **Step 1: Write the plugin README**

Create `plugins/gh-read/README.md` with this exact content:

````markdown
# gh-read

Read-only proxy for `gh api`. Enforces GET-only access and an endpoint allowlist so Claude Code cannot accidentally mutate GitHub state.

## Install

```
/plugin marketplace add yngvark/claude-plugins
/plugin install gh-read@yngvark
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (the script uses `uv run --script`)
- `gh` CLI, authenticated (`gh auth status`)

## Project structure

```
skills/gh-read/
  SKILL.md          Claude Code skill definition
  gh-read.py        the proxy script
test_gh_read.py     pytest suite — unit + end-to-end tests
Makefile            dev commands
```

## Running tests

```bash
make test
```

This runs `uv run --script test_gh_read.py`, which installs pytest into an isolated environment and executes all tests.

## How the security model works

Two allowlists gate every invocation:

1. **Path allowlist** — only `repos/{owner}/{repo}/{resource}` paths and `search/{type}` paths are permitted, where each segment is one of a fixed set. Checked via string splitting, no regex; query strings and fragments are stripped before validation.

2. **Flag allowlist** — only known-safe flags (`--jq`, `--paginate`, `--header`, `--cache`, `--template`, `--preview` and their short forms) pass through. Everything else is rejected. This protects against unknown or future `gh api` flags that could trigger writes.

Additionally, `--method GET` is always passed explicitly as defense-in-depth.

## Adding a new allowed endpoint

1. Edit `skills/gh-read/gh-read.py`:
   - For `repos/{owner}/{repo}/{name}` paths: add the resource name to `ALLOWED_RESOURCES`.
   - For `repos/{owner}/{repo}/{group}/{sub}` paths: add the tuple to `ALLOWED_NESTED_RESOURCES`.
   - For `search/{type}` paths: add the type to `ALLOWED_SEARCH_TYPES`.
2. Add tests in `test_gh_read.py` — both an acceptance and a related rejection case.
3. Run `make test`.

## Adding a new allowed flag

1. Add the flag to `SAFE_FLAGS_NO_ARG` (if it takes no value) or `SAFE_FLAGS_WITH_ARG` (if it does) in `skills/gh-read/gh-read.py`.
2. Add tests in `test_gh_read.py` covering the bare flag, `--flag=value`, and short-flag concatenation forms as applicable.
3. Run `make test`.
````

- [ ] **Step 2: Verify no stale paths**

Run: `grep -n '~/.claude/skills/gh-read' plugins/gh-read/README.md && echo FAIL || echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/gh-read/README.md
git commit -m "Add gh-read plugin README"
```

---

### Task 6: Register plugin in marketplace

**Files:**
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Read current marketplace.json**

Run: `cat .claude-plugin/marketplace.json`
Expected: shows the existing single-plugin (`one-shot`) array.

- [ ] **Step 2: Append the `gh-read` entry**

Replace the entire `plugins` array so the file ends up exactly like this:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "yngvark",
  "description": "Yngvar's Claude Code plugins",
  "owner": {
    "name": "Yngvar Kristiansen"
  },
  "metadata": {
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "one-shot",
      "source": "./plugins/one-shot",
      "description": "Activate one-shot mode: a decider subagent answers clarifying questions on your behalf so you are not interrupted during design or implementation.",
      "author": {
        "name": "Yngvar Kristiansen"
      }
    },
    {
      "name": "gh-read",
      "source": "./plugins/gh-read",
      "description": "Read-only GitHub API proxy. Forces GET and an endpoint allowlist so Claude Code cannot mutate GitHub state.",
      "author": {
        "name": "Yngvar Kristiansen"
      }
    }
  ]
}
```

- [ ] **Step 3: Verify JSON parses and contains both plugins**

Run:
```bash
python3 -c "import json; m=json.load(open('.claude-plugin/marketplace.json')); names=[p['name'] for p in m['plugins']]; assert names==['one-shot','gh-read'], names; print('OK', names)"
```
Expected: `OK ['one-shot', 'gh-read']`

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "Register gh-read plugin in marketplace"
```

---

### Task 7: Update root README

**Files:**
- Modify: `README.md` (at repo root)

- [ ] **Step 1: Read current README**

Run: `cat README.md`
Expected: shows the `### one-shot` section under `## Plugins`.

- [ ] **Step 2: Add the `### gh-read` subsection**

Edit `README.md`. After the `### one-shot` section (after the line `Design notes: [\`docs/one-shot.md\`](docs/one-shot.md).`) and **before** `## License`, insert this block (note: the outer fence is four backticks so the inner triple-backtick code fence renders correctly):

````markdown

### gh-read

Read-only proxy for `gh api`. Forces `--method GET` and enforces a path/flag allowlist so Claude Code cannot accidentally mutate GitHub state when fetching issues, PRs, workflow runs, or other read-only data.

After installing, the `gh-read` skill activates whenever Claude needs to query the GitHub API.

```
/plugin install gh-read@yngvark
```

Design notes: [`docs/gh-read.md`](docs/gh-read.md).
````

- [ ] **Step 3: Verify both plugins are listed**

Run: `grep -E '^### ' README.md`
Expected: two lines — `### one-shot` and `### gh-read`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Document gh-read plugin in root README"
```

---

### Task 8: Final verification

- [ ] **Step 1: Confirm full file layout**

Run: `find plugins/gh-read -type f | sort`
Expected (exactly six lines):
```
plugins/gh-read/.claude-plugin/plugin.json
plugins/gh-read/Makefile
plugins/gh-read/README.md
plugins/gh-read/skills/gh-read/SKILL.md
plugins/gh-read/skills/gh-read/gh-read.py
plugins/gh-read/test_gh_read.py
```

- [ ] **Step 2: Re-run the test suite**

Run: `cd plugins/gh-read && make test`
Expected: all tests pass, exit code 0.

- [ ] **Step 3: Confirm no path leaks**

Run: `grep -rn '~/.claude/skills/gh-read' plugins/gh-read/ && echo FAIL || echo OK`
Expected: `OK`

- [ ] **Step 4: Confirm git working tree is clean**

Run: `git status --porcelain`
Expected: empty output (everything committed).

- [ ] **Step 5: Show commit history for the feature**

Run: `git log --oneline cb3e164..HEAD`
Expected: lists the design-doc commit plus the seven implementation commits in order.
