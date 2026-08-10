#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import pytest
import subprocess
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Load the module under test
_mod_path = str(Path(__file__).parent / "skills" / "gh-read" / "gh-read.py")
gh_read = SourceFileLoader("gh_read", _mod_path).load_module()

is_path_allowed = gh_read.is_path_allowed
is_safe_flag = gh_read.is_safe_flag

SCRIPT = _mod_path


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# is_path_allowed
# ---------------------------------------------------------------------------

class TestPathAllowed:
    # -- valid paths --

    def test_issues(self):
        assert is_path_allowed("repos/owner/repo/issues")

    def test_issues_with_leading_slash(self):
        assert is_path_allowed("/repos/owner/repo/issues")

    def test_issues_with_id(self):
        assert is_path_allowed("repos/owner/repo/issues/123")

    def test_issues_sub_resource(self):
        assert is_path_allowed("repos/owner/repo/issues/123/comments")

    def test_pulls(self):
        assert is_path_allowed("repos/owner/repo/pulls")

    def test_pulls_with_id(self):
        assert is_path_allowed("repos/owner/repo/pulls/42")

    def test_commits(self):
        assert is_path_allowed("repos/owner/repo/commits")

    def test_contents(self):
        assert is_path_allowed("repos/owner/repo/contents")

    def test_contents_deep_path(self):
        assert is_path_allowed("repos/owner/repo/contents/src/main/app.py")

    def test_compare(self):
        assert is_path_allowed("repos/owner/repo/compare/main...feature")

    def test_releases(self):
        assert is_path_allowed("repos/owner/repo/releases")

    def test_comments(self):
        assert is_path_allowed("repos/owner/repo/comments/99")

    def test_branches(self):
        assert is_path_allowed("repos/owner/repo/branches")

    def test_branches_with_name(self):
        assert is_path_allowed("repos/owner/repo/branches/main")

    def test_branches_protection(self):
        assert is_path_allowed("repos/owner/repo/branches/main/protection")

    def test_branches_protection_sub_resource(self):
        assert is_path_allowed(
            "repos/owner/repo/branches/main/protection/required_status_checks"
        )

    def test_git_refs(self):
        assert is_path_allowed("repos/owner/repo/git/refs")

    def test_git_refs_sub(self):
        assert is_path_allowed("repos/owner/repo/git/refs/heads/main")

    def test_actions_runs(self):
        assert is_path_allowed("repos/owner/repo/actions/runs")

    def test_actions_runs_with_id(self):
        assert is_path_allowed("repos/owner/repo/actions/runs/12345")

    def test_actions_workflows(self):
        assert is_path_allowed("repos/owner/repo/actions/workflows")

    def test_repo_properties_values(self):
        assert is_path_allowed("repos/owner/repo/properties/values")

    def test_org_properties_schema(self):
        assert is_path_allowed("orgs/myorg/properties/schema")

    def test_org_properties_schema_with_name(self):
        assert is_path_allowed("orgs/myorg/properties/schema/my-prop")

    def test_org_properties_values(self):
        assert is_path_allowed("orgs/myorg/properties/values")

    def test_query_string_on_resource(self):
        assert is_path_allowed("repos/owner/repo/pulls?state=closed")

    def test_query_string_on_nested_resource(self):
        assert is_path_allowed("repos/owner/repo/actions/runs?status=failure")

    def test_query_string_with_amp(self):
        assert is_path_allowed("repos/owner/repo/issues?state=open&per_page=50")

    def test_fragment_on_resource(self):
        assert is_path_allowed("repos/owner/repo/pulls#frag")

    # -- rejected paths --

    def test_reject_empty(self):
        assert not is_path_allowed("")

    def test_reject_just_repos(self):
        assert not is_path_allowed("repos")

    def test_reject_repos_owner(self):
        assert not is_path_allowed("repos/owner")

    def test_reject_repos_owner_repo(self):
        assert not is_path_allowed("repos/owner/repo")

    def test_reject_deployments(self):
        assert not is_path_allowed("repos/owner/repo/deployments")

    def test_reject_hooks(self):
        assert not is_path_allowed("repos/owner/repo/hooks")

    def test_reject_keys(self):
        assert not is_path_allowed("repos/owner/repo/keys")

    def test_reject_user(self):
        assert not is_path_allowed("user")

    def test_reject_graphql(self):
        assert not is_path_allowed("graphql")

    def test_reject_orgs(self):
        assert not is_path_allowed("orgs/myorg/repos")

    def test_reject_repo_properties_bare(self):
        assert not is_path_allowed("repos/owner/repo/properties")

    def test_reject_org_properties_bare(self):
        assert not is_path_allowed("orgs/myorg/properties")

    def test_reject_org_empty_name(self):
        assert not is_path_allowed("orgs//properties/schema")

    def test_reject_empty_owner(self):
        assert not is_path_allowed("repos//repo/issues")

    def test_reject_empty_repo(self):
        assert not is_path_allowed("repos/owner//issues")

    def test_reject_git_trees(self):
        assert not is_path_allowed("repos/owner/repo/git/trees")

    def test_reject_actions_secrets(self):
        assert not is_path_allowed("repos/owner/repo/actions/secrets")

    def test_reject_actions_permissions(self):
        assert not is_path_allowed("repos/owner/repo/actions/permissions")

    def test_reject_disallowed_with_query_string(self):
        assert not is_path_allowed("repos/owner/repo/hooks?state=open")

    # -- search paths --

    def test_search_issues(self):
        assert is_path_allowed("search/issues")

    def test_search_issues_with_query(self):
        assert is_path_allowed("search/issues?q=repo:cli/cli+is:open")

    def test_search_issues_with_leading_slash(self):
        assert is_path_allowed("/search/issues")

    def test_search_repositories(self):
        assert is_path_allowed("search/repositories")

    def test_search_code(self):
        assert is_path_allowed("search/code")

    def test_search_commits(self):
        assert is_path_allowed("search/commits")

    def test_search_users(self):
        assert is_path_allowed("search/users")

    def test_search_labels(self):
        assert is_path_allowed("search/labels")

    def test_search_topics(self):
        assert is_path_allowed("search/topics")

    def test_reject_search_bare(self):
        assert not is_path_allowed("search")

    def test_reject_search_unknown_type(self):
        assert not is_path_allowed("search/teams")

    def test_reject_search_extra_segment(self):
        assert not is_path_allowed("search/issues/123")


# ---------------------------------------------------------------------------
# is_safe_flag
# ---------------------------------------------------------------------------

class TestSafeFlag:
    # -- allowed flags --

    def test_paginate(self):
        assert is_safe_flag("--paginate")

    def test_short_paginate(self):
        assert is_safe_flag("-p")

    def test_preview(self):
        assert is_safe_flag("--preview")

    def test_jq(self):
        assert is_safe_flag("--jq")

    def test_jq_with_value(self):
        assert is_safe_flag("--jq=.items")

    def test_template(self):
        assert is_safe_flag("--template")

    def test_template_with_value(self):
        assert is_safe_flag("--template={{.title}}")

    def test_header(self):
        assert is_safe_flag("--header")

    def test_header_with_value(self):
        assert is_safe_flag("--header=Accept:application/json")

    def test_short_header(self):
        assert is_safe_flag("-H")

    def test_short_header_concat(self):
        assert is_safe_flag("-HAccept:application/json")

    def test_short_q(self):
        assert is_safe_flag("-q")

    def test_short_q_concat(self):
        assert is_safe_flag("-q.items")

    def test_cache(self):
        assert is_safe_flag("--cache")

    def test_cache_with_value(self):
        assert is_safe_flag("--cache=1h")

    # -- rejected flags --

    def test_reject_method(self):
        assert not is_safe_flag("--method")

    def test_reject_method_value(self):
        assert not is_safe_flag("--method=POST")

    def test_reject_method_prefix(self):
        assert not is_safe_flag("--metho")

    def test_reject_method_short_prefix(self):
        assert not is_safe_flag("--me=DELETE")

    def test_reject_X(self):
        assert not is_safe_flag("-X")

    def test_reject_X_concat_POST(self):
        assert not is_safe_flag("-XPOST")

    def test_reject_X_concat_DELETE(self):
        assert not is_safe_flag("-XDELETE")

    def test_reject_X_concat_PATCH(self):
        assert not is_safe_flag("-XPATCH")

    def test_reject_X_concat_PUT(self):
        assert not is_safe_flag("-XPUT")

    def test_reject_field(self):
        assert not is_safe_flag("--field")

    def test_reject_field_value(self):
        assert not is_safe_flag("--field=title=x")

    def test_reject_short_f(self):
        assert not is_safe_flag("-f")

    def test_reject_short_f_concat(self):
        assert not is_safe_flag("-ftitle=test")

    def test_reject_short_F(self):
        assert not is_safe_flag("-F")

    def test_reject_short_F_concat(self):
        assert not is_safe_flag("-Ftitle=test")

    def test_reject_raw_field(self):
        assert not is_safe_flag("--raw-field")

    def test_reject_input(self):
        assert not is_safe_flag("--input")

    def test_reject_input_value(self):
        assert not is_safe_flag("--input=/tmp/body.json")

    def test_reject_unknown_long(self):
        assert not is_safe_flag("--hostname")

    def test_reject_unknown_short(self):
        assert not is_safe_flag("-i")


# ---------------------------------------------------------------------------
# End-to-end: integration via subprocess
# ---------------------------------------------------------------------------

class TestEndToEnd:
    # -- rejection cases --

    def test_no_args(self):
        r = run([])
        assert r.returncode == 1
        assert "Usage" in r.stderr

    def test_help_long(self):
        r = run(["--help"])
        assert r.returncode == 0
        assert "Usage" in r.stdout
        assert "Allowed path patterns" in r.stdout
        assert "Allowed flags" in r.stdout

    def test_help_short(self):
        r = run(["-h"])
        assert r.returncode == 0
        assert "Usage" in r.stdout

    def test_help_after_positional(self):
        r = run(["repos/o/r/issues", "--help"])
        assert r.returncode == 0
        assert "Usage" in r.stdout

    def test_help_after_stray_arg(self):
        # e.g. a shell glob that matched two script paths, shifting --help
        r = run(["/some/other/gh-read.py", "--help"])
        assert r.returncode == 0
        assert "Usage" in r.stdout

    def test_no_path(self):
        r = run(["--jq", ".items"])
        assert r.returncode == 1
        assert "no API path" in r.stderr

    def test_disallowed_path(self):
        r = run(["repos/owner/repo/hooks"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr
        assert "allowlist" in r.stderr

    def test_bypass_X_concat(self):
        r = run(["repos/o/r/issues", "-XPOST"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_method_prefix(self):
        r = run(["repos/o/r/issues", "--me=DELETE"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_f_concat(self):
        r = run(["repos/o/r/issues", "-ftitle=pwned"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_F_concat(self):
        r = run(["repos/o/r/issues", "-Ftitle=pwned"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_field_eq(self):
        r = run(["repos/o/r/issues", "--field=title=x"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_input_eq(self):
        r = run(["repos/o/r/issues", "--input=/tmp/x"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_bypass_raw_field(self):
        r = run(["repos/o/r/issues", "--raw-field", "body=x"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_double_dash_separator(self):
        r = run(["repos/o/r/issues", "--", "-XPOST"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_extra_positional_arg(self):
        r = run(["repos/o/r/issues", "extra"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    def test_unknown_flag(self):
        r = run(["repos/o/r/issues", "--hostname=evil.com"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr

    # -- acceptance cases (path validated, flags allowed, gh api called) --
    # These will fail with a gh error (no auth / fake repo) but should NOT
    # be rejected by our script. We check that stderr does NOT contain REJECTED.

    def test_accept_bare_path(self):
        r = run(["repos/o/r/issues"])
        assert "REJECTED" not in r.stderr

    def test_accept_with_jq(self):
        r = run(["repos/o/r/pulls", "--jq", ".[].title"])
        assert "REJECTED" not in r.stderr

    def test_accept_with_jq_eq(self):
        r = run(["repos/o/r/pulls", "--jq=.[].title"])
        assert "REJECTED" not in r.stderr

    def test_accept_with_paginate(self):
        r = run(["repos/o/r/commits", "--paginate"])
        assert "REJECTED" not in r.stderr

    def test_accept_with_header(self):
        r = run(["repos/o/r/contents", "-H", "Accept:application/vnd.github.raw"])
        assert "REJECTED" not in r.stderr

    def test_accept_with_cache(self):
        r = run(["repos/o/r/releases", "--cache", "1h"])
        assert "REJECTED" not in r.stderr

    def test_accept_short_q_concat(self):
        r = run(["repos/o/r/issues", "-q.items"])
        assert "REJECTED" not in r.stderr

    def test_accept_search_issues_with_query(self):
        r = run(["search/issues?q=repo:cli/cli+is:open"])
        assert "REJECTED" not in r.stderr

    def test_reject_search_unknown_type_e2e(self):
        r = run(["search/teams"])
        assert r.returncode == 1
        assert "REJECTED" in r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))
