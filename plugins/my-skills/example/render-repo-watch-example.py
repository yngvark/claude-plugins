#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.11"
# ///

"""Render the README example repo-watch page from fictional repositories.

Writes example/repo-watch.html. Screenshot it with the screenshot skill to
refresh example/repo-watch-screenshot.png.
"""

from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).parent
SKILLS = HERE.parent / "skills"
rw = SourceFileLoader("rw", str(SKILLS / "repo-watch" / "repo-watch.py")).load_module()

ME = "mona"
NOW = "2026-09-30T07:40:00Z"


def pr(repo, num, title, author, days, updated, **extra):
    p = {"type": "PullRequest", "state": "open", "number": num, "title": title,
         "url": f"https://github.com/acme/{repo}/pull/{num}", "author": author, "draft": False,
         "created_at": f"2026-09-{30 - days:02d}T09:00:00Z", "updated_at": f"2026-09-{30 - updated:02d}T06:00:00Z",
         "labels": [], "comments": 0, "additions": 0, "deletions": 0, "requested_reviewers": [],
         "review_state": "none", "ci": "passing"}
    p.update(extra)
    return p


def issue(repo, num, title, author, days, updated, **extra):
    i = {"type": "Issue", "state": "open", "number": num, "title": title,
         "url": f"https://github.com/acme/{repo}/issues/{num}", "author": author,
         "created_at": f"2026-09-{30 - days:02d}T09:00:00Z", "updated_at": f"2026-09-{30 - updated:02d}T06:00:00Z",
         "labels": [], "comments": 0}
    i.update(extra)
    return i


def repo(name, failing=(), prs=(), issues=()):
    return {"name": f"acme/{name}", "url": f"https://github.com/acme/{name}", "default_branch": "main",
            "failing": list(failing), "prs": list(prs), "issues": list(issues)}


REPOS = [
    repo("platform-templates",
         failing=[{"name": "Nightly end-to-end test", "url": "https://github.com/acme/platform-templates/actions/runs/1",
                   "conclusion": "failure", "event": "schedule", "updated_at": "2026-09-30T03:10:00Z"}],
         prs=[pr("platform-templates", 412, "Upgrade Terraform AWS provider to 6.x", "alice", 2, 0, comments=5,
                 additions=184, deletions=97, requested_reviewers=[ME], review_state="approved"),
              pr("platform-templates", 415, "Add a template for SQS queues", ME, 4, 1, comments=3, additions=320,
                 deletions=4, ci="failing", review_state="changes_requested")],
         issues=[issue("platform-templates", 401, "Database template ignores the backup retention variable", "carol",
                       9, 0, comments=6, labels=["bug"]),
                 issue("platform-templates", 377, "Document how to override the default log retention", "erik",
                       21, 5, comments=2, labels=["documentation"])]),
    repo("deploy-workflows",
         prs=[pr("deploy-workflows", 88, "Cache Terraform providers between plan and apply", "bob", 1, 0,
                 additions=41, deletions=12, draft=True, ci="pending")]),
    repo("infra-cli",
         failing=[{"name": "Release", "url": "https://github.com/acme/infra-cli/actions/runs/2",
                   "conclusion": "failure", "event": "push", "updated_at": "2026-09-29T14:00:00Z"}],
         issues=[issue("infra-cli", 57, "`pkg update` fails when the manifest has comments", "dave", 3, 1,
                       comments=4, labels=["bug"])]),
    repo("docs"),
    repo("reference-app"),
]

DATA = {"title": "Platform repos", "me": ME, "fetched_at": NOW,
        "authors": ["alice", "bob", "carol", "dave", ME], "repos": REPOS}

css = (SKILLS / "notification-summary" / "summary.css").read_text() + (SKILLS / "repo-watch" / "repo-watch.css").read_text()
out = HERE / "repo-watch.html"
out.write_text(rw.render(DATA, css))
print(out)
