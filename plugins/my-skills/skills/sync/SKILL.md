---
name: sync
description: Bring this machine to the target state described in the user's "Sync document" note, which lists what must be the same on all of the user's Macs. Takes an optional section name to sync only that item.
argument-hint: "[section name]"
disable-model-invocation: true
---

# sync

The user keeps a note called "Sync document" in their notes folder. Each `##` section in it describes one thing that must be set up on every one of their Macs, usually with a command that checks it and a command that installs it. This skill makes the current machine match the note. Running it twice in a row must change nothing the second time.

## 1. Read the note

Use the `notes:note` skill to read the note named "Sync document". Its file name starts with a date, so find it by those words and don't ask the user for the file name. If the notes skill finds nothing, tell the user and stop.

If the user passed a section name, sync only the section whose heading matches it. Otherwise sync every section. Skip sections whose heading starts with `Howto`, because they explain tools and describe no target state.

## 2. Check each section

Run the section's check commands and compare the output with what the section says it should be. If the check block is missing or says `TODO`, use another check the section's text mentions. If it mentions none, work one out from what the section says must be true, and tell the user which check you used.

## 3. Fix what differs

When a check fails, run the section's install commands, then run the check again.

- Running `/sync` is the user's request to run the install commands written in the note, so don't ask before running them.
- Ask before you remove anything, and before you run a command that is not written in the note.
- Some steps can't run from here. A step might have to run outside the sandbox, or need a token that the user creates by hand. Give the user those steps as commands to run, and don't work around a denied path.
- If an install command fails, report its output and go on with the next section.

## 4. Report

Show one table with a row per section: the section name, whether it was already in place, what you did, and whether the check passes now. Under the table, list the steps the user must do themselves.

If a check command in the note was missing, wrong or out of date, propose a fix to the note. Edit the note only if the user agrees.
