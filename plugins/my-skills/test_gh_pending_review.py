#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "skills" / "gh-pending-review" / "pending-review.py"
pr = SourceFileLoader("pr", str(SCRIPT)).load_module()

DIFF = """\
diff --git a/config.tf b/config.tf
index 1111111..2222222 100644
--- a/config.tf
+++ b/config.tf
@@ -8,4 +8,5 @@ locals {
   name = "app"
-  extra = {}
+  extra_parameters = {
+    Foo = "bar"
   }
   tags = {}
diff --git a/README.md b/README.md
new file mode 100644
--- /dev/null
+++ b/README.md
@@ -0,0 +1,2 @@
+# App
+Uses ```code``` here.
"""

# Stands in for `gh`. It keeps reviews in a JSON file and answers the calls pending-review.py makes.
FAKE_GH = """
import json, os, sys

state_path = os.environ["FAKE_GH_STATE"]
with open(state_path) as f:
    state = json.load(f)
args = sys.argv[1:]

def save():
    with open(state_path, "w") as f:
        json.dump(state, f)

def next_node_id():
    state["comment_count"] = state.get("comment_count", 0) + 1
    return f"C{state['comment_count']}"

if args[:2] == ["pr", "diff"]:
    print(state["diff"], end="")
elif args[:2] == ["api", "graphql"] and "updatePullRequestReviewComment" in (request := json.load(sys.stdin))["query"]:
    v = request["variables"]
    comment = next(c for r in state["reviews"] for c in r["comments"] if c["node_id"] == v["id"])
    comment["body"] = v["body"]
    save()
    print(json.dumps({"data": {"updatePullRequestReviewComment": {"pullRequestReviewComment": {"id": v["id"]}}}}))
elif args[:2] == ["api", "graphql"] and "reviewThreads" in request["query"]:
    threads = [
        {"path": c["path"], "line": c["line"], "diffSide": c["side"],
         "comments": {"nodes": [{"id": c["node_id"], "body": c["body"], "pullRequestReview": {"id": r["node_id"]}}]}}
        for r in state["reviews"] for c in r["comments"]
    ]
    print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": threads}}}}}))
elif args[:2] == ["api", "graphql"]:
    v = request["variables"]
    review = next(r for r in state["reviews"] if r["node_id"] == v["reviewId"])
    c = {"node_id": next_node_id(), "path": v["path"], "body": v["body"].replace("\\n", "\\r\\n"), "line": v["line"], "side": v["side"]}
    if v["startLine"] is not None:
        c |= {"start_line": v["startLine"], "start_side": v["startSide"]}
    review["comments"].append(c)
    save()
    print(json.dumps({"data": {"addPullRequestReviewThread": {"thread": {"id": "T1"}}}}))
elif args[:3] == ["api", "--method", "POST"]:
    payload = json.load(sys.stdin)
    state["posted"] = payload
    review_id = len(state["reviews"]) + 1
    review = {"id": review_id, "node_id": f"R{review_id}", "state": "COMMENTED" if "event" in payload else "PENDING",
              "body": payload.get("body", ""), "comments": [{"node_id": next_node_id(), **c} for c in payload["comments"]]}
    state["reviews"].append(review)
    save()
    print(json.dumps({k: v for k, v in review.items() if k != "comments"}))
elif args[:3] == ["api", "--method", "PUT"]:
    review_id = int(args[3].rsplit("/", 1)[1])
    next(r for r in state["reviews"] if r["id"] == review_id)["body"] = args[5].split("=", 1)[1]
    save()
    print("{}")
elif args[0] == "api" and "/comments" in args[1]:
    review_id = int(args[1].split("/reviews/")[1].split("/")[0])
    comments = next(r for r in state["reviews"] if r["id"] == review_id)["comments"]
    print(json.dumps([{"path": c["path"], "body": c["body"]} for c in comments]))
elif args[0] == "api" and "/reviews" in args[1]:
    print(json.dumps([{k: v for k, v in r.items() if k != "comments"} for r in state["reviews"]]))
else:
    sys.exit("unexpected gh call: " + " ".join(args))
"""


@pytest.fixture
def github(tmp_path, monkeypatch):
    fake = tmp_path / "gh"
    fake.write_text(f"#!{sys.executable}\n{FAKE_GH}")
    fake.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"diff": DIFF, "reviews": []}))
    monkeypatch.setenv("PENDING_REVIEW_GH", str(fake))
    monkeypatch.setenv("FAKE_GH_STATE", str(state))

    class GitHub:
        def state(self):
            return json.loads(state.read_text())

        def add_review(self, **review):
            s = self.state()
            s["reviews"].append({"comments": [], "body": "", **review})
            state.write_text(json.dumps(s))

    return GitHub()


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=os.environ)


DRAFT = """\
Ser bra ut.

## config.tf:10
Use `additional`, like the other templates:

```suggestion
  additional_parameters = {
```

## config.tf:9 (old)
Why was this removed?

## README.md:1-2
Shorter, please.
"""


def write_draft(tmp_path, text=DRAFT):
    draft = tmp_path / "review.md"
    draft.write_text(text)
    return draft


def test_parse_draft_reads_body_ranges_and_sides():
    body, comments = pr.parse_draft(DRAFT)

    assert body == "Ser bra ut."
    assert [(c.path, c.start, c.end, c.side) for c in comments] == [
        ("config.tf", 10, 10, "RIGHT"),
        ("config.tf", 9, 9, "LEFT"),
        ("README.md", 1, 2, "RIGHT"),
    ]
    assert comments[0].body.startswith("Use `additional`")
    assert comments[0].body.endswith("```")


def test_parse_diff_maps_both_sides():
    lines = pr.parse_diff(DIFF)

    assert lines[("config.tf", "RIGHT")] == {
        8: '  name = "app"', 9: "  extra_parameters = {", 10: '    Foo = "bar"', 11: "  }", 12: "  tags = {}"
    }
    assert lines[("config.tf", "LEFT")] == {8: '  name = "app"', 9: "  extra = {}", 10: "  }", 11: "  tags = {}"}
    assert lines[("README.md", "RIGHT")] == {1: "# App", 2: "Uses ```code``` here."}
    assert ("README.md", "LEFT") not in lines


@pytest.mark.usefixtures("github")
def test_preview_shows_current_and_suggested_code(tmp_path):
    result = run("preview", "o/r", "7", str(write_draft(tmp_path)))

    assert result.returncode == 0, result.stderr
    assert result.stdout == """\
**Review comment**

Ser bra ut.

**1. `config.tf:10`**

Now:

```
    Foo = "bar"
```

Suggested:

```
  additional_parameters = {
```

> Use `additional`, like the other templates:

**2. `config.tf:9 (old)`**

Now:

```
  extra = {}
```

> Why was this removed?

**3. `README.md:1-2`**

Now:

````
# App
Uses ```code``` here.
````

> Shorter, please.
"""


@pytest.mark.usefixtures("github")
def test_preview_rejects_lines_outside_the_diff(tmp_path):
    draft = write_draft(tmp_path, "## config.tf:2\nHmm.\n\n## README.md:2-3\nHmm.\n")

    result = run("preview", "o/r", "7", str(draft))

    assert result.returncode == 1
    assert "config.tf:2: line 2 is not part of the PR diff" in result.stderr
    assert "README.md:2-3: line 3 is not part of the PR diff" in result.stderr


def test_create_starts_a_pending_review(tmp_path, github):
    result = run("create", "o/r", "7", str(write_draft(tmp_path)))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://github.com/o/r/pull/7/files"
    posted = github.state()["posted"]
    assert "event" not in posted
    assert posted["body"] == "Ser bra ut."
    assert [{k: v for k, v in c.items() if k != "body"} for c in posted["comments"]] == [
        {"path": "config.tf", "line": 10, "side": "RIGHT"},
        {"path": "config.tf", "line": 9, "side": "LEFT"},
        {"path": "README.md", "line": 2, "side": "RIGHT", "start_line": 1, "start_side": "RIGHT"},
    ]
    assert github.state()["reviews"][0]["state"] == "PENDING"


def test_create_adds_to_an_existing_pending_review(tmp_path, github):
    github.add_review(id=1, node_id="R1", state="COMMENTED")
    github.add_review(id=2, node_id="R2", state="PENDING")

    result = run("create", "o/r", "7", str(write_draft(tmp_path)))

    assert result.returncode == 0, result.stderr
    assert "posted" not in github.state()
    review = github.state()["reviews"][1]
    assert review["body"] == "Ser bra ut."
    assert [(c["path"], c["line"], c.get("start_line")) for c in review["comments"]] == [
        ("config.tf", 10, None),
        ("config.tf", 9, None),
        ("README.md", 2, 1),
    ]


def test_create_keeps_an_existing_review_comment(tmp_path, github):
    github.add_review(id=1, node_id="R1", state="PENDING", body="Already written.")

    result = run("create", "o/r", "7", str(write_draft(tmp_path)))

    assert result.returncode == 1
    assert "already has a review comment" in result.stderr
    assert github.state()["reviews"][0]["comments"] == []


def test_create_adds_nothing_when_a_line_is_outside_the_diff(tmp_path, github):
    result = run("create", "o/r", "7", str(write_draft(tmp_path, "## config.tf:10\nOk.\n\n## config.tf:1\nHmm.\n")))

    assert result.returncode == 1
    assert github.state()["reviews"] == []


def test_edit_replaces_only_the_comments_in_the_draft(tmp_path, github):
    run("create", "o/r", "7", str(write_draft(tmp_path)))
    draft = write_draft(tmp_path, "## config.tf:9 (old)\nWhy was [this](https://example.com) removed?\n")

    result = run("edit", "o/r", "7", str(draft))

    assert result.returncode == 0, result.stderr
    assert [pr.normalize(c["body"]) for c in github.state()["reviews"][0]["comments"]] == [
        pr.normalize(DRAFT.split("## config.tf:10\n")[1].split("## config.tf:9")[0]),
        "Why was [this](https://example.com) removed?",
        "Shorter, please.",
    ]


def test_edit_needs_a_comment_on_the_same_line(tmp_path, github):
    run("create", "o/r", "7", str(write_draft(tmp_path)))

    result = run("edit", "o/r", "7", str(write_draft(tmp_path, "## config.tf:11\nNew.\n")))

    assert result.returncode == 1
    assert "Found 0 pending comments on config.tf:11" in result.stderr


@pytest.mark.usefixtures("github")
def test_edit_without_a_pending_review_fails(tmp_path):
    result = run("edit", "o/r", "7", str(write_draft(tmp_path)))

    assert result.returncode == 1
    assert "no pending review" in result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
