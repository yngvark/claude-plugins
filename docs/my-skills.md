# my-skills plugin — design

`my-skills` holds skills that have nothing in common except that the user finds them useful. Each new skill goes here instead of into its own plugin, so consumers install once and get new skills on update. A skill moves to its own plugin only if it grows hooks, settings or enough surface to deserve a separate install.

notification-summary and anonymize-eval-prompts are slash-only. Each runs only when the user asks for it explicitly, and keeping them out of Claude's skill list keeps their descriptions out of every session's context.

## notification-summary

The user follows several teams' repositories through GitHub notifications. The notifications page lists threads in update order, so the few that need action (a requested review, a blocked PR) sit between Renovate PRs and quiet subscriptions. The skill reads the same notifications and produces a local HTML page that puts the actionable threads first, with a short summary of each.

### Split between script and Claude

`notification-summary.py` does the deterministic work, and Claude does the judgement:

1. `fetch` gets notifications, applies the query's filters, and enriches each issue or PR thread with author, state, CI result, review decision, body and the comments since the user last read the thread. It writes `notifications.json` to a new temp dir.
2. Claude reads that file and writes `summary.json`. It lists only the threads worth showing, each with a section, priority, lead-in reason and one- or two-sentence summary. It also writes two to four highlights that answer "what should I do now?" and that render at the top of the page.
3. `render` merges the two files into HTML and opens the page in the default browser. Facts such as title, link, author, age, CI and diff size come from `notifications.json`, so Claude cannot misstate them. Threads that Claude left out go into a collapsed "Other" table, newest activity first with an "Updated" column, so nothing disappears silently.

Keeping rendering in the script means the page looks the same every run and that tests cover it. Claude writes judgements only, which keeps its output small.

### Query

The skill accepts the query syntax from `github.com/notifications?query=...` (or the whole URL), because the user already has these saved as URLs. The notifications REST API has no search parameter, so the script filters client-side:

- `repo:`, `org:` and `reason:` use fields on the notification itself.
- `topic:` needs one repository lookup per distinct repo. The script caches these lookups.
- `author:` is the issue or PR author, which only the subject lookup returns. The script therefore filters by author after enrichment.

Repeated terms of one kind are OR-ed, and different kinds are AND-ed, matching the GitHub UI. Unknown terms fail loudly rather than being ignored, so a typo does not silently widen the result.

The default query comes from `$NOTIFICATION_SUMMARY_QUERY`. This repo is public, so team topics and colleagues' usernames stay out of it.

### GitHub access

The script calls `gh api` directly instead of going through the `gh-read` plugin. It uses a fixed set of endpoints, and depending on another plugin's install path would break when that plugin is not installed. `fetch` only reads.

GitHub's notifications API rejects fine-grained tokens, while the token inside a sandbox is usually fine-grained and scoped to one owner. When `GITHUB_NOTIFICATIONS_TOKEN` is set, the script sends notification endpoints (listing and marking done) with it as `GH_TOKEN`, and every other call with gh's default auth. The variable holds a classic token with only the `notifications` scope, so the broad token never reads repo content. sc2 hands it to the sandbox only on launches with `-e gn`. A thread whose repo the default token cannot read stays in the result with `"enriched": false` and only the notification's own fields, instead of aborting the fetch.

### Marking as done

`done ID...` sends `DELETE /notifications/threads/{id}`, which is GitHub's "mark as done". GitHub then leaves the thread out of the notifications list until it gets new activity, so the next run of the skill does not show it again. The script keeps no state of its own for this.

Each thread on the page has a checkbox. The page shows a command for the ticked threads, such as `for id in 1 2; do gh api --silent --method DELETE notifications/threads/$id; done`, and the user copies it into a terminal. The command passes `--silent` because gh otherwise sends each response through the pager, which waits for a keypress on every thread. The page shows the plain `gh` call rather than the `done` command so the user can see what they run. The page cannot call GitHub itself, because a local HTML file has no access to the user's token, and putting a token in the browser would expose it. Both the page and `done` accept only numeric IDs, so a bad ID cannot reach another API path.

`done` exists for Claude. When the user names threads in chat, Claude runs `done`, because the gh-read hook blocks Bash commands that call `gh api` directly.

### Page design

The page has a white background with soft, shadowed cards in light mode and near-black with bordered cards in dark mode. The accents are Mediterranean colors: sea blue, terracotta, lemon, green and purple. Priority 1 items are tinted terracotta, and priority 2 items are tinted amber. Highlights sit in one card between the counters and the sections. Their text may contain `[text](url)` links, and the script turns only http(s) URLs into links. The page follows the OS theme, and `?theme=light|dark` overrides it. The CSS lives in `summary.css` next to the script.

The README shows `example/screenshot.png`. `example/render-example.py` renders the page it is taken from, using fictional repositories and people, because this repo is public and real notifications name colleagues and internal repos. Rerun it and screenshot the HTML at 900px width in light mode after changing the page design.

## apply-writing-rules

The user's writing rules for any prose a human reads. They are a skill rather than part of the user's CLAUDE.md so that only the description sits in every session's context; the ~3k-token body loads when Claude is about to write docs, PR descriptions, commit messages and similar text. It is model-invocable for that reason, unlike notification-summary. The user's CLAUDE.md keeps a one-line pointer to the skill so Claude reaches for it.

## anonymize-eval-prompts

Step 2 of `claude plugin eval` asks for real prompts where a skill should or should not have helped. Real prompts make better eval cases than drafted ones, but they come from colleagues, who should not find their own words, names or systems in an eval. The skill turns real prompts into cases that keep each prompt's request and its "should help" label, and drop everything else that points back to the author.

It works in two passes. Claude first replaces private details with fictional ones of the same kind, so a repository name stays a repository name and the skill under test still sees a realistic prompt. Public terms the skill reacts to, such as tool names and commands, stay. Claude then rewrites the anonymized prompts with the `lossless-text-compression` skill. That skill's true/false statements make sure each rewrite still asks for the same thing, while the compression changes the wording. Anonymizing first means the compression agents never see the private details.

`check-rewrites.py` makes the result checkable without a human reading every pair. It fails a case when a removed detail is still in the rewrite, or when the rewrite shares more than four consecutive words with its original. Four words allows common phrases and short commands but catches copied sentences. The user still approves the final list, because only they know whether a rewrite is recognizable to its author.

The originals live only in the session's scratchpad directory and the conversation, never in a repository, and Claude deletes the scratchpad files after the user approves.
