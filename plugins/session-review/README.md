# session-review

Retrospect on a Claude Code session and propose changes that would have helped if they had been in place at the start.

## What it does

1. Reads the session's transcript (`~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`).
2. Inventories every `CLAUDE.md` in the repo (root + subdirs).
3. Looks for friction signals — user corrections, repeated explanations, denied tools, wrong-direction work, repeated workflows.
4. Emits a report:
   - **Proposed CLAUDE.md changes** as unified diffs (one per file).
   - **Skill candidates** for workflows the session repeated.
5. Walks the user through applying approved CLAUDE.md edits one at a time.

Only `CLAUDE.md` files are ever modified. Skill candidates are report-only.

## Usage

```
/session-review
```

A `SessionEnd` hook also prints a one-line nudge reminding you the command exists.

## Components

- `commands/session-review.md` — slash command entry point.
- `skills/session-review/SKILL.md` — the review procedure.
- `skills/session-review/find_transcript.py` — locates the active session's transcript.
- `hooks/hooks.json` + `hooks/session-end-nudge.py` — the SessionEnd nudge.

## Design notes

- The hook deliberately does **not** run analysis at SessionEnd — output during teardown is not seen interactively, and we don't want to burn tokens silently. The hook only prints a one-line reminder.
- The slash command intentionally reads the transcript file rather than relying on in-context conversation, so tool I/O and post-compaction content are still available.
