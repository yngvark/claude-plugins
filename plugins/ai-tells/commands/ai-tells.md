---
description: Lint prose for AI writing tells using the vale-ai-tells Vale package.
argument-hint: "[file paths, or nothing to check what was just written]"
allowed-tools: ["Bash", "Read", "Edit", "Skill"]
---

Run the `ai-tells` skill to lint prose for AI writing tells.

What to check: $ARGUMENTS

If that names files, lint those. If it is empty, lint the prose files changed in
the working tree (`git status --short`); when there are none, ask the user which
text they mean.

Report the findings and say which ones look like real tells and which look like
false positives. Do not edit anything unless the user asks for fixes.
