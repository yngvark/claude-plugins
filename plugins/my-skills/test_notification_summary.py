#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import datetime as dt
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SKILL = Path(__file__).parent / "skills" / "notification-summary"
ns = SourceFileLoader("ns", str(SKILL / "notification-summary.py")).load_module()

NOW = dt.datetime(2026, 9, 23, 9, 0, tzinfo=dt.timezone.utc)


class TestParseQuery:
    def test_url_with_repeated_authors(self):
        q = ns.parse_query(
            "https://github.com/notifications?query=topic%3Aplatform+author%3Aalice+author%3Abob+author%3Aalice+"
        )
        assert q["topics"] == ["platform"]
        assert q["authors"] == ["alice", "bob"]

    def test_plus_separated_string(self):
        assert ns.parse_query("topic:x+author:a")["authors"] == ["a"]

    def test_reason_hyphen_becomes_underscore(self):
        assert ns.parse_query("reason:review-requested")["reasons"] == ["review_requested"]

    def test_is_terms(self):
        q = ns.parse_query("is:unread is:pr")
        assert q["unread_only"] and q["types"] == ["PullRequest"]

    def test_empty_query_matches_everything(self):
        q = ns.parse_query("")
        assert not any(q[k] for k in ("topics", "authors", "repos", "orgs", "reasons", "types"))

    @pytest.mark.parametrize("term", ["label:bug", "foo", "author:"])
    def test_unsupported_term_raises(self, term):
        with pytest.raises(ValueError):
            ns.parse_query(term)


class TestCiAndReviews:
    def test_ci_states(self):
        assert ns.ci_state([]) == "none"
        assert ns.ci_state([{"status": "completed", "conclusion": "success"}]) == "passing"
        assert ns.ci_state([{"status": "in_progress", "conclusion": None}]) == "pending"
        assert ns.ci_state([{"status": "in_progress"}, {"status": "completed", "conclusion": "failure"}]) == "failing"

    def test_latest_review_per_user_wins(self):
        reviews = [
            {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
            {"user": {"login": "a"}, "state": "APPROVED"},
            {"user": {"login": "b"}, "state": "COMMENTED"},
        ]
        assert ns.review_state(reviews) == "approved"

    def test_changes_requested_beats_approval(self):
        reviews = [{"user": {"login": "a"}, "state": "APPROVED"}, {"user": {"login": "b"}, "state": "CHANGES_REQUESTED"}]
        assert ns.review_state(reviews) == "changes_requested"


def notif(i, repo, typ, num, reason="subscribed", owner="org"):
    kind = "pulls" if typ == "PullRequest" else "issues"
    return {
        "id": str(i), "unread": True, "reason": reason, "updated_at": f"2026-09-2{i}T08:00:00Z", "last_read_at": None,
        "repository": {"full_name": f"{owner}/{repo}", "owner": {"login": owner}},
        "subject": {"type": typ, "title": f"t{i}", "url": f"https://api.github.com/repos/{owner}/{repo}/{kind}/{num}"},
    }


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.notifs = [
            notif(1, "infra", "PullRequest", 10, "review_requested"),
            notif(2, "infra", "Issue", 11),
            notif(3, "website", "Issue", 12),
            notif(4, "infra", "Issue", 13),
            {**notif(5, "infra", "Issue", 14), "subject": {"type": "CheckSuite", "title": "ci", "url": None}},
        ]
        self.authors = {10: "alice", 11: "bob", 12: "alice", 13: "renovate"}

    def __call__(self, path):
        self.calls.append(path)
        path = path.removeprefix(ns.API_PREFIX)
        if path.startswith("notifications"):
            return self.notifs if "page=1" in path else []
        if path == "user":
            return {"login": "me"}
        if path == "repos/org/infra":
            return {"topics": ["platform"]}
        if path == "repos/org/website":
            return {"topics": ["web"]}
        if "/comments" in path:
            return [{"user": {"login": "bob"}, "created_at": "2026-09-22T00:00:00Z", "body": "x" * 1000}]
        if "/reviews" in path:
            return [{"user": {"login": "bob"}, "state": "CHANGES_REQUESTED"}]
        if "/check-runs" in path:
            return {"check_runs": [{"status": "completed", "conclusion": "failure"}]}
        num = int(path.rsplit("/", 1)[1])
        d = {"number": num, "title": f"title {num}", "html_url": f"https://github.com/x/{num}", "state": "open",
             "user": {"login": self.authors[num]}, "created_at": "2026-09-20T00:00:00Z", "labels": [], "comments": 2,
             "body": "body"}
        if "/pulls/" in path:
            d.update({"head": {"sha": "abc"}, "additions": 5, "deletions": 1, "requested_reviewers": [{"login": "me"}],
                      "review_comments": 1, "merged_at": None, "draft": False})
        return d


class TestFetch:
    def test_filters_by_topic_and_author_and_enriches(self):
        gh = FakeGitHub()
        data = ns.Fetcher(get=gh, workers=1).fetch(ns.parse_query("topic:platform author:alice author:bob"), 7, NOW)
        assert data["me"] == "me"
        assert [t["number"] for t in data["threads"]] == [11, 10]  # newest first; website and renovate dropped
        pr = next(t for t in data["threads"] if t["number"] == 10)
        assert pr["ci"] == "failing"
        assert pr["review_state"] == "changes_requested"
        assert pr["requested_reviewers"] == ["me"]
        assert pr["comments"] == 3
        assert len(pr["recent_comments"][0]["body"]) == ns.COMMENT_LIMIT + 1
        assert "notifications?all=true&since=2026-09-16T09:00:00Z&per_page=50&page=1" in gh.calls

    def test_skips_topic_lookup_without_topic_filter(self):
        gh = FakeGitHub()
        ns.Fetcher(get=gh, workers=1).fetch(ns.parse_query("author:alice"), 7, NOW)
        assert "repos/org/infra" not in gh.calls

    def test_reason_filter(self):
        data = ns.Fetcher(get=FakeGitHub(), workers=1).fetch(ns.parse_query("reason:review-requested"), 7, NOW)
        assert [t["number"] for t in data["threads"]] == [10]

    def test_unread_only_asks_api_for_unread(self):
        gh = FakeGitHub()
        ns.Fetcher(get=gh, workers=1).fetch(ns.parse_query("is:unread"), 7, NOW)
        assert any(c.startswith("notifications?all=false") for c in gh.calls)


def thread(i, **kw):
    t = {"id": str(i), "repo": "org/infra", "type": "Issue", "number": i, "title": f"Title {i}",
         "url": f"https://github.com/org/infra/issues/{i}", "author": "alice", "state": "open", "draft": False,
         "created_at": "2026-09-20T00:00:00Z", "closed_at": None, "labels": [], "comments": 0,
         "updated_at": "2026-09-22T00:00:00Z"}
    t.update(kw)
    return t


DATA = {
    "me": "me", "fetched_at": "2026-09-23T09:00:00Z", "since": "2026-09-16T09:00:00Z",
    "query": ns.parse_query("topic:platform author:alice"),
    "threads": [
        thread(1, type="PullRequest", additions=4, deletions=2, ci="failing", review_state="changes_requested"),
        thread(2, state="merged", type="PullRequest", closed_at="2026-09-22T10:00:00Z"),
        thread(3, title="<script>alert(1)</script>"),
    ],
}
SUMMARY = {"title": "Team", "items": [
    {"id": "2", "section": "worth_reading", "summary": "Adds `ok pkg`."},
    {"id": "1", "section": "needs_you", "priority": 1, "reason": "Your PR is blocked", "summary": "Fix CI."},
    {"id": "999", "section": "needs_you", "summary": "unknown id is ignored"},
]}


class TestRender:
    html = ns.render(DATA, SUMMARY, "/*css*/")

    def test_sections_in_order(self):
        h = self.html
        assert h.index("Needs you") < h.index("Title 1") < h.index("Worth reading") < h.index("Title 2")

    def test_unplaced_threads_go_to_other(self):
        assert "1 other notifications" in self.html
        assert self.html.index("other notifications") < self.html.index("&lt;script&gt;")

    def test_escapes_and_renders_code(self):
        assert "<script>alert" not in self.html
        assert "<code>ok pkg</code>" in self.html

    def test_status_and_tags(self):
        h = self.html
        assert "<b>Your PR is blocked</b> · by alice · open 3 days" in h
        assert "merged yesterday" in h
        assert 'class="tag fail">CI failing' in h and "changes requested" in h and "+4 −2" in h

    def test_ignores_unknown_ids(self):
        assert "unknown id" not in self.html

    def test_stats(self):
        assert '<b>1</b><span>need you</span>' in self.html

    def test_empty(self):
        h = ns.render({**DATA, "threads": []}, {"items": []}, "")
        assert "No notifications match" in h


def test_cli_render(tmp_path):
    (tmp_path / "n.json").write_text(json.dumps(DATA))
    (tmp_path / "s.json").write_text(json.dumps(SUMMARY))
    assert ns.main(["render", str(tmp_path / "n.json"), str(tmp_path / "s.json")]) == 0
    out = (tmp_path / "notification-summary.html").read_text()
    assert "--bg: #ffffff" in out and "data-theme=dark" in out


def test_cli_rejects_bad_query(capsys):
    assert ns.main(["fetch", "label:bug"]) == 2
    assert "unsupported" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
