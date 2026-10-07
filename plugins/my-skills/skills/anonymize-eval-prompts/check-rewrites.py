#!/usr/bin/env -S uv --quiet run --locked --script

# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "7 days"
# ///

"""Check that rewritten eval prompts neither copy nor leak their originals.

    check-rewrites.py CASES.json [--max-run N]

CASES.json is a list of objects:

    {"original": "...", "rewrite": "...", "private": ["Alice", "acme-billing"]}

For each case the script reports the longest run of consecutive words that
the rewrite shares with the original, and every `private` term the rewrite
still contains (case-insensitive). It exits 1 if any shared run is longer
than N words (default 4) or any private term remains, else 0.
"""

import argparse
import json
import re
import sys

WORD = re.compile(r"\w+(?:[.\-/']\w+)*")


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def longest_shared_run(a: list[str], b: list[str]) -> list[str]:
    best_len, best_end = 0, 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len, best_end = cur[j], i
        prev = cur
    return a[best_end - best_len : best_end]


def leaked_terms(rewrite: str, private: list[str]) -> list[str]:
    low = rewrite.lower()
    return [t for t in private if t.strip() and t.lower() in low]


def check(cases: list[dict], max_run: int) -> tuple[list[str], bool]:
    lines, ok = [], True
    for n, case in enumerate(cases, 1):
        run = longest_shared_run(words(case["original"]), words(case["rewrite"]))
        leaks = leaked_terms(case["rewrite"], case.get("private", []))
        too_long = len(run) > max_run
        ok = ok and not too_long and not leaks
        status = "FAIL" if too_long or leaks else "ok"
        lines.append(f"case {n}: {status}, longest shared run {len(run)} words: {' '.join(run)!r}")
        for t in leaks:
            lines.append(f"case {n}: private term still present: {t!r}")
    return lines, ok


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cases")
    p.add_argument("--max-run", type=int, default=4)
    args = p.parse_args()
    with open(args.cases) as f:
        cases = json.load(f)
    lines, ok = check(cases, args.max_run)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
