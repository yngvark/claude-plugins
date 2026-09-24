# my-skills plugin — design

`my-skills` holds skills that have nothing in common except that the user finds them useful. Each new skill goes here instead of into its own plugin, so consumers install once and get new skills on update. A skill moves to its own plugin only if it grows hooks, settings or enough surface to deserve a separate install.

## notification-summary

The user follows several teams' repositories through GitHub notifications. The notifications page lists threads in update order, so the few that need action (a requested review, a blocked PR) sit between Renovate PRs and quiet subscriptions. The skill reads the same notifications and produces a local HTML page that puts the actionable threads first, with a short summary of each.

### Split between script and Claude

`notification-summary.py` does the deterministic work, and Claude does the judgement:

1. `fetch` gets notifications, applies the query's filters, and enriches each issue or PR thread with author, state, CI result, review decision, body and the comments since the user last read the thread. It writes `notifications.json` to a new temp dir.
2. Claude reads that file and writes `summary.json`. It lists only the threads worth showing, each with a section, priority, lead-in reason and one- or two-sentence summary.
3. `render` merges the two files into HTML. Facts such as title, link, author, age, CI and diff size come from `notifications.json`, so Claude cannot misstate them. Threads that Claude left out go into a collapsed "Other" table, so nothing disappears silently.

Keeping rendering in the script means the page looks the same every run and that tests cover it. Claude writes judgements only, which keeps its output small.

### Query

The skill accepts the query syntax from `github.com/notifications?query=...` (or the whole URL), because the user already has these saved as URLs. The notifications REST API has no search parameter, so the script filters client-side:

- `repo:`, `org:` and `reason:` use fields on the notification itself.
- `topic:` needs one repository lookup per distinct repo. The script caches these lookups.
- `author:` is the issue or PR author, which only the subject lookup returns. The script therefore filters by author after enrichment.

Repeated terms of one kind are OR-ed, and different kinds are AND-ed, matching the GitHub UI. Unknown terms fail loudly rather than being ignored, so a typo does not silently widen the result.

The default query comes from `$NOTIFICATION_SUMMARY_QUERY`. This repo is public, so team topics and colleagues' usernames stay out of it.

### GitHub access

The script calls `gh api --method GET` directly instead of going through the `gh-read` plugin. It uses a fixed set of read-only endpoints, and depending on another plugin's install path would break when that plugin is not installed.

### Page design

The page has a white background with soft, shadowed cards in light mode and near-black with bordered cards in dark mode. The accents are Mediterranean colors: sea blue, terracotta, lemon, green and purple. Priority 1 items are tinted terracotta, and priority 2 items are tinted amber. The page follows the OS theme, and `?theme=light|dark` overrides it. The CSS lives in `summary.css` next to the script.
