#!/usr/bin/env -S uv --quiet run --locked --script

# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "7 days"
# ///

"""Preview and create a pending GitHub pull request review from a local draft.

    pending-review.py preview REPO NUMBER DRAFT
    pending-review.py create REPO NUMBER DRAFT

DRAFT is a Markdown file. Text before the first comment header is the review
body, and may be empty. Each comment starts with a header line:

    ## path/to/file.tf:14        comment on line 14 of the new version
    ## path/to/file.tf:10-14     comment on lines 10 to 14
    ## path/to/file.tf:14 (old)  comment on line 14 of the old version

The comment text follows its header. A ```suggestion block in it holds the
new version of the commented lines.

`preview` checks that every commented line is part of the PR diff, and prints
each comment with the current code and the suggested code. `create` runs the
same check, then adds the comments to the user's pending review, or starts a
new pending review if there is none. It never submits the review. Afterwards
it reads the review back and exits 1 if a comment is missing.

Set PENDING_REVIEW_GH to use another `gh` binary (the tests use a fake one).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HEADER = re.compile(r"^## (?P<path>\S+):(?P<start>\d+)(?:-(?P<end>\d+))?(?P<old> \(old\))?\s*$")
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
SUGGESTION = re.compile(r"^(?P<fence>`{3,})suggestion[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$\n?", re.M | re.S)


@dataclass
class Comment:
    path: str
    start: int
    end: int
    side: str
    body: str

    @property
    def location(self) -> str:
        lines = f"{self.start}-{self.end}" if self.start != self.end else str(self.end)
        return f"{self.path}:{lines}" + (" (old)" if self.side == "LEFT" else "")


def gh(*args: str, stdin: str | None = None) -> str:
    cmd = [os.environ.get("PENDING_REVIEW_GH", "gh"), *args]
    result = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{result.stderr.strip()}")
    return result.stdout


def normalize(body: str) -> str:
    # GitHub stores bodies with CRLF line endings when they pass through its web UI.
    return body.replace("\r\n", "\n").strip()


def parse_draft(text: str) -> tuple[str, list[Comment]]:
    body: list[str] = []
    comments: list[Comment] = []
    for line in text.splitlines():
        m = HEADER.match(line)
        if m:
            start = int(m["start"])
            end = int(m["end"] or start)
            if end < start:
                sys.exit(f"Bad line range in header: {line}")
            comments.append(Comment(m["path"], start, end, "LEFT" if m["old"] else "RIGHT", ""))
        elif comments:
            comments[-1].body += line + "\n"
        else:
            body.append(line)
    for c in comments:
        c.body = c.body.strip()
        if not c.body:
            sys.exit(f"The comment on {c.location} is empty.")
    if not comments:
        sys.exit("The draft has no comments. Each comment starts with a line like `## path/to/file:14`.")
    return "\n".join(body).strip(), comments


def parse_diff(diff: str) -> dict[tuple[str, str], dict[int, str]]:
    """Map (path, side) to the lines a review comment can point at: {line number: text}."""
    lines: dict[tuple[str, str], dict[int, str]] = {}
    path = old_path = None
    old = new = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = old_path = None
        elif line.startswith("--- "):
            old_path = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else old_path
        elif m := HUNK.match(line):
            old, new = int(m[1]), int(m[2])
        elif path is None or not line or line[0] not in " +-":
            continue
        elif line[0] == " ":
            lines.setdefault((path, "LEFT"), {})[old] = line[1:]
            lines.setdefault((path, "RIGHT"), {})[new] = line[1:]
            old, new = old + 1, new + 1
        elif line[0] == "-":
            lines.setdefault((path, "LEFT"), {})[old] = line[1:]
            old += 1
        else:
            lines.setdefault((path, "RIGHT"), {})[new] = line[1:]
            new += 1
    return lines


def commented_code(repo: str, number: str, comments: list[Comment]) -> list[str]:
    """Return the code each comment points at, or exit if a comment points outside the PR diff."""
    diff = parse_diff(gh("pr", "diff", number, "-R", repo, "--color", "never"))
    code, errors = [], []
    for c in comments:
        known = diff.get((c.path, c.side), {})
        missing = [n for n in range(c.start, c.end + 1) if n not in known]
        if missing:
            errors.append(f"{c.location}: line {missing[0]} is not part of the PR diff, so GitHub cannot take a comment on it.")
        else:
            code.append("\n".join(known[n] for n in range(c.start, c.end + 1)))
    if errors:
        sys.exit("\n".join(errors))
    return code


def fenced(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def preview(args: argparse.Namespace) -> int:
    body, comments = parse_draft(Path(args.draft).read_text())
    code = commented_code(args.repo, args.number, comments)
    out = []
    if body:
        out.append(f"**Review comment**\n\n{body}")
    for i, (c, now) in enumerate(zip(comments, code), 1):
        out.append(f"**{i}. `{c.location}`**")
        out.append(f"Now:\n\n{fenced(now)}")
        for s in SUGGESTION.finditer(c.body):
            out.append(f"Suggested:\n\n{fenced(s['code'].rstrip(chr(10)))}")
        text = SUGGESTION.sub("", c.body).strip()
        if text:
            out.append("\n".join("> " + line if line else ">" for line in text.splitlines()))
    print("\n\n".join(out))
    return 0


def thread_input(c: Comment) -> dict:
    fields = {"path": c.path, "body": c.body, "line": c.end, "side": c.side}
    if c.start != c.end:
        fields |= {"start_line": c.start, "start_side": c.side}
    return fields


def create(args: argparse.Namespace) -> int:
    repo, number = args.repo, args.number
    body, comments = parse_draft(Path(args.draft).read_text())
    commented_code(repo, number, comments)

    # GitHub allows one pending review per user and PR, and shows it only to that user.
    reviews = json.loads(gh("api", f"repos/{repo}/pulls/{number}/reviews?per_page=100"))
    pending = next((r for r in reviews if r["state"] == "PENDING"), None)

    if pending is None:
        payload: dict[str, object] = {"comments": [thread_input(c) for c in comments]}
        if body:
            payload["body"] = body
        # Leaving out `event` keeps the review pending.
        review = json.loads(gh("api", "--method", "POST", f"repos/{repo}/pulls/{number}/reviews", "--input", "-", stdin=json.dumps(payload)))
    else:
        review = pending
        if body and normalize(pending.get("body") or "") not in ("", normalize(body)):
            sys.exit("Your pending review on this PR already has a review comment. Remove the text above the first `##` header from the draft, or edit the review comment on GitHub.")
        for c in comments:
            add_thread(pending["node_id"], c)
        if body and not pending.get("body"):
            gh("api", "--method", "PUT", f"repos/{repo}/pulls/{number}/reviews/{pending['id']}", "-f", f"body={body}")

    verify(repo, number, review["id"], comments)
    print(f"https://github.com/{repo}/pull/{number}/files")
    return 0


def add_thread(review_node_id: str, c: Comment) -> None:
    fields = thread_input(c)
    variables = {
        "reviewId": review_node_id,
        "path": fields["path"],
        "body": fields["body"],
        "line": fields["line"],
        "side": fields["side"],
        "startLine": fields.get("start_line"),
        "startSide": fields.get("start_side"),
    }
    query = """
mutation($reviewId: ID!, $path: String!, $body: String!, $line: Int!, $side: DiffSide, $startLine: Int, $startSide: DiffSide) {
  addPullRequestReviewThread(input: {pullRequestReviewId: $reviewId, path: $path, body: $body, line: $line, side: $side, startLine: $startLine, startSide: $startSide}) {
    thread { id }
  }
}"""
    result = json.loads(gh("api", "graphql", "--input", "-", stdin=json.dumps({"query": query, "variables": variables})))
    if result.get("errors") or not (result.get("data") or {}).get("addPullRequestReviewThread"):
        sys.exit(f"GitHub did not add the comment on {c.location}:\n{json.dumps(result.get('errors'), indent=2)}")


def verify(repo: str, number: str, review_id: int, comments: list[Comment]) -> None:
    live = json.loads(gh("api", f"repos/{repo}/pulls/{number}/reviews/{review_id}/comments?per_page=100"))
    found = {(x["path"], normalize(x["body"])) for x in live}
    missing = [c.location for c in comments if (c.path, normalize(c.body)) not in found]
    if missing:
        sys.exit("The pending review lacks the comments on: " + ", ".join(missing))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func, help_text in [
        ("preview", preview, "print each comment with the current code and the suggested code"),
        ("create", create, "add the draft's comments to your pending review on the PR"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("repo")
        p.add_argument("number")
        p.add_argument("draft")
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
