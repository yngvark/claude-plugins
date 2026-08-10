# yngvark/claude-plugins

A Claude Code plugin marketplace.

## Install

In Claude Code:

```
/plugin marketplace add yngvark/claude-plugins
/plugin install one-shot@yngvark
```

## Plugins

### one-shot

Activate one-shot mode: a decider subagent answers clarifying questions on your behalf so you are not interrupted during design or implementation.

The user supplies high-level intent once; all subsequent decisions are made by a `one-shot-decider` subagent, logged to a per-session file under `<project>/one-shot-log/`, and the user is only re-interrupted for plan-mode plan approval.

After installing, activate by saying "activate one-shot mode" (or similar) in any session. On first use, default preferences are bootstrapped to `~/.claude/one-shot/preferences.md` — edit that file to tune how decisions are made on your behalf.

Design notes: [`docs/one-shot.md`](docs/one-shot.md).

### gh-read

Read-only proxy for `gh api`. Forces `--method GET` and enforces a path/flag allowlist so Claude Code cannot accidentally mutate GitHub state when fetching issues, PRs, workflow runs, or other read-only data.

After installing, the `gh-read` skill activates whenever Claude needs to query the GitHub API.

```
/plugin install gh-read@yngvark
```

Design notes: [`docs/gh-read.md`](docs/gh-read.md).

### public-ready

Pre-publication scan for the current Git repository. Flags secrets (via `gitleaks`) and personal/internal info (via a Claude-driven layer) in the content that would become public on the next `git push`. Invoked as the `/public-ready` slash command or by asking Claude in plain language ("is this safe to make public?").

```
/plugin install public-ready@yngvark
```

Design notes: [`docs/superpowers/specs/2026-05-07-public-ready-plugin-design.md`](docs/superpowers/specs/2026-05-07-public-ready-plugin-design.md).

### notes

A "second brain" for a plain Markdown notes folder (e.g. an Obsidian vault). `/note` jots a quick thought into the folder as a new file; `/daily-notes-add-title` renames bare `yyyy-mm-dd.md` daily notes to include a descriptive title based on their contents. Point `$OBSIDIAN_NOTES_DIR` at your folder.

```
/plugin install notes@yngvark
```

Design notes: [`docs/notes.md`](docs/notes.md).

### playwright-cli

Browser automation through the `playwright-cli` binary — navigate pages, fill forms, click, snapshot, screenshot, mock requests, record traces and video. Install this to make a global "verify UI changes with the playwright-cli skill" rule work in every repo, rather than only the ones carrying a local copy of the skill.

```
/plugin install playwright-cli@yngvark
```

Design notes: [`docs/playwright-cli.md`](docs/playwright-cli.md).

## License

MIT — see [`LICENSE`](LICENSE).
