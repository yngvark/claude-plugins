#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

import subprocess
import sys

SAFE_FLAGS_NO_ARG = {"--paginate", "-p", "--preview"}
SAFE_FLAGS_WITH_ARG = {"-q", "--jq", "--template", "-H", "--header", "--cache"}

# Allowed third-level resources under repos/{owner}/{repo}/
ALLOWED_RESOURCES = {
    "issues",
    "pulls",
    "commits",
    "contents",
    "compare",
    "releases",
    "comments",
    "branches",
}

# Allowed fourth-level resources under repos/{owner}/{repo}/{group}/{sub}
ALLOWED_NESTED_RESOURCES = {
    ("git", "refs"),
    ("actions", "runs"),
    ("actions", "workflows"),
    ("properties", "values"),
}

# Allowed resources under orgs/{org}/{group}/{sub}
ALLOWED_ORG_NESTED_RESOURCES = {
    ("properties", "schema"),
    ("properties", "values"),
}

# Allowed search types under search/{type}
ALLOWED_SEARCH_TYPES = {
    "issues",
    "repositories",
    "code",
    "commits",
    "users",
    "labels",
    "topics",
}


def is_path_allowed(path: str) -> bool:
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts = path.strip("/").split("/")
    if not parts or not parts[0]:
        return False
    # search/{type}
    if parts[0] == "search":
        return len(parts) == 2 and parts[1] in ALLOWED_SEARCH_TYPES
    # orgs/{org}/{group}/{sub}[/...]
    if parts[0] == "orgs":
        return (
            len(parts) >= 4
            and bool(parts[1])
            and (parts[2], parts[3]) in ALLOWED_ORG_NESTED_RESOURCES
        )
    # Must start with: repos / {owner} / {repo} / {resource...}
    if len(parts) < 4 or parts[0] != "repos":
        return False
    owner, repo = parts[1], parts[2]
    if not owner or not repo:
        return False
    resource = parts[3]
    # repos/{owner}/{repo}/{resource}[/...]
    if resource in ALLOWED_RESOURCES:
        return True
    # repos/{owner}/{repo}/{group}/{sub}[/...]
    if len(parts) >= 5 and (resource, parts[4]) in ALLOWED_NESTED_RESOURCES:
        return True
    return False


def is_safe_flag(arg: str) -> bool:
    """Check if a flag is in the allowlist. Handles --flag=value and -fvalue forms."""
    if arg in SAFE_FLAGS_NO_ARG or arg in SAFE_FLAGS_WITH_ARG:
        return True
    # Handle --flag=value
    if "=" in arg:
        flag_part = arg.split("=", 1)[0]
        return flag_part in SAFE_FLAGS_NO_ARG or flag_part in SAFE_FLAGS_WITH_ARG
    # Handle -qvalue (short flag with concatenated value)
    if len(arg) > 2 and arg[0] == "-" and arg[1] != "-":
        short_flag = arg[:2]
        return short_flag in SAFE_FLAGS_WITH_ARG
    return False


USAGE = """Usage: gh-read.py <api-path> [flags...]

Read-only GitHub API proxy. Forces GET and rejects paths/flags outside the allowlists.

Allowed path patterns:
  repos/{owner}/{repo}/{issues,pulls,commits,contents,compare,releases,comments,branches}[/...]
  repos/{owner}/{repo}/git/refs[/...]
  repos/{owner}/{repo}/actions/{runs,workflows}[/...]
  repos/{owner}/{repo}/properties/values
  orgs/{org}/properties/{schema,values}[/...]
  search/{issues,repositories,code,commits,users,labels,topics}

Allowed flags:
  --paginate, -p              paginate results
  --preview <name>            enable an API preview
  --jq <expr>, -q <expr>      filter output with jq
  --template <tmpl>           format output with Go template
  --header <h>, -H <h>        send a header
  --cache <duration>          cache responses

Examples:
  gh-read.py repos/cli/cli/issues
  gh-read.py repos/cli/cli/pulls/42
  gh-read.py repos/cli/cli/issues?state=open --jq '.[].title'
  gh-read.py search/issues?q=repo:cli/cli+is:open+freeze
"""


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # Accept help anywhere in argv — an unexpanded glob or a stray leading arg
    # would otherwise push --help past position 0 and get it rejected as a flag.
    if any(arg in ("--help", "-h") for arg in args):
        print(USAGE)
        sys.exit(0)

    # Extract API path (first non-flag argument) and validate all flags
    api_path = None
    filtered_args = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            filtered_args.append(arg)
            continue
        if arg == "--":
            print("REJECTED: '--' separator not allowed.", file=sys.stderr)
            sys.exit(1)
        if arg.startswith("-"):
            if not is_safe_flag(arg):
                print(f"REJECTED: flag '{arg}' is not in the safe allowlist.", file=sys.stderr)
                print(f"Allowed flags: {sorted(SAFE_FLAGS_NO_ARG | SAFE_FLAGS_WITH_ARG)}", file=sys.stderr)
                sys.exit(1)
            filtered_args.append(arg)
            # If it's a WITH_ARG flag without =, the next arg is its value
            if arg in SAFE_FLAGS_WITH_ARG:
                skip_next = True
            continue
        if api_path is None:
            api_path = arg
        else:
            # Extra positional args not allowed
            print(f"REJECTED: unexpected positional argument '{arg}'.", file=sys.stderr)
            sys.exit(1)

    if api_path is None:
        print("ERROR: no API path provided.", file=sys.stderr)
        sys.exit(1)

    if not is_path_allowed(api_path):
        print(f"REJECTED: path '{api_path}' is not in the read-safe allowlist.", file=sys.stderr)
        print("Allowed patterns:", file=sys.stderr)
        print("  repos/{owner}/{repo}/{issues,pulls,commits,git/refs,actions/runs,actions/workflows,contents,compare,releases,comments,branches,properties/values}", file=sys.stderr)
        print("  orgs/{org}/properties/{schema,values}", file=sys.stderr)
        print("  search/{issues,repositories,code,commits,users,labels,topics}", file=sys.stderr)
        sys.exit(1)

    cmd = ["gh", "api", "--method", "GET", api_path] + filtered_args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
