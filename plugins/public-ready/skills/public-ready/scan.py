#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


INSTALL_HINT = (
    "ERROR: 'gitleaks' is required but was not found on PATH.\n"
    "Install it with one of:\n"
    "  brew install gitleaks                 # macOS / Linuxbrew\n"
    "  apt-get install gitleaks              # Debian/Ubuntu (where packaged)\n"
    "  https://github.com/gitleaks/gitleaks/releases  # binary releases\n"
)


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


def parse_findings(report_json: str) -> list[dict]:
    text = report_json.strip()
    if not text or text == "null":
        return []
    raw = json.loads(text)
    if raw is None:
        return []
    out: list[dict] = []
    for item in raw:
        match = item.get("Match", "") or item.get("Secret", "")
        out.append(
            {
                "file": item.get("File", ""),
                "line": int(item.get("StartLine", 0) or 0),
                "rule": item.get("RuleID", ""),
                "description": item.get("Description", ""),
                "snippet": match,
            }
        )
    return out


def format_report_section(findings: list[dict]) -> str:
    if not findings:
        return "_No secrets detected by gitleaks._"
    lines: list[str] = []
    for f in findings:
        lines.append(
            f"- **{f['file']}:{f['line']}** — `{f['rule']}` "
            f"({f['description']}): `{f['snippet']}`"
        )
    return "\n".join(lines)


def run_gitleaks(repo: Path, report_path: Path) -> None:
    """Run gitleaks against the working directory. Treats exit codes 0 (clean)
    and 1 (findings) as success; raises on anything else.
    """
    proc = subprocess.run(
        [
            "gitleaks",
            "detect",
            "--no-git",
            "--source",
            str(repo),
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--exit-code",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"gitleaks exited with {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def filter_to_publish_set(findings: list[dict], publish: list[str]) -> list[dict]:
    publish_set_norm = set(publish)
    return [f for f in findings if f["file"] in publish_set_norm]


def main() -> int:
    if shutil.which("gitleaks") is None:
        print(INSTALL_HINT, file=sys.stderr)
        return 1

    repo = Path.cwd()
    publish = publish_set(repo)

    with tempfile.TemporaryDirectory() as td:
        report_path = Path(td) / "gitleaks.json"
        try:
            run_gitleaks(repo, report_path)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        report_text = report_path.read_text() if report_path.exists() else ""

    all_findings = parse_findings(report_text)
    findings = filter_to_publish_set(all_findings, publish)

    print("## Secrets")
    print()
    print(format_report_section(findings))
    print()
    print(f"_Scanned {len(publish)} file(s) in the publish set._")
    return 0


if __name__ == "__main__":
    sys.exit(main())
