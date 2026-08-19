# notes

A small "second brain" for a plain Markdown notes folder (e.g. an Obsidian
vault). Three skills:

- **`/note`** — jot a quick thought, idea, or reminder into the notes folder as
  a new Markdown file (one note per file). You can pass the text directly, or
  ask Claude to capture something from the conversation.
- **`/read-note`** — find and read a note you already have, by file name, by a
  topic in its body, or just "my last note". Use it to pick up work described in
  an earlier note. Read-only.
- **`/daily-notes-add-title`** — find daily notes named just by date
  (`2026-07-01.md`) and rename them to include a descriptive title based on
  their contents (`2026-07-01 Meeting with team.md`). The date prefix is always
  kept; only a title is appended.

## Install

```
/plugin marketplace add yngvark/claude-plugins
/plugin install notes@yngvark
```

## Setup

Point an environment variable at your notes / Obsidian folder so the skills
know where to read and write:

```sh
export OBSIDIAN_NOTES_DIR="$HOME/path/to/vault"
```

`NOTES_DIR` is accepted as a fallback if `OBSIDIAN_NOTES_DIR` is unset. Nothing
about your folder path is stored in this repo.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (the helper script runs via `uv run --script`)

## How it works

The semantic work — writing the note, inventing a title from a day's contents,
judging which search hit you meant — is done by Claude. A small helper script
(`scripts/notes.py`) handles the deterministic, testable parts: resolving the
notes directory, sanitizing titles into safe filenames, looking notes up by name
(`find`) or contents (`search`) or recency (`recent`), listing untitled daily
notes, and renaming files (using `git mv` when the vault is a Git repo, so
history is preserved). Renames and new files never overwrite an existing file —
a numeric suffix is added on collision. Lookups skip hidden folders such as
`.obsidian/` and `.trash/`.

## Development

```
make test
```
