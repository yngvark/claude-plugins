# notes plugin — design

## Why

The user keeps a plain Markdown notes folder (an Obsidian vault, though nothing
here depends on Obsidian) as a "second brain". Three recurring needs:

1. **Capture** — quickly drop a thought, idea, or reminder somewhere durable,
   either typed by the user or written by Claude on the user's behalf.
2. **Recall** — reopen a note written earlier and act on it, typically to resume
   work a note describes ("see that handoff note, I want to continue"). The user
   remembers roughly what the note is called or what it's about, not where it
   sits in the vault.
3. **Title daily notes** — the user often creates daily notes named only by date
   (`2026-07-01.md`, frequently via Obsidian). Bare dates are hard to scan
   later; a short title summarizing the day's contents makes them findable.

The plugin ships three skills — `/note`, `/read-note`, and
`/daily-notes-add-title` — that cover these.

## Key decisions

- **Notes folder via env var.** This is a public repo, so no personal absolute
  path can be committed. The folder is resolved from `$OBSIDIAN_NOTES_DIR`
  (falling back to `$NOTES_DIR`). Chosen over a gitignored config file or
  asking each time because it's set-once and leaks nothing.
- **One file per note.** `/note` writes each thought to its own Markdown file
  rather than appending to a running inbox or the daily note. Keeps notes
  atomic and independently linkable.
- **Title format `yyyy-mm-dd <Title>.md`** with a normal space after the date
  and human-readable spacing in the title (e.g. `2026-07-01 Meeting with
  team.md`). The date prefix is always preserved; only a title is appended.
- **Capture and recall are separate skills.** `/note` only writes; `/read-note`
  only reads. Bundling them invited a specific failure: given `See Foo.md — I
  want to continue that`, a write-only `/note` skill dutifully saved a new note
  whose entire body was a pointer to `Foo.md`, which is the opposite of what was
  wanted. Both skills now name that case explicitly and hand off to each other,
  and `/read-note` is documented as read-only so recall can never mutate the
  vault.
- **Three lookup modes, no index.** `find` matches file names, `search` matches
  file contents, `recent` sorts by mtime — all plain `rglob` over the vault, no
  cache or index to invalidate. A personal vault is small enough that a full
  walk is imperceptible, and a stale index would be worse than a slow one.
  Hidden folders (`.obsidian/`, `.trash/`) are skipped: they hold plugin state
  and deleted files, never notes.
- **Name matching is forgiving, ranking is strict.** `find` lowercases, drops a
  trailing `.md` (so a pasted filename works), and matches the query's words in
  any order, which means a half-remembered title still hits. Ranking then sorts
  the noise back out: exact stem, prefix, substring, words-in-any-order, and
  most-recently-modified first within a tier — so Claude can usually read the
  top hit rather than asking the user to choose.
- **Thin split between Claude and a helper script.** The semantic work
  (writing the note body, inventing a title from a day's contents, judging which
  hit the user meant) is Claude's. The deterministic, testable work lives in
  `scripts/notes.py`: resolving the directory, sanitizing titles into
  filesystem-safe names, ranking name and content matches, listing untitled
  daily notes (`^\d{4}-\d{2}-\d{2}\.md$`), and renaming. This keeps the fragile
  parts unit-tested and out of the LLM's hands.
- **Safe renames/writes.** Filenames are sanitized (illegal chars stripped,
  whitespace collapsed, length capped) and de-duplicated with a numeric suffix,
  so nothing is ever overwritten. Renames use `git mv` when the vault is a Git
  repo, preserving history.

## Structure

```
plugins/notes/
  .claude-plugin/plugin.json
  commands/note.md                        # thin /note entry point -> skill
  commands/read-note.md                   # thin entry point -> skill
  commands/daily-notes-add-title.md       # thin entry point -> skill
  scripts/notes.py                        # shared, tested filesystem helper
  skills/note/SKILL.md
  skills/read-note/SKILL.md
  skills/daily-notes-add-title/SKILL.md
  test_notes.py                           # pytest over notes.py (via uv)
  Makefile                                # `make test`
  README.md
```

The commands mirror the pattern used by the other plugins in this marketplace
(`public-ready`, `session-review`): a thin slash-command that invokes a skill
of the same name.

## Testing

`make test` runs `test_notes.py` via `uv run --script`. It covers title
sanitizing, unique-path collision handling, the daily-note regex, lookup
behaviour (name-match ranking, `.md`-suffix and case tolerance, words in any
order, subfolders, hidden-folder exclusion, content hits with one line per note,
recency ordering, limits) and the CLI subcommands (`resolve-dir`, `find`,
`search`, `recent`, `daily-list`, `daily-rename` including the `git mv` path,
and `note-path`). Fixtures stamp fixed mtimes so recency ordering is
deterministic.
