#!/usr/bin/env python3
"""SessionEnd hook for the session-review plugin.

Reads the Claude Code hook event from stdin and prints a single-line nudge
suggesting /session-review. Stdlib-only so it runs without uv/dependencies.
"""

from __future__ import annotations

import json
import sys

NUDGE = "[session-review] Consider running /session-review to capture lessons from this session."


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass
    print(NUDGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
