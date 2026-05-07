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
