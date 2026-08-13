#!/usr/bin/env -S uv --quiet run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Tests for the gh-read PreToolUse hook (block-gh-api.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPT = Path(__file__).parent / "hooks" / "block-gh-api.py"


def run_hook(event: dict, plugin_root: str | None = None) -> tuple[int, dict | None, str]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    out = proc.stdout.strip()
    parsed = json.loads(out) if out else None
    return proc.returncode, parsed, proc.stderr


def bash_event(command: str) -> dict:
    return {
        "session_id": "test",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestDeniesGhApi:
    @pytest.mark.parametrize(
        "command",
        [
            "gh api repos/foo/bar/issues",
            "gh   api repos/foo/bar",
            "ls && gh api /user",
            "ls; gh api /user",
            "(gh api foo)",
            "gh api -X GET repos/foo/bar",
            "bash -c 'gh api repos/foo/bar'",
            "gh api foo | jq .",
            "$(gh api foo)",
        ],
    )
    def test_command_is_denied(self, command: str) -> None:
        code, out, _ = run_hook(bash_event(command))
        assert code == 0
        assert out is not None, f"expected deny output, got nothing for: {command!r}"
        decision = out["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert "gh-read" in decision["permissionDecisionReason"]


class TestDenyReasonPath:
    def test_plugin_root_is_expanded(self) -> None:
        _, out, _ = run_hook(bash_event("gh api /user"), plugin_root="/plugins/gh-read")
        assert out is not None
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "/plugins/gh-read/skills/gh-read/gh-read.py" in reason
        assert "${CLAUDE_PLUGIN_ROOT}" not in reason

    def test_falls_back_to_own_location_when_unset(self) -> None:
        _, out, _ = run_hook(bash_event("gh api /user"))
        assert out is not None
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        expected = HOOK_SCRIPT.resolve().parent.parent / "skills" / "gh-read" / "gh-read.py"
        assert str(expected) in reason
        assert "${CLAUDE_PLUGIN_ROOT}" not in reason


class TestDenyReasonIsActionable:
    def test_reason_includes_rewritten_command(self) -> None:
        _, out, _ = run_hook(bash_event("gh api repos/foo/bar/issues --jq '.[].title'"))
        assert out is not None
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "skills/gh-read/gh-read.py repos/foo/bar/issues --jq '.[].title'" in reason

    def test_reason_rewrites_only_the_gh_api_invocation(self) -> None:
        _, out, _ = run_hook(bash_event("ls && gh api /user"))
        assert out is not None
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ls && " in reason
        assert "gh-read.py /user" in reason

    def test_reason_explains_how_to_extend_the_allowlist(self) -> None:
        _, out, _ = run_hook(bash_event("gh api repos/foo/bar/secrets"))
        assert out is not None
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ALLOWED_RESOURCES" in reason
        assert "github.com/yngvark/claude-plugins" in reason
        assert "consent" in reason


class TestProseMentionsAreNotCommands:
    """Text that merely names the blocked command must not trip the hook."""

    @pytest.mark.parametrize(
        "command",
        [
            "git commit -F - <<'EOF'\nfix: stop using gh api directly\nEOF",
            'git commit -F - <<"MSG"\nnote: gh api is blocked\nMSG',
            "cat > notes.md <<'EOF'\nNever call gh api yourself.\nEOF",
            "git commit -m 'docs: explain why gh api is blocked'",
            'git commit -m "docs: explain why gh api is blocked"',
            'git commit --message="gh api notes"',
        ],
    )
    def test_prose_passes(self, command: str) -> None:
        code, out, _ = run_hook(bash_event(command))
        assert code == 0
        assert out is None, f"expected no decision, got: {out!r} for: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            # Heredoc fed to an interpreter: the body is code, not data.
            "bash <<'EOF'\ngh api /user\nEOF",
            "python3 - <<'PY'\nsubprocess.run('gh api /user')\nPY",
            "sh <<'EOF'\ngh api /user\nEOF",
            # Unquoted delimiter: the shell substitutes inside the body.
            "cat <<EOF\n$(gh api /user)\nEOF",
            # Real command after the heredoc closes.
            "git commit -F - <<'EOF'\nmessage text\nEOF\ngh api /user",
            # A message flag does not exempt the rest of the line.
            "git commit -m 'msg' && gh api /user",
        ],
    )
    def test_still_denied(self, command: str) -> None:
        code, out, _ = run_hook(bash_event(command))
        assert code == 0
        assert out is not None, f"expected deny, got nothing for: {command!r}"


class TestAllowsLegitimateCommands:
    @pytest.mark.parametrize(
        "command",
        [
            "gh pr view 42",
            "gh issue create --title foo",
            "gh run view 12345 --log",
            "gh auth status",
            "gh-read.py repos/foo/bar/issues",
            "${CLAUDE_PLUGIN_ROOT}/skills/gh-read/gh-read.py repos/foo/bar/pulls",
            "ls -la",
            "echo hello",
            "git status",
            "ghapi-something --help",
        ],
    )
    def test_command_passes(self, command: str) -> None:
        code, out, _ = run_hook(bash_event(command))
        assert code == 0
        assert out is None, f"expected no decision, got: {out!r} for: {command!r}"


class TestNonBashToolsIgnored:
    def test_write_tool_with_gh_api_string_is_ignored(self) -> None:
        event = {
            "session_id": "test",
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/foo",
                "content": "documentation about gh api usage",
            },
        }
        code, out, _ = run_hook(event)
        assert code == 0
        assert out is None


class TestMalformedInput:
    def test_invalid_json_is_silently_allowed(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="not json at all",
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_missing_tool_input(self) -> None:
        code, out, _ = run_hook({"tool_name": "Bash"})
        assert code == 0
        assert out is None

    def test_command_field_is_not_string(self) -> None:
        event = {"tool_name": "Bash", "tool_input": {"command": ["gh", "api", "x"]}}
        code, out, _ = run_hook(event)
        assert code == 0
        assert out is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
