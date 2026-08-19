---
description: Find and read an existing note from your Markdown/Obsidian notes folder.
argument-hint: [note name, or a topic to look up]
allowed-tools: ["Bash", "Read", "Skill"]
---

Run the `read-note` skill to find and read an existing note.

What to look up: $ARGUMENTS

If that is empty, ask the user (briefly) which note they mean, or list the most
recent notes for them to pick from. Never create a new note in this command.
