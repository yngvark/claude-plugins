#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

import shutil
import subprocess
import sys
from pathlib import Path


def publish_set(repo: Path) -> list[str]:
    """Return the list of repo-relative paths that would become public on the
    next `git push`: files tracked at HEAD plus staged additions not yet
    committed. Order is deterministic (sorted), entries are unique.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    tracked_paths = [p for p in tracked.split(b"\x00") if p]

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    staged_paths = [p for p in staged.split(b"\x00") if p]

    seen: set[bytes] = set()
    out: list[str] = []
    for p in tracked_paths + staged_paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p.decode("utf-8", errors="replace"))
    return sorted(out)
