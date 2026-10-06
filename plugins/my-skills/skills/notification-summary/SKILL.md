---
name: notification-summary
description: Summarize the most important GitHub issues and PRs from the user's notifications into an HTML page in a temp dir. Takes an optional github.com/notifications URL or query.
disable-model-invocation: true
---

# notification-summary

Builds an HTML page that opens with a few highlights, then sorts the user's GitHub notifications into "Needs you", "Worth reading" and a collapsed "Other" table, with a one- or two-sentence summary per thread.

The script is `${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py`. It calls GitHub through `gh`. Only the `done` command changes anything.

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

It prints the path to `notifications.json` in a new temp dir. GitHub's notifications API rejects fine-grained tokens, so the script lists notifications with `$GITHUB_NOTIFICATIONS_TOKEN` (a classic token) when it is set. If the fetch fails because that variable is missing, tell the user to relaunch the sandbox with the env bundle that provides `GITHUB_NOTIFICATIONS_TOKEN` (`sc2 -e gn`), and stop. If `gh` fails because it cannot read its config, tell the user and stop.

## 3. Judge

Read `notifications.json`. `me` is the user's login. Each thread has `reason` (`review_requested`, `mention`, `assign`, `author`, `comment`, `subscribed`, …), state, CI, review state, body and the comments since the user last read it. A thread with `"enriched": false` is in a repo the token could not read, so it has only the title, repo, reason and update time. Summarize it from those alone and say that the details were unavailable.

Write `summary.json` next to it:

```json
{
  "title": "Platform team notifications",
  "highlights": [
    {"label": "Top priority", "text": "On [platform#412](https://github.com/acme/platform/pull/412), bob asked you to decide on the provider version. The release waits on it."},
    {"label": "Other review requests", "text": "Four more PRs wait on your review. Two of them are already approved."}
  ],
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
- `highlights` is the short answer to "what should I do now?". Write two to four items, most urgent first, each with a label of one to three words and one or two plain sentences. Group threads where that helps ("Six more PRs wait on your review"). Link threads as `[repo#N](url)`; only http(s) links render. Give the user the same highlights in chat.
- `title` names the query in a few words.

## 4. Render

```bash
${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py render <dir>/notifications.json <dir>/summary.json
```

The command opens the page in the default browser and prints its path; pass `--no-open` to skip that. The page follows the OS light/dark setting; `?theme=light` or `?theme=dark` overrides it.

## 5. Mark as done

Each thread on the page has a checkbox. Ticking threads shows a `gh` command at the bottom of the page that the user runs in a terminal. It marks the notifications as done on GitHub, so the next fetch leaves them out until they get new activity.

If the user names threads in chat instead ("mark the Renovate PRs as done"), look up their IDs in `notifications.json` and run:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/notification-summary/notification-summary.py done <thread id> [<thread id> ...]
```
