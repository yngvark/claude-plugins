---
name: public-ready
description: Pre-publication scan for the current Git repo. Use when the user asks "is this safe to make public", "scan for secrets before publishing", "check for leaks", "what shouldn't be in this repo if it goes public", or otherwise wants a leak/internal-info check before opening a repo to the public.
---

# public-ready — pre-publication scan

Use this skill when the user wants to check whether the current repository is safe to make public (or to push to a public remote). It scans the **publish set** — files tracked at HEAD plus staged additions — which is what would become visible on the next `git push`.

## How to run the scan

1. **Run `scan.py` for the secrets pass.**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/skills/public-ready/scan.py
   ```

   This uses `gitleaks` under the hood and prints a markdown `## Secrets` section to stdout. If `gitleaks` is missing the script prints an install hint and exits non-zero — relay that to the user and stop.

2. **Read the publish-set files for the internal-info pass.**

   Get the list of files to inspect by running:

   ```bash
   git ls-files
   git diff --cached --name-only --diff-filter=A
   ```

   Read the union of those files (skip binaries, lockfiles, and anything obviously generated). Look for organization-specific or personal information that probably shouldn't be public:

   - **Internal hostnames / URLs** — anything pointing at infrastructure that isn't a public website (e.g., `*.internal`, `*.corp`, `*.local`, internal subdomains of an organization, `intranet.*`).
   - **RFC1918 / link-local IPs** — `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, `169.254.x.x`. (Don't flag `127.0.0.1` or `0.0.0.0`.)
   - **Real-looking email addresses** on non-generic domains (i.e., not `@example.com`, `@gmail.com`, etc.). Especially employee-shaped addresses on company domains.
   - **Personal names** that look like real employees (firstname.lastname, "Reviewed by …", changelog entries with full names, commit-author-shaped strings inside files).
   - **Internal project codenames** — strings that look like internal project names not used externally. Use repo context (README, package metadata) to judge whether a name is public or internal.
   - **Private network identifiers** — internal Slack workspace IDs, internal Jira project keys mentioned in code, internal ticket links.

   Be conservative. Prefer false negatives over false positives. Skip:

   - Placeholder names: `John Doe`, `Jane Smith`, `Foo Bar`, `Alice`, `Bob`.
   - Documentation IPs: `192.0.2.x`, `198.51.100.x`, `203.0.113.x` (RFC 5737 reserved-for-docs ranges).
   - Generic example emails: `*@example.com`, `*@test.com`.
   - The user's own commit-author email/name as visible in `git log` — that's already public on the repo's commits.
   - Strings inside vendored / generated / lockfile content.

3. **Emit the combined report.**

   Reply to the user with a single markdown report in this exact shape:

   ```markdown
   # public-ready report

   ## Secrets
   <output of scan.py's "## Secrets" section, verbatim>

   ## Possibly internal info
   - <file>:<line> — <short reason why this looks internal/personal>
   - ...
   _(or "_No internal/personal info detected._" if nothing found)_

   ## Verdict
   <one of:>
   - "Looks safe to publish."
   - "Found N issue(s) — review before publishing."
   ```

   The verdict count is the total number of items across both sections. The user's next action is on them — do not modify any files.
