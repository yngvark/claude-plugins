---
name: note
description: Jot a quick thought, idea, or reminder into the user's Markdown/Obsidian notes folder as a new file. Use when the user says "/note", "note this down", "add a note", "write this to my notes/second brain", or asks Claude to capture a thought for later.
---

# note — capture a thought to the notes folder

Use this skill to save a quick thought, idea, snippet, or reminder as a **new
Markdown file** in the user's notes folder (their "second brain"). One note =
one file.

The note content is whatever the user gives you. If they invoked `/note` with
text after it, that text is the note. If they invoked it bare, ask what they
want to capture (one short question), or — if Claude is capturing something
from the current conversation on the user's behalf — use that.

## First: is this really a new note?

If the text points at a note that already exists — a file name, "see X.md", "my
note about Y", "that handoff note" — the user wants that note **read**, not a
new file containing a pointer to it. Switch to the `read-note` skill instead.
`See Foo.md — I want to continue that` is a request to open `Foo.md`.

When it's genuinely ambiguous, ask in one line before writing anything. Writing
is cheap; a junk note the user has to hunt down and delete is not.

## Steps

1. **Resolve the notes folder.**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py resolve-dir
   ```

   If this errors (the env var is unset or the path is missing), relay the
   error to the user and stop — they need to set `$OBSIDIAN_NOTES_DIR`.

2. **Decide the note body and a short title.**

   - The **title** is a concise, human-readable summary of the note (a few
     words, e.g. `Idea for caching layer`). It becomes the filename.
   - The **body** is Markdown. Start with an `# <title>` heading, then the
     thought. Keep the user's wording; lightly clean up only if they clearly
     dictated rough text. Do not pad it with commentary.

3. **Get a safe, unique file path** for the title:

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py note-path "Idea for caching layer"
   ```

   This prints an absolute path inside the notes folder, sanitized and
   de-duplicated (e.g. `.../Idea for caching layer.md`, or `... 2.md` if that
   name is taken). Use the path it prints verbatim.

4. **Write the file** at that path with the Write tool, using the body from
   step 2.

5. **Confirm** to the user with the file name (and folder), in one line. Don't
   dump the full path unless asked — the folder is personal.

## Notes

- Never overwrite an existing note; always use the path from `note-path`, which
  avoids collisions.
- Do not reorganize, retitle, or touch other files in the folder — this skill
  only adds one new note per invocation.
- To read an existing note instead, use `read-note`.
