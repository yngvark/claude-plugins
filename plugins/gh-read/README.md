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
settings.json       default permission allow for gh-read.py
test_gh_read.py     pytest suite — unit + end-to-end tests
Makefile            dev commands
```

## Default permission

The plugin ships a `settings.json` that pre-allows `Bash(${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py:*)` so consumers are not prompted on every invocation. This is safe because the script itself is the security boundary — see "How the security model works" below. By installing the plugin you are trusting the script's allowlists; review `skills/gh-read/gh-read.py` before installing if that trust is not warranted.

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
