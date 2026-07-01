---
description: Jot a quick thought or reminder into your Markdown/Obsidian notes folder as a new file.
argument-hint: [the thought to capture]
allowed-tools: ["Bash", "Write", "Skill"]
---

Run the `note` skill to capture a thought into the user's notes folder.

The note content is: $ARGUMENTS

If that is empty, ask the user (briefly) what they want to capture, then invoke
the skill. Confirm the saved note's file name when done.
