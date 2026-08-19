---
description: Jot a quick thought or reminder into your Markdown/Obsidian notes folder as a new file.
argument-hint: [the thought to capture]
allowed-tools: ["Bash", "Read", "Write", "Skill"]
---

Run the `note` skill to capture a thought into the user's notes folder.

The note content is: $ARGUMENTS

If that is empty, ask the user (briefly) what they want to capture, then invoke
the skill. Confirm the saved note's file name when done.

If the text instead refers to a note that already exists (a file name, "see
X.md", "that note about Y"), the user wants it read — run the `read-note` skill
and don't create a new file.
