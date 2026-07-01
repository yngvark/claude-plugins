---
name: daily-notes-add-title
description: Give bare daily notes a descriptive title. Renames files named yyyy-mm-dd.md to "yyyy-mm-dd <title>.md" where the title summarizes the note's contents. Use when the user says "/daily-notes-add-title", "add titles to my daily notes", or "title my untitled daily notes".
---

# daily-notes-add-title — title untitled daily notes

The user creates daily notes named just by date, e.g. `2026-07-01.md`. This
skill reads such a note and renames it to include a short title that reflects
its contents, e.g. `2026-07-01 Sprint planning and infra cleanup.md`.

## Steps

1. **Resolve the notes folder** (and surface any error, then stop):

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py resolve-dir
   ```

2. **Find the untitled daily notes to process.**

   - If the user named a specific file, use that.
   - Otherwise list every bare `yyyy-mm-dd.md` file:

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py daily-list
     ```

     Add `--recursive` if the user keeps daily notes in subfolders. Files that
     already have a title (e.g. `2026-07-01 something.md`) are not listed —
     they're skipped by design.

   If nothing is listed, tell the user there are no untitled daily notes and
   stop.

3. **For each file, read its contents** with the Read tool and derive a
   **concise title** (a handful of words) summarizing what the day's note is
   about. Skip empty files — tell the user they were skipped rather than
   inventing a title. Keep titles readable with normal spaces and capitalization
   (e.g. `Meeting with team`); the script strips characters that are illegal in
   filenames.

4. **Rename** each file:

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/notes.py daily-rename "/path/2026-07-01.md" "Meeting with team"
   ```

   This renames the file in place to `2026-07-01 Meeting with team.md` (using
   `git mv` when the file is tracked, so history is preserved), and prints the
   new path.

5. **When more than one file is involved**, briefly confirm each proposed title
   with the user before renaming, or show the full list of intended renames and
   proceed once they agree. Renaming is easy to reverse, but a batch rename is
   worth a quick check.

6. **Report** the renames you made (old name → new name), one per line.

## Notes

- Only files matching `yyyy-mm-dd.md` exactly are candidates. The date prefix
  is always preserved; only a title is appended.
- Do not edit the note's contents — this skill only renames files.
