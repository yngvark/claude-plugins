---
description: Add a descriptive title to bare yyyy-mm-dd daily notes based on their contents.
argument-hint: [optional path to a specific daily note]
allowed-tools: ["Bash", "Read", "Skill"]
---

Run the `daily-notes-add-title` skill to give untitled daily notes
(`yyyy-mm-dd.md`) a title that reflects their contents.

Target: $ARGUMENTS

If a specific file path is given above, title just that note. Otherwise find
and process all untitled daily notes in the notes folder. Report each rename.
