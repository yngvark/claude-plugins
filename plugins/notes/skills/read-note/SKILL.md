---
name: read-note
description: Find and read existing notes in the user's Markdown/Obsidian notes folder. Use when the user refers to a note that already exists — "/read-note", "see <something>.md", "read my note about X", "what did I write about Y", "look up my notes on Z", "continue what's in that handoff note" — or when they want to pick up work described in an earlier note. Do NOT create a new note here; that is the `note` skill.
---

# read-note — find and read an existing note

Use this skill when the user points at a note that **already exists**. Read it
and act on its contents; never write a new file.

The strongest signal is the user naming a file or referring back to something
they wrote earlier ("see X.md", "that handoff note", "my note on Y"). A bare
reference like `See Foo.md` is a request to read `Foo.md`, not to record the
sentence "See Foo.md" as a new note.

## Steps

1. **Resolve the notes folder.**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py resolve-dir
   ```

   If this errors (the env var is unset or the path is missing), relay the
   error to the user and stop — they need to set `$OBSIDIAN_NOTES_DIR`.

2. **Locate the note.** Pick the search that matches what the user gave you:

   - **A file name or title** (even a partial or misremembered one):

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py find "handoff renovate"
     ```

     Matching is case-insensitive, ignores a trailing `.md`, searches
     subfolders, and also matches when the query's words appear in the name in
     any order. Best matches come first, then most recently modified.

   - **A topic that may only appear in the body:**

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py search "automerge working hours"
     ```

     Prints `path:lineno: matching line`, one hit per note, newest first.

   - **"my last note" / "what I wrote yesterday":**

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py recent --limit 10
     ```

   Add `--limit N` to any of these. Fall back from `find` to `search` when a
   name lookup comes up empty.

3. **Handle the result count.**

   - **One hit** — read it (step 4).
   - **Several plausible hits** — read the top candidate; if it clearly isn't
     what the user meant, list the file names and ask which one.
   - **Nothing** — say so plainly and stop. Do not create a note as a
     consolation, and do not invent contents.

4. **Read the file** with the Read tool, using the path the script printed
   verbatim.

5. **Act on it.** Answer the user's question from the note, or — if the note
   describes work to continue — summarize where things stand and pick up from
   there. Follow links the note contains (`[[wiki links]]`, relative paths,
   URLs) when they're needed to make sense of it; `find` resolves a
   `[[wiki link]]` target by name.

## Notes

- Read-only. Do not edit, rename, move, or reorganize notes here — the user's
  vault is theirs. Use the `note` skill to add a note, and
  `daily-notes-add-title` to rename daily notes.
- Notes are personal. Quote what's needed to answer, don't dump a whole file
  back at the user, and keep the folder path out of your reply unless asked.
- Hidden folders (`.obsidian/`, `.trash/`) are skipped by design.
