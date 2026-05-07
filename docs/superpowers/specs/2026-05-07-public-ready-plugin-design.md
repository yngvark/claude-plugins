# `public-ready` plugin — design

## Purpose

A Claude Code plugin in the `yngvark/claude-plugins` marketplace that scans the
current Git repository for content that should not be in a public repo, before
the user makes the repo public (or pushes it to a public remote).

The scan covers two categories:

1. **Secrets** — API keys, tokens, private keys, credentials. Detected by
   wrapping [`gitleaks`](https://github.com/gitleaks/gitleaks).
2. **Personal / internal info** — internal hostnames and URLs, RFC1918 IPs,
   real-looking employee names, project codenames, real email addresses on
   non-public domains, and other organization-specific strings. Detected by a
   Claude-driven layer guided by the plugin's `SKILL.md`.

Out of scope for v1: git history scanning, repo-hygiene checks (large files,
IDE junk, `.DS_Store`), config files, persistent report files, hooks on
`git push`, autofix.

## How the user invokes it

Two paths, both of which run the same scan:

- Slash command `/public-ready` — explicit, discoverable, deliberate
  pre-publish scan.
- Skill — activates on natural-language triggers such as "is this safe to make
  public", "scan for leaks before going public", "check for secrets in this
  repo".

This matches the existing marketplace conventions: `gh-read` uses a skill,
`one-shot` uses skill plus agent. No hooks, no automation on push — invocation
is always explicit.

## What gets scanned

"Files that would become public on the next `git push`":

- Files tracked at HEAD: `git ls-files`.
- Plus staged additions not yet committed: `git diff --cached --name-only --diff-filter=A`.

Untracked files, gitignored files, and content already pushed to the remote
are out of scope. (The user is asking "if I push and make this public, what
escapes?" — that's the scope.)

## Scan flow

When `/public-ready` is run, or the skill activates:

1. **Verify `gitleaks` is installed.** The plugin's Python script checks `which gitleaks`. If missing, prints an install hint (`brew install gitleaks` / link to releases) and exits non-zero. The user must install gitleaks themselves — no auto-install, no bundling, no degraded mode. Same dependency posture as `gh-read` requiring `gh`.
2. **Run gitleaks against the publish set.** `scan.py` enumerates the publish set (tracked ∪ staged-added) and runs gitleaks on it, capturing JSON output. Findings are normalized to `{file, line, rule, severity, snippet}`.
3. **Claude reads the publish set for internal/personal info.** The skill instructs Claude to scan the same files for organization-specific strings. The skill enumerates what to look for and what to ignore (placeholder names like `John Doe`, RFC docs, generic examples). Claude is told to be conservative and to prefer false negatives over false positives.
4. **Single combined markdown report streamed to chat.** Sections:
   - `## Secrets` — gitleaks findings, ranked by severity.
   - `## Possibly internal info` — Claude's findings with brief justification per item.
   - `## Verdict` — one of `Looks safe to publish.` or `Found N issues — review before publishing.`

Nothing is written to disk.

## Components

```
plugins/public-ready/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── public-ready.md          # slash command /public-ready
├── skills/
│   └── public-ready/
│       ├── SKILL.md             # natural-language triggers + scan instructions
│       └── scan.py              # uv shebang; wraps gitleaks
├── test_public_ready.py         # integration tests for scan.py
├── Makefile                     # `make test`
└── README.md                    # user-facing install / usage notes
```

This mirrors the `gh-read` layout exactly — same plugin-root test file,
Makefile, and README.

### `plugin.json`

Standard manifest with `name: "public-ready"`, description, and the marketplace
fields used by the existing two plugins.

### `commands/public-ready.md`

Slash command body invokes the skill. Short — most logic lives in the skill.

### `skills/public-ready/SKILL.md`

The skill's frontmatter `description` field includes natural-language triggers
("scan repo for things that shouldn't be public", "check for secrets and
internal info before publishing"). The body instructs Claude to:

- Run `scan.py` to get the secrets findings.
- Read the publish-set files and scan for internal/personal info, with explicit
  guidance on what counts (and what doesn't).
- Format and emit the final combined report as described above.

### `scan.py`

`uv` shebang, single-file Python. Responsibilities:

- Verify `gitleaks` on PATH; clear install hint on failure.
- Build the publish set via `git ls-files` and `git diff --cached --name-only --diff-filter=A`.
- Invoke `gitleaks` against that set, parse JSON output.
- Print normalized findings. Exit non-zero on missing gitleaks; exit zero on a
  clean scan or on findings (findings aren't an error — they're the output).

## Testing

Integration tests for `scan.py` in `test_public_ready.py`, run via `make test`,
mirroring the `gh-read` test suite:

- Repo containing a known secret → gitleaks invoked → finding surfaced in
  output.
- Repo with no secrets → output reports nothing.
- `gitleaks` missing from PATH → script exits non-zero with install hint in
  stderr.
- Publish-set enumeration includes tracked files and staged additions, excludes
  untracked files.

The Claude-driven internal-info layer is not unit-tested — it's a prompt, not
code. Its behavior is exercised manually whenever the skill activates.

## Why this shape

- **gitleaks for secrets, Claude for internal-info.** Secret detection is a
  solved problem with a mature, well-maintained tool. Internal-info detection
  is inherently context-dependent (what counts as "internal" varies per org and
  per repo); a static ruleset would either be too generic to catch
  organization-specific codenames or require per-repo config that duplicates
  what Claude can infer from repo context.
- **Required dependency on `gitleaks`.** Matches `gh-read`'s posture toward
  `gh`. Auto-install is platform-fragile; bundling bloats the repo; degraded
  mode silently weakens the plugin's core purpose.
- **Slash command + skill, no hook.** Pre-publish scanning is a deliberate
  action, not an every-push event. A push-time hook would generate noise and
  false positives on every push to private mirrors, dev branches, etc.
- **Markdown to chat, no file written.** The user runs this once before
  publishing. A persistent artifact would be churn; inline mutations to the
  source files would risk overstepping.
- **Tracked + staged, not history.** Catches what's about to leak. History
  scanning is a separate problem (and largely unhelpful — once a secret is in
  history, the fix is rotation + history rewrite, not a scanner).
