#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///

"""User stories for the repo-watch page, run against a fake GitHub."""

import datetime as dt
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SKILL = Path(__file__).parent / "skills" / "repo-watch"
rw = SourceFileLoader("rw", str(SKILL / "repo-watch.py")).load_module()

NOW = dt.datetime(2026, 9, 30, 9, 0, tzinfo=dt.timezone.utc)
CFG = {"title": "Platform", "authors": ["Alice", "bob"], "repos": ["acme/infra", "acme/docs", "acme/gone"]}


def pull(num, author, draft=False):
    return {"number": num, "user": {"login": author}, "draft": draft}


def run(wid, name, conclusion, created, status="completed"):
    return {"workflow_id": wid, "name": name, "status": status, "conclusion": conclusion, "event": "push",
            "html_url": f"https://github.com/acme/infra/actions/runs/{wid}{created}", "created_at": created,
            "updated_at": created}


class FakeGitHub:
    def __init__(self):
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        if path == "user":
            return {"login": "me"}
        if path == "repos/acme/gone":
            raise RuntimeError("HTTP 404: Not Found")
        if path in ("repos/acme/infra", "repos/acme/docs"):
            return {"default_branch": "trunk" if "infra" in path else "main",
                    "html_url": f"https://github.com/{path.removeprefix('repos/')}"}
        if path.startswith("repos/acme/infra/pulls?"):
            return [pull(1, "renovate[bot]"), pull(2, "alice"), pull(3, "bob", draft=True)] if path.endswith("&page=1") else []
        if path.startswith("repos/acme/infra/pulls/") and path.count("/") == 4:
            num = int(path.rsplit("/", 1)[1])
            return {"number": num, "title": f"PR {num} <b>", "html_url": f"https://github.com/acme/infra/pull/{num}",
                    "user": {"login": {2: "alice", 3: "bob"}[num]}, "draft": num == 3,
                    "created_at": "2026-09-27T00:00:00Z", "updated_at": f"2026-09-2{num}T00:00:00Z",
                    "labels": [], "comments": 1, "review_comments": 2, "additions": 10, "deletions": 3,
                    "requested_reviewers": [{"login": "me"}] if num == 2 else [], "head": {"sha": f"sha{num}"}}
        if "/reviews" in path:
            return [{"user": {"login": "carol"}, "state": "APPROVED"}]
        if "/check-runs" in path:
            return {"check_runs": [{"status": "completed", "conclusion": "success"}]}
        if path.startswith("repos/acme/infra/issues?"):
            if not path.endswith("&page=1"):
                return []
            return [
                {"number": 7, "title": "Bot issue", "user": {"login": "dependabot[bot]"}, "labels": [{"name": "bug"}],
                 "comments": 4, "created_at": "2026-09-01T00:00:00Z", "updated_at": "2026-09-29T00:00:00Z",
                 "html_url": "https://github.com/acme/infra/issues/7"},
                {"number": 8, "title": "Dependency Dashboard", "user": {"login": "renovate[bot]"}},
                {"number": 2, "title": "PR 2 as an issue", "pull_request": {}, "user": {"login": "alice"}},
            ]
        if path.startswith("repos/acme/infra/actions/runs?"):
            return {"workflow_runs": [
                run(10, "Deploy", None, "2026-09-30T08:00:00Z", status="in_progress"),
                run(10, "Deploy", "failure", "2026-09-29T08:00:00Z"),
                run(11, "Lint", "success", "2026-09-29T07:00:00Z"),
                run(11, "Lint", "failure", "2026-09-28T07:00:00Z"),
            ]}
        if path.startswith("repos/acme/docs/"):
            return {"workflow_runs": []} if "/actions/" in path else []
        raise AssertionError(f"unexpected call {path}")


@pytest.fixture(scope="module")
def data():
    return rw.Fetcher(get=FakeGitHub(), workers=1).fetch(CFG, NOW)


@pytest.fixture(scope="module")
def html(data):
    return rw.render(data, "")


def infra(data):
    return data["repos"][0]


class TestWhatThePageShows:
    def test_team_prs_show_and_dependency_bot_prs_do_not(self, data):
        assert [p["number"] for p in infra(data)["prs"]] == [3, 2]  # newest update first, renovate dropped

    def test_author_names_match_regardless_of_case(self, data):
        assert "alice" in [p["author"] for p in infra(data)["prs"]]

    def test_every_open_issue_shows_whoever_opened_it(self, data):
        assert [i["number"] for i in infra(data)["issues"]] == [7]

    def test_a_workflow_whose_latest_run_on_the_default_branch_failed_shows(self, data):
        assert [w["name"] for w in infra(data)["failing"]] == ["Deploy"]

    def test_a_workflow_that_failed_before_but_passes_now_does_not_show(self, data):
        assert "Lint" not in [w["name"] for w in infra(data)["failing"]]

    def test_workflow_runs_come_from_the_default_branch(self):
        gh = FakeGitHub()
        rw.Fetcher(get=gh, workers=1).fetch(CFG, NOW)
        assert any(c.startswith("repos/acme/infra/actions/runs?branch=trunk&") for c in gh.calls)

    def test_pr_rows_show_ci_review_size_and_draft(self, html):
        assert 'class="kind pr">Draft' in html
        assert "CI passing" in html and "approved" in html and "+10 −3" in html
        assert "by alice · open 3 days · 3 comments · updated 8 days ago" in html

    def test_repo_heading_counts_what_is_open(self, html):
        assert "<small>1 failing · 2 team PRs · 1 issue</small>" in html

    def test_a_pr_waiting_on_my_review_says_so(self, html):
        assert html.count("review requested from you") == 1

    def test_repos_come_in_config_order(self, data):
        assert [r["name"] for r in data["repos"]] == CFG["repos"]

    def test_renovates_dependency_dashboard_issue_is_hidden(self, html):
        assert "Dependency Dashboard" not in html

    def test_stats_count_everything(self, html):
        assert "<b>1</b><span>failing workflows</span>" in html
        assert "<b>2</b><span>team PRs</span>" in html
        assert "<b>1</b><span>open issues</span>" in html


class TestEdgeCases:
    def test_repos_that_cannot_load_are_listed_at_the_bottom_and_the_rest_still_renders(self, html):
        assert "<summary>Could not load 1 repo</summary>" in html
        assert ">gone</a>: HTTP 404: Not Found. GitHub answers 404 for a private repo" in html
        assert html.index(">infra</a>") < html.index("Could not load")

    def test_a_repo_with_nothing_open_goes_on_the_quiet_line(self, html):
        assert 'Nothing open in <a href="https://github.com/acme/docs">docs</a>.' in html
        assert "<h2><a href=\"https://github.com/acme/docs\">" not in html

    def test_titles_are_escaped(self, html):
        assert "PR 2 &lt;b&gt;" in html and "PR 2 <b>" not in html

    def test_long_issue_lists_end_with_a_link_to_the_rest(self, data):
        r = {**infra(data), "issues": infra(data)["issues"] * 13}
        h = rw.render({**data, "repos": [r]}, "")
        assert h.count('class="row k-issue"') == rw.ISSUES_SHOWN
        assert '<a href="https://github.com/acme/infra/issues">3 more open issues</a>' in h

    def test_pagination_stops_on_a_short_page(self):
        calls = []

        def get(path):
            calls.append(path)
            return [{}] * (rw.PER_PAGE if path.endswith("&page=1") else 1)

        assert len(rw.Fetcher(get=get).pages("x?a=1")) == rw.PER_PAGE + 1
        assert calls == ["x?a=1&per_page=100&page=1", "x?a=1&per_page=100&page=2"]


class TestConfig:
    def test_missing_config_explains_how_to_create_it(self, tmp_path, capsys):
        assert rw.main(["--config", str(tmp_path / "nope.toml"), "--no-open"]) == 2
        err = capsys.readouterr().err
        assert "no config at" in err and 'repos = ["acme/platform", "acme/docs"]' in err

    @pytest.mark.parametrize("body", ['repos = ["no-slash"]', "repos = []", 'repos = ["a/b"]\nauthors = [1]'])
    def test_bad_config_is_rejected(self, tmp_path, capsys, body):
        (tmp_path / "c.toml").write_text(body)
        assert rw.main(["--config", str(tmp_path / "c.toml"), "--no-open"]) == 2
        assert capsys.readouterr().err

    def test_config_path_from_env(self, tmp_path, monkeypatch):
        (tmp_path / "c.toml").write_text('title = "X"\nauthors = ["a"]\nrepos = ["o/r"]')
        monkeypatch.setenv("REPO_WATCH_CONFIG", str(tmp_path / "c.toml"))
        monkeypatch.setattr(rw.Fetcher, "fetch", lambda self, cfg: {
            "title": cfg["title"], "me": "me", "fetched_at": "2026-09-30T09:00:00Z", "authors": cfg["authors"],
            "repos": []})
        assert rw.main(["--out", str(tmp_path), "--no-open"]) == 0
        page = (tmp_path / "repo-watch.html").read_text()
        assert "<title>X</title>" in page and ".watch" in page and "--bg: #ffffff" in page


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
