---
name: google-docs-clipboard
description: Edit a section of a Google Docs document and put the result on the macOS clipboard so it pastes into Google Docs with headings, numbered lists, links and code intact. Use when the user shares text from a Google Doc, such as a runbook step, and wants it rewritten, or asks you to copy text they will paste into Google Docs.
---

# google-docs-clipboard

You cannot read or write the Google Doc. The user copies a section from it, you edit it, and the user pastes your version back. The script is `${CLAUDE_PLUGIN_ROOT}/skills/google-docs-clipboard/docs-clipboard.py`. It needs macOS.

## 1. Get the original from the clipboard

Text the user pastes into chat has lost its links, heading levels and red or bold text. Read the original from the clipboard instead:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/google-docs-clipboard/docs-clipboard.py read
```

If the script says the clipboard holds no HTML, the user copied plain text or has copied something else since. Ask them to copy the section in Google Docs again. Never drop a link or formatting you cannot see. If you must work from plain text, tell the user which links and formatting they need to add back after pasting.

Write the output to a Markdown draft in the scratchpad directory, one file per section, such as `step-2.md`.

## 2. Edit the draft

- Keep the heading level from the original unless the user asks for another. `##` pastes as Heading 2, `###` as Heading 3.
- Indent nested list items 3 spaces more than their parent.
- Put a command in a fenced code block, indented under its list item. It pastes in Courier New inside the same item, with its indentation kept.
- Place a warning before the step it guards.
- Leave out any part of the section you cannot reproduce in full, such as text whose formatting you only have as plain text. Tell the user what to change there by hand instead.

## 3. Copy it to the clipboard

```bash
${CLAUDE_PLUGIN_ROOT}/skills/google-docs-clipboard/docs-clipboard.py write DRAFT
```

The script puts both HTML and plain text on the clipboard. Tell the user it is ready to paste with Cmd+V, and which text in the document to select first so the paste replaces it.

"Copy again" or "paste again" means run `write` again. You cannot paste for the user, and the clipboard may hold something else by now.

## 4. Later rounds

When the user sends back a version they changed in Google Docs, for example by accepting Google's writing suggestions, that version is the new original. Update the draft to match it word for word, then make the next change on top of it.

## Privacy

The document is the user's. Keep its content in the scratchpad directory. Never write it into a repository, a commit, a skill or a memory file.
