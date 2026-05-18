#!/usr/bin/env -S uv --quiet run --script
"""Locate the current session's Claude Code transcript file.

Claude Code stores per-project transcripts as JSONL files under
``~/.claude/projects/<encoded-cwd>/`` where ``<encoded-cwd>`` is the current
working directory with every ``/`` replaced by ``-`` (so a leading ``/``
becomes a leading ``-``).

This script prints the absolute path of the most recently modified ``*.jsonl``
in that directory. It exits non-zero with a message on stderr if the directory
or any transcripts are missing.

Args (for testing only):
    --cwd <dir>            Override the current working directory.
    --projects-root <dir>  Override ``~/.claude/projects``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def encode_cwd(cwd: str) -> str:
    return cwd.replace("/", "-")


def find_latest_transcript(projects_root: Path, cwd: str) -> Path | None:
    transcript_dir = projects_root / encode_cwd(cwd)
    if not transcript_dir.is_dir():
        return None
    candidates = sorted(
        transcript_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument(
        "--projects-root",
        default=str(Path.home() / ".claude" / "projects"),
    )
    args = parser.parse_args(argv)

    latest = find_latest_transcript(Path(args.projects_root), args.cwd)
    if latest is None:
        print(
            f"No transcript found under {args.projects_root}/{encode_cwd(args.cwd)}",
            file=sys.stderr,
        )
        return 1
    print(str(latest))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
