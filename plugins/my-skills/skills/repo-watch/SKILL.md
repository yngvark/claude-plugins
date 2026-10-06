---
name: repo-watch
description: Build an HTML page that lists, per repository, the workflows whose latest run on the default branch failed, open PRs by the user's team, and open issues, with dependency-update PRs left out.
disable-model-invocation: true
---

# repo-watch

Run the script. It builds the whole page on its own; Claude writes nothing into it.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/repo-watch/repo-watch.py [--config FILE] [--no-open]
```

It prints the path to `repo-watch.html` in a new temp dir and opens it in the browser. Takes 10–20 seconds for about 20 repos.

The config is TOML at `--config`, `$REPO_WATCH_CONFIG` or `~/.config/my-skills/repo-watch.toml`, with `title`, `authors` (team logins whose PRs to show) and `repos` (`owner/name`). If it is missing, the script prints an example; help the user create it.

Repos that fail to load are listed at the bottom of the page. A 404 on a repo that exists usually means the `gh` token has no SSO authorization for that org; tell the user to authorize it (`gh auth refresh`, or the SSO settings of the token).

After the run, tell the user in one or two sentences what stands out: failing workflows, and PRs that wait on their review.
