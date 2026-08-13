#!/usr/bin/env python3
"""PreToolUse hook for the gh-read plugin.

Reads a Claude Code hook event from stdin and denies any Bash command that
invokes `gh api` directly. Callers must go through the gh-read proxy script,
which enforces GET-only access and an endpoint allowlist.

Stdlib-only so it runs without uv/dependencies on every Bash call.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

GH_API_PATTERN = re.compile(r"\bgh\s+api\b")

# A quoted heredoc delimiter (<<'EOF', <<-"EOF") means the shell performs no
# expansion or command substitution on the body — it is literal data on stdin.
HEREDOC_START = re.compile(r"""<<-?\s*(?:'([A-Za-z_][\w]*)'|"([A-Za-z_][\w]*)")""")

# ...but the process *reading* that data may still execute it. If any of these
# appear on the line opening the heredoc, the body is treated as code and
# scanned normally.
INTERPRETERS = re.compile(
    r"\b(?:bash|sh|zsh|dash|ksh|fish|eval|source|exec|xargs|env|python3?|perl|ruby|node|deno|uv|make)\b"
)

# `git commit -m '…'` and friends: git never executes the message text.
GIT_MESSAGE_COMMAND = re.compile(r"\bgit\s+(?:commit|tag|merge|revert|stash|notes)\b")
GIT_MESSAGE_FLAG = re.compile(r"""(?:-m|--message=?)\s*('[^']*'|"[^"]*")""")


def strip_inert_text(command: str) -> str:
    """Blank out parts of a command that are data, not code.

    Without this, prose that merely mentions the blocked command — a commit
    message, a file written via heredoc — trips the hook. Every exemption is
    also a place to hide a real call, so this stays deliberately narrow: only
    quoted heredocs not fed to an interpreter, and git message arguments. The
    hook is a tripwire for honest mistakes, not a sandbox (see docs/gh-read.md).
    """
    lines = command.splitlines()
    out: list[str] = []
    delimiter: str | None = None
    for line in lines:
        if delimiter is not None:
            out.append("" if line.strip() != delimiter else line)
            if line.strip() == delimiter:
                delimiter = None
            continue
        out.append(line)
        match = HEREDOC_START.search(line)
        if match and not INTERPRETERS.search(line):
            delimiter = match.group(1) or match.group(2)
    result = "\n".join(out)
    if GIT_MESSAGE_COMMAND.search(result):
        result = GIT_MESSAGE_FLAG.sub("-m ''", result)
    return result


DENY_REASON_TEMPLATE = """Direct use of 'gh api' is blocked by the gh-read plugin. Use {script} instead — it enforces GET-only access and an endpoint allowlist.

Retry with:
    {suggestion}

If that call is then rejected as not allowlisted, do NOT work around it with `gh api`, `curl`, or any other tool. Instead:
1. Tell the user prominently that the gh-read plugin is missing support, naming the endpoint or flag needed and why.
2. Offer to fix it — the allowlist lives in {script} (ALLOWED_RESOURCES, ALLOWED_NESTED_RESOURCES, ALLOWED_ORG_NESTED_RESOURCES, ALLOWED_SEARCH_TYPES, SAFE_FLAGS_*), and the plugin source is https://github.com/yngvark/claude-plugins. Propose the concrete edit, or offer to file an issue there.
3. NEVER edit the plugin or file an issue without explicit user consent."""


def script_path() -> str:
    """Absolute path to gh-read.py.

    Claude Code expands ${CLAUDE_PLUGIN_ROOT} in plugin config and skill text,
    but not in hook output, so the message must carry a real path. Prefer the
    env var; fall back to this file's own location when it is unset, so the
    message is never a literal, uncopyable placeholder.
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    root = Path(plugin_root) if plugin_root else Path(__file__).resolve().parent.parent
    return str(root / "skills" / "gh-read" / "gh-read.py")


def deny_reason(command: str) -> str:
    script = script_path()
    suggestion = GH_API_PATTERN.sub(script, command, count=1)
    return DENY_REASON_TEMPLATE.format(script=script, suggestion=suggestion)


def evaluate(event: dict) -> dict | None:
    if event.get("tool_name") != "Bash":
        return None
    command = event.get("tool_input", {}).get("command")
    if not isinstance(command, str):
        return None
    if GH_API_PATTERN.search(strip_inert_text(command)):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason(command),
            }
        }
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(event, dict):
        return 0
    decision = evaluate(event)
    if decision is not None:
        json.dump(decision, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
