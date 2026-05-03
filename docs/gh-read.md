# Design: `gh-read` plugin

## Why this exists

`gh-read.py` is a read-only proxy for `gh api`. It forces `--method GET` and enforces a path/flag allowlist so Claude Code cannot accidentally mutate GitHub state (close issues, merge PRs, change settings) when asking for "just" some data.

The script has lived as a personal skill at `~/.claude/skills/gh-read/` and is referenced by the user's global `CLAUDE.md` ("NEVER use `gh api` directly — run `~/.claude/skills/gh-read/gh-read.py`"). Packaging it as a plugin in this marketplace makes the canonical version public, installable, and version-controlled, instead of living only in one developer's home directory.

## Architecture

A second plugin in this marketplace, alongside `one-shot`. Standard Claude Code plugin layout:

```
plugins/gh-read/
├── .claude-plugin/plugin.json     manifest (name, version, description, author, keywords, license)
├── skills/gh-read/
│   ├── SKILL.md                    activation entry point — frontmatter + body
│   └── gh-read.py                  the proxy script (unchanged behavior)
├── test_gh_read.py                 pytest suite (at plugin root, not inside skills/)
├── Makefile                        `make test` runs the suite
└── README.md                       install + dev instructions
```

The skill is auto-discovered by Claude Code via the `skills/gh-read/SKILL.md` path. The python script is invoked via Bash from within that skill's body.

## Layout decisions

### Tests live at plugin root, not inside `skills/gh-read/`

The test suite (`test_gh_read.py`) and `Makefile` are dev artifacts — Claude Code never executes them at runtime; they exist so the allowlists can be edited safely. Putting them at plugin root keeps the skill payload focused on what Claude actually loads (`SKILL.md` + the script it invokes), while still keeping tests in the same plugin directory so anyone cloning the marketplace can run `make test`.

The test file's `_mod_path` line changes from `Path(__file__).parent / "gh-read.py"` to `Path(__file__).parent / "skills" / "gh-read" / "gh-read.py"`. The Makefile target stays `uv run --script test_gh_read.py`.

### No `allowed-tools` frontmatter

The source SKILL.md declared:

```yaml
allowed-tools: Bash(~/.claude/skills/gh-read/gh-read.py *), Bash(python3 ~/.claude/skills/gh-read/gh-read.py *)
```

For the plugin we drop this entirely. Reasons:

- The path-prefixed `Bash(...)` form would need to embed `${CLAUDE_PLUGIN_ROOT}`. The official plugin-structure docs confirm `${CLAUDE_PLUGIN_ROOT}` expansion in hook command paths, MCP server JSON, and skill *body* text, but are silent on whether it expands inside `allowed-tools` frontmatter values. No sibling plugin in the local cache uses this pattern, so it's not a tested path.
- The `gh-read.py` script is itself the security boundary: it forces `--method GET`, rejects any path outside the allowlist, and rejects any flag outside the allowlist. A generic Bash permission prompt does not weaken that.
- Behaviorally: first invocation per session will prompt for Bash permission (or be allowed automatically if the user already allows Bash). After that the user is undisturbed.

### Script is moved, not copied; local copy stays for now

The plugin is a parallel installation. The user's existing `~/.claude/skills/gh-read/` keeps working alongside the plugin; the user manually retires it on their own schedule (see Cleanup, below). This avoids any cutover-day breakage of the user's CLAUDE.md reference.

### Path references switch to `${CLAUDE_PLUGIN_ROOT}`

Inside the plugin SKILL.md body, every `~/.claude/skills/gh-read/gh-read.py` becomes `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py`. The python script itself is path-independent — it does not reference its own location — so no changes inside `gh-read.py`.

## Components

### `plugins/gh-read/.claude-plugin/plugin.json`

Mirror of `one-shot`'s plugin.json shape:

```json
{
  "name": "gh-read",
  "version": "0.1.0",
  "description": "Read-only GitHub API proxy. Forces GET and an endpoint allowlist so Claude Code cannot mutate GitHub state.",
  "author": { "name": "Yngvar Kristiansen" },
  "keywords": ["github", "api", "read-only", "security"],
  "license": "MIT"
}
```

### `plugins/gh-read/skills/gh-read/SKILL.md`

YAML frontmatter:

```yaml
---
name: gh-read
description: Read-only GitHub API access. Use when fetching data from GitHub — listing issues, viewing pull requests, checking CI/workflow run status, reading file contents, comparing branches, listing releases, getting commit details, or viewing git refs and comments.
---
```

Body: identical content to the source SKILL.md, with `~/.claude/skills/gh-read/gh-read.py` replaced by `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py` throughout. The opening line ("NEVER use `gh api` directly. Always use ... instead.") keeps the canonical full path so it's unambiguous.

### `plugins/gh-read/skills/gh-read/gh-read.py`

Byte-for-byte copy of the source script. No edits.

### `plugins/gh-read/test_gh_read.py`

Copy of source test file with one line changed — `_mod_path` updated to point into `skills/gh-read/`.

### `plugins/gh-read/Makefile`

Same as source.

### `plugins/gh-read/README.md`

Adapted from the source README. Install section points to the marketplace:

```
/plugin marketplace add yngvark/claude-plugins
/plugin install gh-read@yngvark
```

Dev sections (running tests, adding allowed endpoints, adding allowed flags) stay as in the source, with paths updated where needed.

## Marketplace registration

Append a second entry to `.claude-plugin/marketplace.json`:

```json
{
  "name": "gh-read",
  "source": "./plugins/gh-read",
  "description": "Read-only GitHub API proxy. Forces GET and an endpoint allowlist so Claude Code cannot mutate GitHub state.",
  "author": { "name": "Yngvar Kristiansen" }
}
```

## Root `README.md` update

Add a `### gh-read` subsection under `## Plugins`, parallel to `### one-shot`. Mention purpose in one paragraph, show the install command, link to `docs/gh-read.md`.

## Cleanup (for the user, after install)

Once the plugin is installed and verified working:

```bash
rm -rf ~/.claude/skills/gh-read
```

Then edit `~/.claude/CLAUDE.md` — replace the existing instruction:

> ❌ NEVER use `gh api` directly. You can use other `gh` commands directly, such as `gh pr` or `gh issue`, but not `gh api`. Instead, run `~/.claude/skills/gh-read/gh-read.py`. Run it directly, do not use uv run. It enforces read-only access.

Two options for the replacement:

- **Path-agnostic (recommended):** "Instead, use the `gh-read` skill — it enforces read-only access." Relies on Claude discovering the skill by name; works regardless of install location.
- **Explicit path:** Replace `~/.claude/skills/gh-read/gh-read.py` with `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py`. Note: `${CLAUDE_PLUGIN_ROOT}` is only set when a plugin is actually active in context, so this is less robust as a global instruction.

## Distribution

Same as `one-shot`:

```
/plugin marketplace add yngvark/claude-plugins
/plugin install gh-read@yngvark
```

## What is explicitly NOT in scope

- No CI to run `make test` on the marketplace repo. (Possible follow-up; not required for the plugin to be usable.)
- No edit to `gh-read.py` itself — same allowlists, same behavior.
- No automated migration off `~/.claude/skills/gh-read/`. The user's local copy and CLAUDE.md reference are left intact; cleanup is documented and manual.
