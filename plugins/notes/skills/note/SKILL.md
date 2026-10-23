---
name: note
description: Save a new note to, or find and read an existing note from, the user's Markdown/Obsidian notes folder. Use whenever the user says "/note", "note this down", "add a note", "write this to my notes/second brain", "save this for later", or otherwise asks Claude to write something down — and also when they refer to a note that already exists: "see <something>.md", "read my note about X", "what did I write about Y", "look up my notes on Z", "continue what's in that handoff note". Never write a note to any other location.
argument-hint: "[a thought to capture, or a note name/topic to look up]"
---

# note — capture or recall a note

The user's notes folder is their "second brain": a plain Markdown folder, one
note per file. This skill either **writes** a new note or **reads** an existing
one. Decide which before doing anything else.

## First: read or write?

**Read** when the text points at a note that already exists:

- a file name or title, even partial: `See Foo.md`, `2026-07-01 Standup`
- a reference back: "my note about Y", "that handoff note", "what did I write
  about Z", "my last note"
- a wish to continue earlier work: `See Foo.md — I want to continue that`

`See Foo.md — I want to continue that` means "open `Foo.md`". It never means
"save a note whose body is a pointer to `Foo.md`".

**Write** when the text is new content to keep: a thought, idea, reminder,
snippet, or a longer write-up (summary, reading list, triage note), or when the
user asks Claude to capture something from the current conversation.

Bare `/note` with no text: if Claude is capturing something from the
conversation on the user's behalf, write that. Otherwise ask, in one short
question, what to capture or look up.

When it is genuinely ambiguous, ask in one line before writing. A junk note the
user has to hunt down and delete costs more than the question.

Both paths start by resolving the notes folder:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/notes.py resolve-dir
```

This prints `$OBSIDIAN_NOTES_DIR`, or the current working directory when that
variable is unset. If it errors (the variable points at a missing path), relay
the error to the user and stop. Never read or write notes anywhere else — not a
scratch directory, not `~/Documents`, not a path you pick yourself.

## Write a new note

1. **Decide the note body and a short title.**

   - The **title** is a concise, human-readable summary of the note (a few
     words, e.g. `Idea for caching layer`). It becomes the filename.
   - The **body** is Markdown. Start with an `# <title>` heading, then the
     thought. Keep the user's wording; lightly clean up only if they clearly
     dictated rough text. Do not pad it with commentary.

2. **Get a safe, unique file path** for the title:

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py note-path "Idea for caching layer"
   ```

   This prints an absolute path inside the notes folder, prefixed with today's
   ISO date, sanitized and de-duplicated (e.g.
   `.../2026-07-01 Idea for caching layer.md`, or `... 2.md` if that name is
   taken). Pass the title without a date; the script adds it. Use the path it
   prints verbatim.

3. **Write the file** at that path with the Write tool, using the body from
   step 1.

4. **Confirm** to the user with the file name, in one line. Don't show the
   full path unless asked — the folder is personal.

Never overwrite an existing note; the path from `note-path` avoids collisions.
Add exactly one new file and touch nothing else in the folder.

## Read an existing note

1. **Locate the note.** Pick the search that matches what the user gave you:

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

2. **Handle the result count.**

   - **One hit:** read it (step 3).
   - **Several plausible hits:** read the top candidate. If it clearly isn't
     what the user meant, list the file names and ask which one.
   - **Nothing:** say so plainly and stop. Do not create a note as a
     consolation, and do not invent contents.

3. **Read the file** with the Read tool, using the path the script printed
   verbatim.

4. **Act on it.** Answer the user's question from the note, or, if the note
   describes work to continue, summarize where things stand and pick up from
   there. Follow links the note contains (`[[wiki links]]`, relative paths,
   URLs) when they're needed to make sense of it; `find` resolves a
   `[[wiki link]]` target by name.

Reading never changes the vault: do not edit, rename, move, or reorganize
notes. To rename daily notes, tell the user to run `/daily-notes-add-title`.
Quote what's needed to answer rather than dumping a whole file back, and keep
the folder path out of your reply unless asked. Hidden folders (`.obsidian/`,
`.trash/`) are skipped by design.
