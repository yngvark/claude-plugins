---
name: session-review
description: Use when the user wants to retrospect on the current Claude Code session and improve future ones. Triggers on "review this session", "what should we add to CLAUDE.md", "did we learn anything reusable", "/session-review", or similar. Reads the session transcript, inventories CLAUDE.md files at the repo root and subdirs, proposes targeted updates as diffs, and surfaces new-skill candidates.
---

# session-review — retrospect on a completed session

The aim is not to summarise the session. The aim is to produce **durable changes** to the repo's `CLAUDE.md` files (and a list of skill candidates) that would have made the session shorter, less wrong, or less repetitive if they had been in place at the start.

Bias toward fewer, sharper findings. One well-placed `CLAUDE.md` line beats five marginal ones.

## Procedure

### 1. Locate the session transcript

Run:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/session-review/find_transcript.py
```

It prints the absolute path of the most recently modified `*.jsonl` in `~/.claude/projects/<encoded-cwd>/`, where `<encoded-cwd>` is the current working directory with every `/` replaced by `-` (including the leading slash → leading dash).

If it exits non-zero, tell the user the transcript could not be found and fall back to using the in-context conversation as the input. Continue the rest of the procedure.

### 2. Read the transcript

Use the `Read` tool on the path printed in step 1. If the file is too large to read in one call, read in chunks. Prioritise:

- User messages (especially short corrections).
- Tool results that contain errors or denials.
- The first ~50 turns (where misunderstandings usually originate) and the last ~50 turns (where the user typically clarifies).

### 3. Inventory existing CLAUDE.md files

From the repo root (`git rev-parse --show-toplevel`):

```bash
find . -name CLAUDE.md -not -path './node_modules/*' -not -path './.git/*'
```

Read each file. Also read the user's global `~/.claude/CLAUDE.md` if accessible — proposals must not duplicate or contradict it.

### 4. Analyse the session for friction signals

Look specifically for:

- **Corrections** from the user that contradict an assumption Claude made: "no, X actually works like…", "stop doing Y", "why did you think that?", "we don't use Z here".
- **Repeated explanations** — the user explained the same concept or constraint more than once across the session.
- **Tool / permission friction** — the same permission prompt repeated, a denied tool retried, a wrapper script the user had to point Claude at more than once.
- **Wrong-direction work** — code written, then reverted or substantially rewritten after a clarification.
- **Repeated workflows** — the same multi-step procedure executed two or more times in the session. These are **skill candidates**, not `CLAUDE.md` material.

Ignore:

- One-off bugs Claude fixed correctly on the first try.
- Style nits the user didn't actually flag.
- Anything already explicitly covered by an existing `CLAUDE.md` (root, subdir, or global).

### 5. Decide placement for each finding

For every candidate `CLAUDE.md` line, pick the **narrowest scope** that still prevents recurrence:

- Subdir-specific (e.g. only the frontend, only an infra dir) → that subdir's `CLAUDE.md` (create one if it doesn't exist *and* the rule is genuinely local).
- Repo-wide → root `CLAUDE.md`.
- Cross-repo / user-wide → flag in the report as "user might want to add to `~/.claude/CLAUDE.md`", but do not edit the global file from this plugin.

Anti-bloat rules:

- Don't add a line that restates default Claude behaviour.
- Don't add a line that contradicts an existing one — flag the conflict instead and ask the user which wins.
- Prefer rewriting / removing a stale existing line over piling on new ones.
- One line per rule. Match the terse tone of the existing `CLAUDE.md` files.

### 6. Emit the report

Reply to the user with exactly this structure:

```markdown
# session-review report

## Proposed CLAUDE.md changes

### <relative-path-from-repo-root> — <create | update>
**Why:** <one line citing transcript evidence — e.g. "user corrected the Git workflow twice (turns 14, 41)">
**Diff:**
```diff
<unified diff fragment for the proposed change>
```

…repeat per finding…

_(or "_No CLAUDE.md changes proposed._" if there are none)_

## Skill candidates
- **<short-name>** — <what it would do> — <transcript evidence, e.g. "scaffolded a plugin from scratch twice">

_(or "_No skill candidates._" if there are none)_

## Verdict
<one line, e.g. "3 CLAUDE.md updates proposed, 1 skill candidate.">
```

Do **not** apply any edits yet.

### 7. Apply approved CLAUDE.md edits interactively

For each proposed change in the report, use `AskUserQuestion` with three options: **Apply**, **Skip**, **Edit first**. On Apply, use `Edit` (or `Write` for new files). On "Edit first", show the diff inline and ask for the user's revised version, then apply. Process changes one at a time so the user always sees what is about to land.

Skill candidates are report-only — do not scaffold skills here. If the user wants one built, point them at the `plugin-dev:create-plugin` workflow.

### 8. Do not modify files outside `CLAUDE.md`

This skill's only write authority is over `CLAUDE.md` files (existing or newly created). Anything else — settings, code, memory — is out of scope.
