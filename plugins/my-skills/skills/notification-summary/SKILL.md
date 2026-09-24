---
name: notification-summary
description: Summarize the most important GitHub issues and PRs from the user's notifications into an HTML page in a temp dir. Use when the user asks to summarize, triage or catch up on GitHub notifications, or passes a github.com/notifications URL or query.
---

# notification-summary

Builds an HTML page that sorts the user's GitHub notifications into "Needs you", "Worth reading" and a collapsed "Other" table, with a one- or two-sentence summary per thread.

The script is `${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py`. It only makes GET requests through `gh`.

## 1. Pick the query

Use, in order:

1. The query or `github.com/notifications?query=...` URL the user passed.
2. `$NOTIFICATION_SUMMARY_QUERY`.
3. Otherwise ask the user for one.

Supported terms: `topic:`, `author:`, `repo:`, `org:`, `reason:`, `is:unread`, `is:pr`, `is:issue`. Repeated terms of the same kind are OR-ed; different kinds are AND-ed. The default window is the last 7 days; pass `--days N` if the user asks for another.

## 2. Fetch

```bash
${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py fetch "<query>" [--days N]
```

It prints the path to `notifications.json` in a new temp dir. If `gh` fails because it cannot read its config (a sandbox), tell the user and stop.

## 3. Judge

Read `notifications.json`. `me` is the user's login. Each thread has `reason` (`review_requested`, `mention`, `assign`, `author`, `comment`, `subscribed`, …), state, CI, review state, body and the comments since the user last read it.

Write `summary.json` next to it:

```json
{
  "title": "Platform team notifications",
  "items": [
    {"id": "<thread id>", "section": "needs_you", "priority": 1,
     "reason": "Review requested from you",
     "summary": "Bumps the AWS provider in all templates. alice approved; bob waits on a second approval."}
  ]
}
```

- **`needs_you`**: the user must act. A review is requested from them, they are mentioned or assigned and the thread is still open, or their own PR (`author == me`) has changes requested or failing CI. Priority 1 blocks someone or has a deadline; priority 2 is the rest.
- **`worth_reading`**: no action needed, but the team made a decision, merged something notable, or discussed actively. Omit `priority`.
- Leave out everything else (bot PRs, quiet threads, trivial merges). The page lists those under "Other".
- `reason` is a short lead-in for `needs_you` items. Omit it for `worth_reading`.
- `summary` says where the thread stands and what the user would need to know, in one or two plain sentences. Base it on the body and recent comments, not only the title. Backticks render as code.
- `title` names the query in a few words.

## 4. Render

```bash
${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py render <dir>/notifications.json <dir>/summary.json
```

Give the user the printed HTML path as an `open <path>` command. The page follows the OS light/dark setting; `?theme=light` or `?theme=dark` overrides it.
