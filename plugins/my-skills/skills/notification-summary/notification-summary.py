#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

"""Fetch and render a summary of GitHub notifications.

Claude does the judgement (which threads matter, what they say). This script
does the deterministic parts:

    fetch [QUERY] [--days N] [--out DIR]
        Fetch notifications matching QUERY, enrich each issue/PR thread with
        author, state, CI, reviews and recent comments, and write
        DIR/notifications.json. Prints the path. QUERY is a GitHub
        notifications URL or its query string, e.g.
        "topic:foo author:alice author:bob".

    render NOTIFICATIONS_JSON SUMMARY_JSON [--out FILE] [--no-open]
        Merge Claude's summary (highlights, sections, priorities, one-line
        reasons and summaries) with the fetched facts and write an HTML page.
        Prints the path and opens the page in the default browser. The page builds a `gh` command that marks the ticked threads
        as done.

    done ID [ID ...]
        Mark notification threads as done, so the next fetch leaves them out.
        GitHub shows a done thread again when it gets new activity.

All GitHub calls go through the `gh` CLI. Only `done` changes anything.
GitHub's notifications API rejects fine-grained tokens. When
GITHUB_NOTIFICATIONS_TOKEN is set, the notification calls use it (a classic
token with the `notifications` scope), and every other call uses gh's default
auth.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

API_PREFIX = "https://api.github.com/"
NOTIFICATIONS_TOKEN_VAR = "GITHUB_NOTIFICATIONS_TOKEN"
BODY_LIMIT = 1500
COMMENT_LIMIT = 600
RECENT_COMMENTS = 8
SECTIONS = [
    ("needs_you", "Needs you", "review requested, mentioned, assigned, or your PR is blocked"),
    ("worth_reading", "Worth reading", "active discussion or decisions"),
]
FAILED_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}


# ---------- query ----------


def parse_query(raw: str) -> dict:
    """Parse a GitHub notifications URL or query string into filters."""
    raw = raw.strip()
    if raw.startswith("http"):
        raw = parse_qs(urlparse(raw).query).get("query", [""])[0]
    elif " " not in raw and "+" in raw:
        raw = raw.replace("+", " ")
    q = {"topics": [], "authors": [], "repos": [], "orgs": [], "reasons": [], "types": [], "unread_only": False}
    keys = {"topic": "topics", "author": "authors", "repo": "repos", "org": "orgs", "reason": "reasons"}
    for tok in raw.split():
        key, sep, val = tok.partition(":")
        if not sep or not val:
            raise ValueError(f"unsupported query term: {tok!r}")
        key = key.lower()
        if key in keys:
            if key == "reason":
                val = val.replace("-", "_")
            target = q[keys[key]]
            if val.lower() not in (v.lower() for v in target):
                target.append(val)
        elif key == "is" and val in ("unread", "read"):
            q["unread_only"] = val == "unread"
        elif key == "is" and val in ("pr", "issue"):
            q["types"].append({"pr": "PullRequest", "issue": "Issue"}[val])
        else:
            raise ValueError(f"unsupported query term: {tok!r}")
    return q


# ---------- fetch ----------


def gh_env(path: str, environ=os.environ) -> dict | None:
    """The environment for a gh call on PATH: GITHUB_NOTIFICATIONS_TOKEN as
    GH_TOKEN (which gh prefers over GITHUB_TOKEN) for notification endpoints,
    otherwise None to inherit ours unchanged."""
    token = environ.get(NOTIFICATIONS_TOKEN_VAR)
    if token and path.startswith("notifications"):
        return {**environ, "GH_TOKEN": token}
    return None


def gh_error(path: str, stderr: str) -> str:
    msg = stderr.strip()
    if path.startswith("notifications") and "403" in msg and not os.environ.get(NOTIFICATIONS_TOKEN_VAR):
        msg += (f"\nGitHub's notifications API rejects fine-grained tokens. Set {NOTIFICATIONS_TOKEN_VAR}"
                " to a classic token with the `notifications` scope.")
    return msg


def gh_get(path: str):
    """GET one GitHub API path through the gh CLI and return parsed JSON."""
    path = path.removeprefix(API_PREFIX)
    res = subprocess.run(["gh", "api", "--method", "GET", path], capture_output=True, text=True, env=gh_env(path))
    if res.returncode != 0:
        raise RuntimeError(f"GET {path} failed: {gh_error(path, res.stderr)}")
    return json.loads(res.stdout or "null")


def gh_delete(path: str) -> None:
    """DELETE one GitHub API path through the gh CLI."""
    res = subprocess.run(["gh", "api", "--method", "DELETE", path], capture_output=True, text=True, env=gh_env(path))
    if res.returncode != 0:
        raise RuntimeError(gh_error(path, res.stderr))


def bare_thread(n: dict) -> dict:
    """A thread from the notification alone, for when its issue or PR is unreadable."""
    s = n["subject"]
    repo = n["repository"]["full_name"]
    num = int(s["url"].rstrip("/").rsplit("/", 1)[1])
    path = "pull" if s["type"] == "PullRequest" else "issues"
    return {
        "id": n["id"],
        "enriched": False,
        "unread": n.get("unread", False),
        "reason": n.get("reason"),
        "updated_at": n["updated_at"],
        "last_read_at": n.get("last_read_at"),
        "repo": repo,
        "type": s["type"],
        "number": num,
        "title": s["title"],
        "url": f"https://github.com/{repo}/{path}/{num}",
        "author": None,
        "state": "open",
        "draft": False,
        "labels": [],
        "comments": 0,
        "body": "",
        "recent_comments": [],
    }


def ci_state(check_runs: list) -> str:
    if not check_runs:
        return "none"
    if any(r.get("conclusion") in FAILED_CONCLUSIONS for r in check_runs):
        return "failing"
    if any(r.get("status") != "completed" for r in check_runs):
        return "pending"
    return "passing"


def review_state(reviews: list) -> str:
    """The decisive state across reviewers: changes_requested beats approved."""
    latest = {}
    for r in reviews:
        if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[(r.get("user") or {}).get("login")] = r["state"]
    states = set(latest.values())
    if "CHANGES_REQUESTED" in states:
        return "changes_requested"
    if "APPROVED" in states:
        return "approved"
    return "none"


def clip(text, limit):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


class Fetcher:
    def __init__(self, get=gh_get, workers=8):
        self.get = get
        self.workers = workers
        self._repos = {}

    def notifications(self, since: str, unread_only: bool) -> list:
        out, page = [], 1
        while True:
            batch = self.get(
                f"notifications?all={'false' if unread_only else 'true'}&since={since}&per_page=50&page={page}"
            )
            out += batch
            if len(batch) < 50:
                return out
            page += 1

    def repo(self, full_name: str) -> dict:
        """The repo, or {} when the token cannot read it."""
        if full_name not in self._repos:
            try:
                self._repos[full_name] = self.get(f"repos/{full_name}")
            except RuntimeError:
                self._repos[full_name] = {}
        return self._repos[full_name]

    def enrich(self, n: dict) -> dict:
        """The thread with its issue or PR details. A fine-grained token reads
        only its owner's repos, so a thread it cannot read keeps just what the
        notification carries, marked "enriched": false."""
        try:
            return self.details(n)
        except RuntimeError:
            return bare_thread(n)

    def details(self, n: dict) -> dict:
        s = n["subject"]
        repo = n["repository"]["full_name"]
        d = self.get(s["url"])
        is_pr = s["type"] == "PullRequest"
        state = d.get("state", "open")
        if is_pr and d.get("merged_at"):
            state = "merged"
        num = d.get("number")
        since = n.get("last_read_at") or n["updated_at"]
        comments = self.get(f"repos/{repo}/issues/{num}/comments?since={since}&per_page=100") or []
        t = {
            "id": n["id"],
            "enriched": True,
            "unread": n.get("unread", False),
            "reason": n.get("reason"),
            "updated_at": n["updated_at"],
            "last_read_at": n.get("last_read_at"),
            "repo": repo,
            "type": s["type"],
            "number": num,
            "title": d.get("title") or s["title"],
            "url": d.get("html_url"),
            "author": (d.get("user") or {}).get("login"),
            "state": state,
            "draft": bool(d.get("draft")),
            "created_at": d.get("created_at"),
            "closed_at": d.get("closed_at"),
            "labels": [lb["name"] for lb in d.get("labels", [])],
            "comments": d.get("comments", 0) + d.get("review_comments", 0),
            "body": clip(d.get("body"), BODY_LIMIT),
            "recent_comments": [
                {"user": (c.get("user") or {}).get("login"), "created_at": c.get("created_at"),
                 "body": clip(c.get("body"), COMMENT_LIMIT)}
                for c in comments[-RECENT_COMMENTS:]
            ],
        }
        if is_pr:
            reviews = self.get(f"repos/{repo}/pulls/{num}/reviews?per_page=100") or []
            checks = self.get(f"repos/{repo}/commits/{d['head']['sha']}/check-runs?per_page=100") or {}
            t.update({
                "additions": d.get("additions"),
                "deletions": d.get("deletions"),
                "requested_reviewers": [u["login"] for u in d.get("requested_reviewers", [])],
                "review_state": review_state(reviews),
                "ci": ci_state(checks.get("check_runs", [])),
            })
        return t

    def fetch(self, q: dict, days: int, now: dt.datetime | None = None) -> dict:
        now = now or dt.datetime.now(dt.timezone.utc)
        since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw = self.notifications(since, q["unread_only"])
        types = q["types"] or ["Issue", "PullRequest"]
        kept = [n for n in raw if n["subject"]["type"] in types and n["subject"].get("url")]
        if q["repos"]:
            wanted = {r.lower() for r in q["repos"]}
            kept = [n for n in kept if n["repository"]["full_name"].lower() in wanted]
        if q["orgs"]:
            wanted = {o.lower() for o in q["orgs"]}
            kept = [n for n in kept if n["repository"]["owner"]["login"].lower() in wanted]
        if q["reasons"]:
            kept = [n for n in kept if n["reason"] in q["reasons"]]
        if q["topics"]:
            wanted = {t.lower() for t in q["topics"]}
            names = sorted({n["repository"]["full_name"] for n in kept})
            with ThreadPoolExecutor(self.workers) as ex:
                topics = dict(zip(names, ex.map(lambda r: self.repo(r).get("topics", []), names)))
            kept = [n for n in kept if wanted & {t.lower() for t in topics[n["repository"]["full_name"]]}]
        with ThreadPoolExecutor(self.workers) as ex:
            threads = list(ex.map(self.enrich, kept))
        if q["authors"]:
            wanted = {a.lower() for a in q["authors"]}
            # An unreadable thread has no known author, so it stays rather than vanish.
            threads = [t for t in threads if not t["enriched"] or (t["author"] or "").lower() in wanted]
        threads.sort(key=lambda t: t["updated_at"], reverse=True)
        return {
            "me": (self.get("user") or {}).get("login"),
            "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "since": since,
            "query": q,
            "threads": threads,
        }


# ---------- render ----------


def e(text) -> str:
    """Escape text for HTML and turn `backticks` into <code>."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(str(text or "")))


def e_links(text) -> str:
    """Like e(), and also turn [text](https://...) into links."""
    return re.sub(r"\[([^\]]+)\]\((https?://[^\s)\"]+)\)", r'<a href="\2">\1</a>', e(text))


def highlights(items: list) -> str:
    rows = []
    for h in items:
        if h.get("text"):
            label = f"<b>{e(h['label'])}:</b> " if h.get("label") else ""
            rows.append(f"<li>{label}{e_links(h['text'])}</li>")
    return f'<ul class="highlights">{"".join(rows)}</ul>' if rows else ""


def kind(t: dict) -> tuple[str, str]:
    if t["state"] == "merged":
        return "merged", "Merged"
    if t["state"] == "closed":
        return "closed", "Closed"
    if t["type"] == "PullRequest":
        return "pr", "Draft" if t.get("draft") else "PR"
    return "issue", "Issue"


def parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def ago(start: str, now: dt.datetime) -> str:
    days = (now.date() - parse_time(start).date()).days
    return "today" if days <= 0 else "yesterday" if days == 1 else f"{days} days ago"


def status_line(t: dict, now: dt.datetime) -> str:
    if not t.get("enriched", True):
        return f"updated {ago(t['updated_at'], now)} · details not readable with this token"
    parts = [f"by {t['author']}"]
    if t["state"] == "merged":
        parts.append(f"merged {ago(t['closed_at'], now)}")
    elif t["state"] == "closed":
        parts.append(f"closed {ago(t['closed_at'], now)}")
    else:
        days = (now.date() - parse_time(t["created_at"]).date()).days
        parts.append("opened today" if days <= 0 else f"open {days} day{'s' if days != 1 else ''}")
    if t["comments"]:
        parts.append(f"{t['comments']} comment{'s' if t['comments'] != 1 else ''}")
    return " · ".join(parts)


def tags(t: dict) -> list[tuple[str, str]]:
    out = []
    if t["type"] == "PullRequest":
        if t.get("additions") is not None:
            out.append((f"+{t['additions']} −{t['deletions']}", ""))
        ci = t.get("ci")
        if ci == "failing":
            out.append(("CI failing", "fail"))
        elif ci == "passing":
            out.append(("CI passing", "ok"))
        elif ci == "pending":
            out.append(("CI running", ""))
        if t.get("review_state") == "changes_requested":
            out.append(("changes requested", "fail"))
        elif t.get("review_state") == "approved":
            out.append(("approved", "ok"))
    out += [(lb, "") for lb in t.get("labels", [])[:3]]
    return out


def card(t: dict, s: dict, now: dt.datetime) -> str:
    k, label = kind(t)
    pri = s.get("priority") or 0
    lead = f"<b>{e(s['reason'])}</b> · " if s.get("reason") else ""
    tag_html = "".join(f'<span class="tag {c}">{e(x)}</span>' for x, c in tags(t))
    return (
        f'<article class="item p{pri} k-{k}">'
        f'<div class="top">{done_box(t)}<span class="kind {k}">{label}</span><a href="{e(t["url"])}">{e(t["title"])}</a>'
        f'<span class="repo">{e(t["repo"])} #{t["number"]}</span></div>'
        f'<p class="why">{lead}{e(status_line(t, now))}</p>'
        f'<p class="sum">{e(s.get("summary"))}</p>'
        + (f'<div class="tags">{tag_html}</div>' if tag_html else "")
        + "</article>"
    )


def done_box(t: dict) -> str:
    return f'<input type="checkbox" class="done" data-id="{e(t["id"])}" title="Mark as done" aria-label="Mark as done">'


# Shows a gh command that marks the ticked threads as done, in the bottom panel.
DONE_SCRIPT = """
const boxes = [...document.querySelectorAll('input.done')];
const bar = document.getElementById('donebar'), cmd = document.getElementById('donecmd');
const del = id => 'gh api --silent --method DELETE notifications/threads/' + id;
function update() {
  const ids = [...new Set(boxes.filter(b => b.checked).map(b => b.dataset.id))].filter(id => /^\\d+$/.test(id));
  bar.hidden = !ids.length;
  cmd.value = ids.length === 1 ? del(ids[0]) : `for id in ${ids.join(' ')}; do ${del('$id')}; done`;
  document.getElementById('donecount').textContent = ids.length;
}
boxes.forEach(b => b.addEventListener('change', update));
document.getElementById('donecopy').addEventListener('click', async e => {
  cmd.select();
  try { await navigator.clipboard.writeText(cmd.value); e.target.textContent = 'Copied'; }
  catch { e.target.textContent = 'Press ⌘C'; }
  setTimeout(() => e.target.textContent = 'Copy', 1500);
});
update();
"""


def describe_query(q: dict) -> str:
    parts = [f"topic:{t}" for t in q["topics"]] + [f"repo:{r}" for r in q["repos"]]
    parts += [f"org:{o}" for o in q["orgs"]] + [f"reason:{r}" for r in q["reasons"]]
    if q["authors"]:
        parts.append(f"{len(q['authors'])} authors" if len(q["authors"]) > 3 else "authors " + ", ".join(q["authors"]))
    return ", ".join(parts) or "all notifications"


def render(data: dict, summary: dict, css: str) -> str:
    now = parse_time(data["fetched_at"])
    by_id = {t["id"]: t for t in data["threads"]}
    placed = {key: [] for key, _, _ in SECTIONS}
    for s in summary.get("items", []):
        t = by_id.get(str(s.get("id")))
        if t and s.get("section") in placed:
            placed[s["section"]].append((t, s))
    for items in placed.values():
        items.sort(key=lambda ts: ts[1].get("priority") or 9)
    used = {t["id"] for items in placed.values() for t, _ in items}
    other = sorted((t for t in data["threads"] if t["id"] not in used), key=lambda t: t["updated_at"], reverse=True)

    counts = [len(placed["needs_you"]), len(placed["worth_reading"]), len(other)]
    stats = "".join(
        f'<div class="stat s{i}"><b>{n}</b><span>{label}</span></div>'
        for i, (n, label) in enumerate(zip(counts, ["need you", "worth reading", "other"]), 1)
    )
    body = [f'<div class="stats">{stats}</div>', highlights(summary.get("highlights", []))]
    for key, name, sub in SECTIONS:
        if placed[key]:
            body.append(f"<h2>{name} <small>{sub}</small></h2>")
            body += [card(t, s, now) for t, s in placed[key]]
    if other:
        rows = "".join(
            f'<tr><td>{done_box(t)}</td><td><span class="kind {kind(t)[0]}">{kind(t)[1]}</span></td>'
            f'<td><a href="{e(t["url"])}">{e(t["title"])}</a></td>'
            f'<td class="repo">{e(t["repo"])} #{t["number"]}</td><td class="repo">{e(t["author"])}</td>'
            f'<td class="repo">{ago(t["updated_at"], now)}</td></tr>'
            for t in other
        )
        head = "<thead><tr><th></th><th></th><th>Title</th><th>Repo</th><th>Author</th><th>Updated ↓</th></tr></thead>"
        body.append(f'<details class="other"><summary>{len(other)} other notifications</summary>'
                    f'<div class="wrap"><table>{head}<tbody>{rows}</tbody></table></div></details>')
    if not data["threads"]:
        body.append("<p>No notifications match this query.</p>")

    if data["threads"]:
        body.append(
            '<div id="donebar" hidden>'
            '<span><b id="donecount">0</b> to mark as done. Run in a terminal:</span>'
            '<input id="donecmd" readonly aria-label="Command"><button id="donecopy" type="button">Copy</button></div>'
            f"<script>{DONE_SCRIPT}</script>"
        )

    local = now.astimezone()
    meta = (f"{local:%d %b %Y, %H:%M} · {len(data['threads'])} notifications since "
            f"{parse_time(data['since']).astimezone():%d %b} · {describe_query(data['query'])}")
    return page(summary.get("title") or "Notification summary", meta, "".join(body), css)


def page(title: str, meta: str, body: str, css: str) -> str:
    """Wrap body HTML in the page shell."""
    return (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{e(title)}</title>"
        # ?theme=light|dark overrides the OS setting.
        "<script>{const t=new URLSearchParams(location.search).get('theme')||"
        "(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');"
        "document.documentElement.dataset.theme=t}</script>"
        f"<style>{css}</style></head><body><main>"
        f"<h1>{e(title)}</h1><p class=meta>{e(meta)}</p>{body}</main></body></html>"
    )


# ---------- done ----------


def mark_done(ids: list[str], delete=gh_delete) -> int:
    """Mark each notification thread as done. Returns the exit code."""
    bad = [i for i in ids if not i.isdigit()]
    if bad:
        print(f"thread IDs must be numbers: {' '.join(bad)}", file=sys.stderr)
        return 2
    failed = False
    for i in ids:
        try:
            delete(f"notifications/threads/{i}")
            print(f"done {i}")
        except RuntimeError as err:
            failed = True
            print(f"failed {i}: {err}", file=sys.stderr)
    return 1 if failed else 0


# ---------- cli ----------


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("query", nargs="?", default="")
    f.add_argument("--days", type=int, default=7)
    f.add_argument("--out", help="output directory (default: a new temp dir)")
    r = sub.add_parser("render")
    r.add_argument("notifications")
    r.add_argument("summary")
    r.add_argument("--out", help="HTML file (default: next to NOTIFICATIONS_JSON)")
    r.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    d = sub.add_parser("done")
    d.add_argument("ids", nargs="+", metavar="ID")
    a = p.parse_args(argv)

    if a.cmd == "done":
        return mark_done(a.ids)

    if a.cmd == "fetch":
        try:
            q = parse_query(a.query)
        except ValueError as err:
            print(err, file=sys.stderr)
            return 2
        out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="notification-summary-"))
        out.mkdir(parents=True, exist_ok=True)
        data = Fetcher().fetch(q, a.days)
        path = out / "notifications.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(path)
        return 0

    data = json.loads(Path(a.notifications).read_text())
    summary = json.loads(Path(a.summary).read_text())
    css = (Path(__file__).parent / "summary.css").read_text()
    out = Path(a.out) if a.out else Path(a.notifications).parent / "notification-summary.html"
    out.write_text(render(data, summary, css))
    print(out)
    if not a.no_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
