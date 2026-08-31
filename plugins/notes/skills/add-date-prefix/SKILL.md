---
name: add-date-prefix
description: Put a yyyy-mm-dd date in front of notes that don't have one, so a folder sorts chronologically. Renames "Standup.md" to "2026-07-01 Standup.md" using the file's creation date. Use when the user says "/add-date-prefix", "add dates to my notes", "these files are missing a date", or "date the undated notes in folder X".
---

# add-date-prefix — date the notes that lack a date

The user names notes `yyyy-mm-dd Title.md` so a folder sorts by date. Notes
written outside that habit end up without a date. This skill finds those and
renames them, taking the date from the file itself.

Only file names change. Never edit a note's contents in this skill.

## Steps

1. **Resolve the notes folder** (surface any error, then stop):

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py resolve-dir
   ```

   If the user named a subfolder ("the ki folder"), pass that folder to every
   command below as the trailing `dir` argument.

2. **List the undated notes and the date each would get:**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py undated-list "/path/to/folder"
   ```

   Each line is `yyyy-mm-dd<TAB>path`. `CLAUDE.md`, `AGENTS.md` and
   `README.md` are left out — they live in a notes folder without being notes.
   Add `--exclude NAME` for any other file the user wants kept as is.

   Only the folder itself is listed. Add `--recursive` to include subfolders,
   but ask first: subfolders often hold a different kind of note that the date
   convention was never meant for. If nothing is listed, say so and stop.

3. **Check the date source.** By default the date is the file's creation time.
   Two cases call for `--date-source`, on both this command and step 5:

   - `--date-source git` when the vault is a Git repository. Cloning resets
     every file's creation time to the moment of the clone, so the commit that
     added a note is the only honest record of when it was written.
   - `--date-source mtime` when the user wants the last edit instead, e.g. for
     a note they keep revising.

4. **Check for links into the notes you're about to rename:**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py link-refs "Standup" "Demo" --dir "/path/to/vault"
   ```

   Pass every note from step 2 and point `--dir` at the whole vault, not just
   the folder — a link can come from anywhere. Each line is
   `target<TAB>file:lineno: line`.

   Renaming a linked note breaks those links: Obsidian only rewrites them when
   the rename happens inside Obsidian, and this skill renames on disk. So if
   there are hits, list them and let the user decide — rename in Obsidian
   instead, or rename here and fix the links afterwards. No hits means the
   renames are safe, and it's worth saying so.

5. **Show the user the full list of intended renames and get their agreement**,
   then rename each note:

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py date-prefix "/path/Standup.md"
   ```

   This renames the file in place to `2026-07-01 Standup.md` (using `git mv`
   when the file is tracked, so history survives) and prints the new path. Pass
   `--date 2026-07-01` to override the date for one note, e.g. when the user
   knows the real date and the file's timestamps don't.

6. **Report** the renames you made, `old name → new name`, one per line.

## Notes

- A note already starting with `yyyy-mm-dd` is never touched, so running this
  twice is harmless. `date-prefix` refuses such a file rather than doubling its
  date.
- Renames never overwrite: a numeric suffix is added on collision.
- A batch rename is easy to reverse but touches many files at once, so confirm
  the list before running it — don't rename first and report after.
