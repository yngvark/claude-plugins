---
description: Put a yyyy-mm-dd date in front of notes that don't have one.
argument-hint: [optional folder, e.g. ki]
allowed-tools: ["Bash", "Read", "Skill"]
---

Run the `add-date-prefix` skill to rename undated notes so their name starts
with a date.

Folder: $ARGUMENTS

If a folder is named above, work only in that folder. Otherwise work in the top
level of the notes folder. Show the intended renames and get agreement before
renaming anything.
