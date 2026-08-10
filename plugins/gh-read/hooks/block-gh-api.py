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

GH_API_PATTERN = re.compile(r"\bgh\s+api\b")


def deny_reason() -> str:
    # Claude Code expands ${CLAUDE_PLUGIN_ROOT} in plugin config and skill text,
    # but not in hook output — resolve it here so the message is copy-pasteable.
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}")
    return (
        "Direct use of 'gh api' is blocked by the gh-read plugin. "
        f"Use {plugin_root}/skills/gh-read/gh-read.py instead — "
        "it enforces GET-only access and an endpoint allowlist. "
        "Run it with --help to see allowed paths and flags."
    )


def evaluate(event: dict) -> dict | None:
    if event.get("tool_name") != "Bash":
        return None
    command = event.get("tool_input", {}).get("command")
    if not isinstance(command, str):
        return None
    if GH_API_PATTERN.search(command):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason(),
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
