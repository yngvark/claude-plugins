#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.11"
# ///

"""Show what is open in a list of GitHub repositories, one section per repo.

    repo-watch.py [--config FILE] [--out DIR] [--no-open]

For each repo in the config, the page lists workflows whose latest run on the
default branch failed, open PRs by the configured authors, and all open
issues. It writes DIR/repo-watch.html, prints the path, and opens it.

The config is TOML, read from --config, $REPO_WATCH_CONFIG or
~/.config/my-skills/repo-watch.toml:

    title = "Platform"
    authors = ["alice", "bob"]
    repos = ["acme/platform", "acme/docs"]

All GitHub calls go through the `gh` CLI and only read.
"""

import argparse
import datetime as dt
import os
import sys
import tempfile
import tomllib
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).parent
SUMMARY_DIR = HERE.parent / "notification-summary"
ns = SourceFileLoader("notification_summary", str(SUMMARY_DIR / "notification-summary.py")).load_module()
e = ns.e

DEFAULT_CONFIG = Path.home() / ".config" / "my-skills" / "repo-watch.toml"
PER_PAGE = 100
MAX_PAGES = 5
ISSUES_SHOWN = 10
EXAMPLE_CONFIG = '''title = "Platform"
authors = ["alice", "bob"]
repos = ["acme/platform", "acme/docs"]'''


# ---------- config ----------


def load_config(path: Path) -> dict:
    """Read and check the TOML config. Raises ValueError with a readable message."""
    if not path.is_file():
        raise ValueError(f"no config at {path}. Create it like this:\n\n{EXAMPLE_CONFIG}")
    cfg = tomllib.loads(path.read_text())
    repos, authors = cfg.get("repos"), cfg.get("authors", [])
    if not repos or not all(isinstance(r, str) and r.count("/") == 1 for r in repos):
        raise ValueError(f"{path}: `repos` must be a list of \"owner/name\" strings")
    if not all(isinstance(a, str) for a in authors):
        raise ValueError(f"{path}: `authors` must be a list of GitHub logins")
    return {"title": cfg.get("title") or "Repo watch", "repos": repos, "authors": authors}


# ---------- fetch ----------


def failing_workflows(runs: list) -> list:
    """Latest completed run per workflow, kept only if it failed. `runs` is newest first."""
    latest = {}
    for r in runs:
        if r.get("status") == "completed" and r.get("workflow_id") not in latest:
            latest[r.get("workflow_id")] = r
    return [
        {"name": r.get("name"), "url": r.get("html_url"), "conclusion": r.get("conclusion"),
         "event": r.get("event"), "updated_at": r.get("updated_at") or r.get("created_at")}
        for r in latest.values() if r.get("conclusion") in ns.FAILED_CONCLUSIONS
    ]


def is_dependency_dashboard(issue: dict) -> bool:
    """Renovate keeps one Dependency Dashboard issue open per repo. It is never news."""
    author = (issue.get("user") or {}).get("login") or ""
    return issue.get("title") == "Dependency Dashboard" and author.endswith("[bot]")


class Fetcher:
    def __init__(self, get=ns.gh_get, workers=8):
        self.get = get
        self.workers = workers

    def pages(self, path: str) -> list:
        out = []
        for page in range(1, MAX_PAGES + 1):
            batch = self.get(f"{path}&per_page={PER_PAGE}&page={page}") or []
            out += batch
            if len(batch) < PER_PAGE:
                break
        return out

    def pr(self, repo: str, p: dict) -> dict:
        num = p["number"]
        d = self.get(f"repos/{repo}/pulls/{num}")
        reviews = self.get(f"repos/{repo}/pulls/{num}/reviews?per_page=100") or []
        checks = self.get(f"repos/{repo}/commits/{d['head']['sha']}/check-runs?per_page=100") or {}
        return {
            "type": "PullRequest", "state": "open", "number": num, "title": d.get("title"),
            "url": d.get("html_url"), "author": (d.get("user") or {}).get("login"), "draft": bool(d.get("draft")),
            "created_at": d.get("created_at"), "updated_at": d.get("updated_at"),
            "labels": [lb["name"] for lb in d.get("labels", [])],
            "comments": d.get("comments", 0) + d.get("review_comments", 0),
            "additions": d.get("additions"), "deletions": d.get("deletions"),
            "requested_reviewers": [u["login"] for u in d.get("requested_reviewers", [])],
            "review_state": ns.review_state(reviews), "ci": ns.ci_state(checks.get("check_runs", [])),
        }

    def repo(self, name: str, authors: set) -> dict:
        info = self.get(f"repos/{name}")
        branch = info.get("default_branch", "main")
        pulls = self.pages(f"repos/{name}/pulls?state=open")
        mine = [p for p in pulls if ((p.get("user") or {}).get("login") or "").lower() in authors]
        issues = [i for i in self.pages(f"repos/{name}/issues?state=open&sort=updated")
                  if "pull_request" not in i and not is_dependency_dashboard(i)]
        runs = self.get(f"repos/{name}/actions/runs?branch={branch}&per_page=100&exclude_pull_requests=true") or {}
        prs = sorted((self.pr(name, p) for p in mine), key=lambda p: p["updated_at"], reverse=True)
        return {
            "name": name, "url": info.get("html_url") or f"https://github.com/{name}", "default_branch": branch,
            "failing": failing_workflows(runs.get("workflow_runs", [])),
            "prs": prs,
            "issues": [
                {"type": "Issue", "state": "open", "number": i["number"], "title": i.get("title"),
                 "url": i.get("html_url"), "author": (i.get("user") or {}).get("login"),
                 "created_at": i.get("created_at"), "updated_at": i.get("updated_at"),
                 "labels": [lb["name"] for lb in i.get("labels", [])], "comments": i.get("comments", 0)}
                for i in issues
            ],
        }

    def safe_repo(self, name: str, authors: set) -> dict:
        try:
            return self.repo(name, authors)
        except (RuntimeError, KeyError, TypeError) as err:
            msg = str(err) or type(err).__name__
            if "HTTP 404" in msg:
                msg += ". GitHub answers 404 for a private repo when your gh token has no SSO authorization for its org."
            return {"name": name, "url": f"https://github.com/{name}", "error": msg}

    def fetch(self, cfg: dict, now: dt.datetime | None = None) -> dict:
        now = now or dt.datetime.now(dt.timezone.utc)
        authors = {a.lower() for a in cfg["authors"]}
        with ThreadPoolExecutor(self.workers) as ex:
            repos = list(ex.map(lambda r: self.safe_repo(r, authors), cfg["repos"]))
        return {
            "title": cfg["title"],
            "me": (self.get("user") or {}).get("login"),
            "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "authors": cfg["authors"],
            "repos": repos,
        }


# ---------- render ----------


def item_row(t: dict, me: str | None, now: dt.datetime) -> str:
    k, label = ns.kind(t)
    tags = ns.tags(t)
    if me and me in t.get("requested_reviewers", []):
        tags.insert(0, ("review requested from you", "you"))
    tag_html = "".join(f'<span class="tag {c}">{e(x)}</span>' for x, c in tags)
    meta = f"{ns.status_line(t, now)} · updated {ns.ago(t['updated_at'], now)}"
    return (
        f'<li class="row k-{k}"><span class="kind {k}">{label}</span>'
        f'<span class="title"><a href="{e(t["url"])}">{e(t["title"])}</a> <span class="repo">#{t["number"]}</span></span>'
        f'<span class="why">{e(meta)}</span>'
        + (f'<span class="tags">{tag_html}</span>' if tag_html else "")
        + "</li>"
    )


def workflow_row(w: dict, branch: str, now: dt.datetime) -> str:
    meta = f"{w['conclusion'].replace('_', ' ')} on {branch} · {w['event']} · {ns.ago(w['updated_at'], now)}"
    return (
        f'<li class="row k-wf"><span class="kind wf">Failing</span>'
        f'<span class="title"><a href="{e(w["url"])}">{e(w["name"])}</a></span><span class="why">{e(meta)}</span></li>'
    )


def repo_section(r: dict, me: str | None, now: dt.datetime) -> str:
    head = f'<h2><a href="{e(r["url"])}">{e(short_name(r))}</a>'
    counts = [(len(r["failing"]), "failing", ""), (len(r["prs"]), "team PR", "s"), (len(r["issues"]), "issue", "s")]
    small = " · ".join(f"{n} {label}{plural if n != 1 else ''}" for n, label, plural in counts if n)
    rows = [workflow_row(w, r["default_branch"], now) for w in r["failing"]]
    rows += [item_row(p, me, now) for p in r["prs"]]
    rows += [item_row(i, me, now) for i in r["issues"][:ISSUES_SHOWN]]
    more = len(r["issues"]) - ISSUES_SHOWN
    if more > 0:
        rows.append(f'<li class="row more"><a href="{e(r["url"])}/issues">{more} more open issues</a></li>')
    return f'<section class="watch">{head}<small>{e(small)}</small></h2><ul class="rows">{"".join(rows)}</ul></section>'


def short_name(r: dict) -> str:
    return r["name"].split("/", 1)[1]


def is_quiet(r: dict) -> bool:
    return not r.get("error") and not (r["failing"] or r["prs"] or r["issues"])


def render(data: dict, css: str) -> str:
    now = ns.parse_time(data["fetched_at"])
    repos = data["repos"]
    loaded = [r for r in repos if not r.get("error")]
    counts = [sum(len(r[k]) for r in loaded) for k in ("failing", "prs", "issues")]
    stats = "".join(
        f'<div class="stat s{i}"><b>{n}</b><span>{label}</span></div>'
        for i, (n, label) in enumerate(zip(counts, ["failing workflows", "team PRs", "open issues"]), 1)
    )
    body = [f'<div class="stats">{stats}</div>']
    body += [repo_section(r, data.get("me"), now) for r in loaded if not is_quiet(r)]
    quiet = [r for r in repos if is_quiet(r)]
    if quiet:
        links = ", ".join(f'<a href="{e(r["url"])}">{e(short_name(r))}</a>' for r in quiet)
        body.append(f'<p class="quiet">Nothing open in {links}.</p>')
    failed = [r for r in repos if r.get("error")]
    if failed:
        rows = "".join(f'<li><a href="{e(r["url"])}">{e(short_name(r))}</a>: {e(r["error"])}</li>' for r in failed)
        body.append(f'<details class="other errors"><summary>Could not load {len(failed)} '
                    f'repo{"s" if len(failed) != 1 else ""}</summary><ul>{rows}</ul></details>')
    local = now.astimezone()
    n = len(data["authors"])
    meta = f"{local:%d %b %Y, %H:%M} · {len(repos)} repos · PRs by {n} team member{'s' if n != 1 else ''}"
    return ns.page(data["title"], meta, "".join(body), css)


# ---------- cli ----------


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help=f"TOML config (default: $REPO_WATCH_CONFIG or {DEFAULT_CONFIG})")
    p.add_argument("--out", help="output directory (default: a new temp dir)")
    p.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    a = p.parse_args(argv)

    path = Path(a.config or os.environ.get("REPO_WATCH_CONFIG") or DEFAULT_CONFIG).expanduser()
    try:
        cfg = load_config(path)
    except (ValueError, tomllib.TOMLDecodeError) as err:
        print(err, file=sys.stderr)
        return 2
    try:
        data = Fetcher().fetch(cfg)
    except RuntimeError as err:
        print(err, file=sys.stderr)
        return 1
    css = (SUMMARY_DIR / "summary.css").read_text() + (HERE / "repo-watch.css").read_text()
    out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="repo-watch-"))
    out.mkdir(parents=True, exist_ok=True)
    page = out / "repo-watch.html"
    page.write_text(render(data, css))
    print(page)
    if not a.no_open:
        webbrowser.open(page.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
