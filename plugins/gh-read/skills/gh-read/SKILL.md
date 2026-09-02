---
name: gh-read
description: Read-only GitHub API access. Use when fetching data from GitHub — listing issues, viewing pull requests, checking CI/workflow run status, reading file contents, comparing branches, listing releases, getting commit details, or viewing git refs and comments.
---

# gh-read — Read-only GitHub API

**NEVER use `gh api` directly.** Always use `${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py` instead. It enforces GET-only access and an endpoint allowlist.

## Usage

```bash
# Print usage / allowed paths / allowed flags
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py --help

# List issues
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues

# Get a specific PR
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls/42

# List workflow runs
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/actions/runs

# Get commit details
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/commits/SHA

# View git refs
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/git/refs

# List comments
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/comments

# Filter with jq
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls --jq '.[].title'

# Paginate results
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues --paginate

# Read file contents
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/contents/path/to/file

# Compare branches
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/compare/main...feature

# List branches / get classic branch protection
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/branches
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/branches/main/protection

# List releases
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/releases

# Query parameters via path
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/issues?state=open

# Use --preview for API previews
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/pulls --preview mercy

# Custom properties (repo values, org schema/values)
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/properties/values
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py orgs/ORG/properties/schema
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py orgs/ORG/properties/values

# Search across GitHub (issues, repos, code, commits, users, labels, topics)
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py 'search/issues?q=repo:OWNER/REPO+is:open+freeze'
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py 'search/repositories?q=language:rust+stars:>1000'

# Notifications (your unread notifications, one thread, or one repo's notifications)
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py notifications
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py 'notifications?all=true&per_page=10'
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py notifications/threads/THREAD_ID
${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/OWNER/REPO/notifications
```

## Allowed paths

- `repos/{owner}/{repo}/` followed by: `issues`, `pulls`, `commits`, `git/refs`, `actions/runs`, `actions/workflows`, `contents`, `compare`, `releases`, `comments`, `branches`, `notifications`, `properties/values` (plus any sub-paths).
- `orgs/{org}/properties/schema` and `orgs/{org}/properties/values` (custom properties).
- `search/{type}` where `{type}` is one of: `issues`, `repositories`, `code`, `commits`, `users`, `labels`, `topics`.
- `notifications` and `notifications/threads/{id}` (plus any sub-paths).

## What's blocked

- Any write flags: `-X`, `--method`, `-f`, `--field`, `--raw-field`, `-F`, `--input`
- Any API path not in the allowlist above (e.g., `/user`, `/repos/o/r/actions/secrets`)

## Missing functionality

If a legitimate read-only GitHub API call is blocked by this skill (path not on the allowlist, flag not supported, etc.), do NOT work around it with `gh api` or other tools. Instead:

1. Show the user a prominent banner notice, e.g.:

   ```
   ╔══════════════════════════════════════════════════════════════════╗
   ║  ⚠️  gh-read SKILL IS MISSING SUPPORT                            ║
   ║                                                                  ║
   ║  Needed: <describe what is missing>                              ║
   ║  Reason: <why the current allowlist/flags are insufficient>      ║
   ║                                                                  ║
   ║  The gh-read skill should be updated to support this.            ║
   ╚══════════════════════════════════════════════════════════════════╝
   ```

2. Offer to create a GitHub issue at https://github.com/yngvark/claude-plugins describing the gap.

3. **NEVER create the issue without explicit user consent.** Wait for the user to confirm before filing anything.
