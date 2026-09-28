#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

"""Render the README example page from fictional notifications.

Writes example/notification-summary.html. Screenshot it with the screenshot
skill to refresh example/screenshot.png.
"""

import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).parent
SKILL = HERE.parent / "skills" / "notification-summary"
ns = SourceFileLoader("ns", str(SKILL / "notification-summary.py")).load_module()

ME = "mona"
NOW = "2026-09-28T07:40:00Z"


def thread(i, repo, typ, num, title, author, reason, state="open", days=1, comments=0, **extra):
    t = {
        "id": str(i), "unread": True, "reason": reason, "updated_at": NOW, "last_read_at": None,
        "repo": f"acme/{repo}", "type": typ, "number": num, "title": title,
        "url": f"https://github.com/acme/{repo}/{'pull' if typ == 'PullRequest' else 'issues'}/{num}",
        "author": author, "state": state, "draft": False,
        "created_at": f"2026-09-{28 - days:02d}T09:00:00Z",
        "closed_at": NOW if state in ("merged", "closed") else None,
        "labels": [], "comments": comments, "body": "", "recent_comments": [],
    }
    if typ == "PullRequest":
        t.update({"additions": 0, "deletions": 0, "requested_reviewers": [], "review_state": "none", "ci": "passing"})
    t.update(extra)
    return t


THREADS = [
    thread(1, "platform", "PullRequest", 412, "Upgrade Terraform AWS provider to 6.x", "alice",
           "review_requested", days=2, comments=5, additions=184, deletions=97, requested_reviewers=[ME],
           review_state="approved", labels=["dependencies"]),
    thread(2, "checkout", "PullRequest", 88, "Retry payment webhook on 5xx from provider", ME,
           "author", days=4, comments=3, additions=61, deletions=12, ci="failing", review_state="changes_requested"),
    thread(3, "checkout", "Issue", 91, "Orders stuck in PENDING after webhook timeout", "carol",
           "assign", days=1, comments=7, labels=["bug", "P2"]),
    thread(4, "platform", "PullRequest", 409, "Move ECS task logs to a 30-day retention class", "dave",
           "subscribed", state="merged", days=3, comments=9, additions=23, deletions=40),
    thread(5, "docs", "Issue", 57, "Decide on a naming convention for shared modules", "alice",
           "mention", days=6, comments=14, labels=["discussion"]),
    thread(6, "platform", "PullRequest", 415, "chore(deps): update actions/checkout to v5", "renovate[bot]",
           "subscribed", days=1, additions=2, deletions=2),
    thread(7, "checkout", "PullRequest", 87, "Fix typo in README", "dave", "subscribed", state="merged", days=2,
           additions=1, deletions=1),
    thread(8, "docs", "PullRequest", 58, "Add runbook for rotating the payment provider key", "carol",
           "subscribed", days=1, comments=1, additions=40, deletions=0),
    thread(9, "platform", "Issue", 401, "Nightly backup job logs a warning about missing tags", "bob",
           "subscribed", state="closed", days=5, comments=2),
]

DATA = {
    "me": ME, "fetched_at": NOW, "since": "2026-09-21T07:40:00Z",
    "query": {"topics": ["platform"], "authors": [], "repos": [], "orgs": [], "reasons": [], "types": [],
              "unread_only": False},
    "threads": THREADS,
}

SUMMARY = {
    "title": "Platform team notifications",
    "items": [
        {"id": "1", "section": "needs_you", "priority": 1, "reason": "Review requested from you",
         "summary": "Bumps the AWS provider in every template. alice approved; dave waits on a second approval "
                    "before the Friday release."},
        {"id": "2", "section": "needs_you", "priority": 1, "reason": "Your PR is blocked",
         "summary": "carol asked for a cap on retries and CI fails on the new `webhook_retry` test."},
        {"id": "3", "section": "needs_you", "priority": 2, "reason": "Assigned to you",
         "summary": "Three orders from Monday never left PENDING. carol narrowed it to the webhook timeout; "
                    "nobody has picked it up yet."},
        {"id": "4", "section": "worth_reading",
         "summary": "Task logs now expire after 30 days instead of never. Saves about a third of the CloudWatch "
                    "bill; long-term debugging uses the S3 archive."},
        {"id": "5", "section": "worth_reading",
         "summary": "The team settled on `<team>-<purpose>` for shared modules. Existing modules get renamed "
                    "in October."},
    ],
}


def main() -> int:
    css = (SKILL / "summary.css").read_text()
    out = HERE / "notification-summary.html"
    out.write_text(ns.render(DATA, SUMMARY, css))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
