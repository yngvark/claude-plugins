---
name: gh-issue-draft
description: Create or edit a GitHub issue through a local draft that the user approves before anything reaches GitHub. Use when asked to create, file, write, rewrite or update a GitHub issue.
---

# gh-issue-draft

Never create or edit the issue before the user has approved the exact title and body. The script is `${CLAUDE_PLUGIN_ROOT}/skills/gh-issue-draft/issue-draft.py`.

## 1. Gather

- Follow the repository's issue template in `.github/ISSUE_TEMPLATE/`, if it has one.
- Run `gh repo view OWNER/REPO --json visibility`. If the repository is public, ask before writing team names, internal repository names, account IDs or other identifying details into the issue.
- Check every fact the issue will state against the code on the default branch, not only against the user's description. Link source lines with permalinks to a commit SHA, so the line numbers stay right.
- To edit an existing issue, pull it into a new draft file in the scratchpad directory:

  ```bash
  ${CLAUDE_PLUGIN_ROOT}/skills/gh-issue-draft/issue-draft.py pull OWNER/REPO NUMBER DRAFT
  ```

  The script prints the current title. For a new issue, write the draft file yourself in the scratchpad directory.

## 2. Write

Write the body to the draft file. Load the `talk-normally-v2:talk-normally` skill before you write, and follow it. Also follow the user's rules for issue bodies in CLAUDE.md and the `apply-writing-rules` skill, if installed. Explain each name the reader cannot look up from the issue itself, such as a template variable or an internal stack, at its first mention. Do not hard-wrap paragraphs.

If the `ai-tells` skill is installed, lint the title and the body with it. Fix the findings that are real, and tell the user which ones you left and why.

## 3. Show and wait

Show the title and the full body in chat, in a fenced Markdown block. Use four backticks for the fence when the body contains a code block. You may shorten long URLs to `…` in the chat copy, but say so.

Ask the user to approve. After each round of feedback, update the draft file, lint it again and show the whole new version. Publish only the version the user approved.

## 4. Publish

Create a new issue:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gh-issue-draft/issue-draft.py create OWNER/REPO DRAFT --title "TITLE"
```

Edit an existing one. Leave out `--title` to keep the current title.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gh-issue-draft/issue-draft.py edit OWNER/REPO NUMBER DRAFT --title "TITLE"
```

`edit` works only on a draft that `pull` or `create` saved a `.base` file for. It exits 2 when someone changed the issue on GitHub after that, and prints the diff. Merge those changes into the draft and show the user the result. Once they approve, move `DRAFT.live` to `DRAFT.base` and run `edit` again.

Both commands read the issue back and fail if GitHub's body differs from the draft. Give the user a link to the issue.
