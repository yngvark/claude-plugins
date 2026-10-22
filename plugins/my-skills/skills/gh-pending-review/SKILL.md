---
name: gh-pending-review
description: Create a pending (unsubmitted) GitHub pull request review with line comments and suggested changes, after showing the user each comment with the current code and the suggested code. Use when asked to create a pending review, add review comments to a PR, or suggest a change on a PR.
---

# gh-pending-review

The script is `${CLAUDE_PLUGIN_ROOT}/skills/gh-pending-review/pending-review.py`. It works without the GitHub API being callable from Bash, so never tell the user you cannot create the review.

The user wants to see the review, not your process. Do not mention the draft file, the script, or how the review reaches GitHub.

## 1. Write the draft

Read the PR diff with `gh pr diff NUMBER -R OWNER/REPO`. Write the draft to a new Markdown file in the scratchpad directory:

````markdown
Optional review comment, shown at the top of the review.

## path/to/file.tf:14
Comment text.

```suggestion
  new_name = {
```

## path/to/file.tf:10-14
A comment on lines 10 to 14 of the new version.

## path/to/file.tf:9 (old)
A comment on line 9 of the old version, such as a removed line.
````

- Keep the user's wording. Write in their language and tone when you fill a gap, such as a `TODO` or "find examples".
- When a comment asks for a code change, add a `suggestion` block with the new version of the commented lines. Write it from the user's guidance, and check it against the code.
- Check every fact in a comment, such as "we use X elsewhere", against the repository.
- Link every file you mention in a comment, so the reader can click it. Use a permalink to the commit SHA of the default branch, with the line number: `` [`app/config.tf`](https://github.com/OWNER/REPO/blob/SHA/app/config.tf#L80) ``.

## 2. Preview and wait

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gh-pending-review/pending-review.py preview OWNER/REPO NUMBER DRAFT
```

The script fails when a comment points at a line outside the PR diff, because GitHub rejects those. Move the comment to a line in the diff.

Show the output in chat exactly as printed. For each comment, it shows the current code ("Now"), the suggested code and the comment text. Then ask the user to approve. After feedback, update the draft and show the whole preview again.

## 3. Create

Once the user approves:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gh-pending-review/pending-review.py create OWNER/REPO NUMBER DRAFT
```

The script adds the comments to the user's pending review on the PR, or starts one. It never submits the review. Reply with one line and the link it prints.

## 4. Change a comment after creating it

Update the draft, show the preview again and wait for approval. Then run `edit` with a draft that holds only the changed comments, on the same lines as before:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gh-pending-review/pending-review.py edit OWNER/REPO NUMBER DRAFT
```
