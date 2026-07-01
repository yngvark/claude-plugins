#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

"""Filesystem helpers for the `notes` plugin.

The semantic work (writing a thought, inventing a title from a note's
contents) is done by Claude. This script only handles the deterministic,
testable parts: resolving the notes directory, sanitizing titles into safe
filenames, finding untitled daily notes, and renaming files.

Subcommands:
    resolve-dir                     Print the notes dir ($OBSIDIAN_NOTES_DIR).
    note-path "<title>"             Print a unique, safe path for a new note.
    daily-list [--recursive] [dir]  List untitled daily notes (yyyy-mm-dd.md).
    daily-rename <path> "<title>"   Rename yyyy-mm-dd.md -> yyyy-mm-dd <title>.md
    sanitize "<title>"              Print the sanitized form of a title.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ENV_VARS = ("OBSIDIAN_NOTES_DIR", "NOTES_DIR")
DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
# Characters that are illegal or awkward in file names across macOS/Windows.
ILLEGAL = r'/\:*?"<>|'
MAX_TITLE_LEN = 80


def sanitize_title(title: str) -> str:
    """Turn a free-text title into a safe filename stem (no extension)."""
    cleaned = "".join(" " if c in ILLEGAL else c for c in title)
    cleaned = cleaned.replace("\n", " ").replace("\t", " ").replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.strip(".")  # no leading/trailing dots
    cleaned = cleaned[:MAX_TITLE_LEN].strip()
    return cleaned


def resolve_dir() -> Path:
    for var in ENV_VARS:
        val = os.environ.get(var)
        if val:
            p = Path(val).expanduser()
            if not p.is_dir():
                sys.exit(f"error: {var}={val!r} is not an existing directory")
            return p
    sys.exit(
        "error: notes directory not set. Point $OBSIDIAN_NOTES_DIR at your "
        "notes/Obsidian folder, e.g.\n"
        "    export OBSIDIAN_NOTES_DIR=\"$HOME/path/to/vault\""
    )


def unique_path(directory: Path, stem: str, ext: str = ".md") -> Path:
    """Return a path in `directory` for `stem`, avoiding existing files."""
    candidate = directory / f"{stem}{ext}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = directory / f"{stem} {n}{ext}"
        if not candidate.exists():
            return candidate
        n += 1


def is_git_tracked(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(path.parent), "ls-files", "--error-unmatch", path.name],
            capture_output=True,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def move(src: Path, dst: Path) -> None:
    """Rename src -> dst, using `git mv` when src is tracked (preserves history)."""
    if is_git_tracked(src):
        subprocess.run(
            ["git", "-C", str(src.parent), "mv", src.name, dst.name], check=True
        )
    else:
        src.rename(dst)


def cmd_resolve_dir(_argv: list[str]) -> None:
    print(resolve_dir())


def cmd_note_path(argv: list[str]) -> None:
    if not argv:
        sys.exit('usage: notes.py note-path "<title>"')
    stem = sanitize_title(argv[0])
    if not stem:
        sys.exit("error: title is empty after sanitizing")
    print(unique_path(resolve_dir(), stem))


def cmd_daily_list(argv: list[str]) -> None:
    recursive = "--recursive" in argv
    rest = [a for a in argv if a != "--recursive"]
    directory = Path(rest[0]).expanduser() if rest else resolve_dir()
    files = directory.rglob("*.md") if recursive else directory.glob("*.md")
    matches = sorted(p for p in files if DAILY_RE.match(p.name))
    for p in matches:
        print(p)


def cmd_daily_rename(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit('usage: notes.py daily-rename <path> "<title>"')
    src = Path(argv[0]).expanduser()
    m = DAILY_RE.match(src.name)
    if not m:
        sys.exit(f"error: {src.name!r} is not a bare daily note (yyyy-mm-dd.md)")
    if not src.is_file():
        sys.exit(f"error: {src} does not exist")
    title = sanitize_title(argv[1])
    if not title:
        sys.exit("error: title is empty after sanitizing")
    dst = unique_path(src.parent, f"{m.group(1)} {title}")
    move(src, dst)
    print(dst)


def cmd_sanitize(argv: list[str]) -> None:
    if not argv:
        sys.exit('usage: notes.py sanitize "<title>"')
    print(sanitize_title(argv[0]))


COMMANDS = {
    "resolve-dir": cmd_resolve_dir,
    "note-path": cmd_note_path,
    "daily-list": cmd_daily_list,
    "daily-rename": cmd_daily_rename,
    "sanitize": cmd_sanitize,
}


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(f"usage: notes.py {{{'|'.join(COMMANDS)}}} ...")
    COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
