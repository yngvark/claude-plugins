#!/usr/bin/env -S uv --quiet run --locked --script

# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "7 days"
# ///

"""Create or edit a GitHub issue from a local draft without overwriting edits made on GitHub.

    issue-draft.py pull REPO NUMBER DRAFT
    issue-draft.py create REPO DRAFT --title TITLE
    issue-draft.py edit REPO NUMBER DRAFT [--title TITLE]

DRAFT is a Markdown file that holds the issue body. After each pull, create
or edit, the script saves the body GitHub returned as DRAFT.base. `edit`
compares the live body with DRAFT.base first. If they differ, someone edited
the issue on GitHub in the meantime: the script writes the live body to
DRAFT.live, prints the diff and exits 2 without editing anything.

After `create` and `edit`, the script reads the issue back and exits 1 if
GitHub's body differs from DRAFT.

Set ISSUE_DRAFT_GH to use another `gh` binary (the tests use a fake one).
"""

import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path


def gh(*args: str) -> str:
    cmd = [os.environ.get("ISSUE_DRAFT_GH", "gh"), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{result.stderr.strip()}")
    return result.stdout


def normalize(body: str) -> str:
    # GitHub stores bodies edited in its web UI with CRLF line endings, and gh adds or drops trailing newlines.
    return body.replace("\r\n", "\n").strip()


def diff(old: str, new: str, old_name: str, new_name: str) -> str:
    lines = difflib.unified_diff(
        normalize(old).splitlines(), normalize(new).splitlines(), old_name, new_name, lineterm=""
    )
    return "\n".join(lines)


def base_path(draft: Path) -> Path:
    return draft.with_name(draft.name + ".base")


def live_path(draft: Path) -> Path:
    return draft.with_name(draft.name + ".live")


def fetch(repo: str, number: str) -> dict:
    return json.loads(gh("issue", "view", number, "-R", repo, "--json", "title,body"))


def verify(repo: str, number: str, draft: Path) -> None:
    live = fetch(repo, number)["body"]
    if normalize(live) != normalize(draft.read_text()):
        sys.exit(f"The body on GitHub differs from {draft}:\n" + diff(draft.read_text(), live, str(draft), "github"))
    base_path(draft).write_text(live)


def pull(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if draft.exists():
        sys.exit(f"{draft} already exists. Pick a new path, so a local draft is never overwritten.")
    issue = fetch(args.repo, args.number)
    draft.write_text(normalize(issue["body"]) + "\n")
    base_path(draft).write_text(issue["body"])
    print(issue["title"])
    return 0


def create(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    url = gh("issue", "create", "-R", args.repo, "--title", args.title, "--body-file", str(draft)).split()[-1]
    verify(args.repo, url.rstrip("/").rsplit("/", 1)[-1], draft)
    print(url)
    return 0


def edit(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    base = base_path(draft)
    if not base.exists():
        sys.exit(f"{base} is missing. Run `pull` first, or create the issue with this script.")
    live = fetch(args.repo, args.number)["body"]
    if normalize(live) != normalize(base.read_text()):
        live_path(draft).write_text(live)
        print(
            f"The issue changed on GitHub after {base} was saved. "
            f"Merge the changes from {live_path(draft)} into {draft}, move it to {base}, and run edit again.",
            file=sys.stderr,
        )
        print(diff(base.read_text(), live, str(base), "github"))
        return 2
    cmd = ["issue", "edit", args.number, "-R", args.repo, "--body-file", str(draft)]
    if args.title:
        cmd += ["--title", args.title]
    url = gh(*cmd).split()[-1]
    verify(args.repo, args.number, draft)
    print(url)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pull", help="write an existing issue's body to a new draft file")
    p.add_argument("repo")
    p.add_argument("number")
    p.add_argument("draft")
    p.set_defaults(func=pull)

    p = sub.add_parser("create", help="create an issue from a draft file")
    p.add_argument("repo")
    p.add_argument("draft")
    p.add_argument("--title", required=True)
    p.set_defaults(func=create)

    p = sub.add_parser("edit", help="replace an issue's body with a draft file")
    p.add_argument("repo")
    p.add_argument("number")
    p.add_argument("draft")
    p.add_argument("--title")
    p.set_defaults(func=edit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
