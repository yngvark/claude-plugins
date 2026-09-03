#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# ///

"""Filesystem helpers for the `notes` plugin.

The semantic work (writing a thought, inventing a title from a note's
contents, judging which search hit the user meant) is done by Claude. This
script only handles the deterministic, testable parts: resolving the notes
directory, sanitizing titles into safe filenames, locating notes by name or
content, finding untitled daily notes, and renaming files.

Subcommands:
    resolve-dir                     Print the notes dir ($OBSIDIAN_NOTES_DIR, else cwd).
    note-path "<title>"             Print a unique, safe path for a new note.
    find "<query>" [--limit N] [dir]    Find notes whose file name matches.
    search "<text>" [--limit N] [dir]   Find notes whose contents match.
    recent [--limit N] [dir]        List the most recently modified notes.
    daily-list [--recursive] [dir]  List untitled daily notes (yyyy-mm-dd.md).
    daily-rename <path> "<title>"   Rename yyyy-mm-dd.md -> yyyy-mm-dd <title>.md
    undated-list [dir]              List notes whose name has no yyyy-mm-dd prefix.
    date-prefix <path>              Rename note.md -> yyyy-mm-dd note.md
    link-refs <name|path> ...       Find notes that link to the given notes.
    sanitize "<title>"              Print the sanitized form of a title.
"""

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ENV_VARS = ("OBSIDIAN_NOTES_DIR", "NOTES_DIR")
DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
# A note counts as dated when its name starts with yyyy-mm-dd, either alone
# ("2026-07-01.md") or followed by a space ("2026-07-01 Standup.md").
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(\s|$)")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_SOURCES = ("birth", "mtime", "git")
# Files that live in a notes folder without being notes, so they never get a
# date prefix. `--exclude NAME` adds more.
DEFAULT_EXCLUDES = ("CLAUDE.md", "AGENTS.md", "README.md")
# Characters that are illegal or awkward in file names across macOS/Windows.
ILLEGAL = r'/\:*?"<>|'
MAX_TITLE_LEN = 80
DEFAULT_LIMIT = 20
SNIPPET_LEN = 200


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
    # No notes folder configured: use the current directory.
    return Path.cwd()


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


def iter_notes(directory: Path):
    """Yield every Markdown note under `directory`, skipping hidden folders.

    Obsidian keeps `.obsidian/` and `.trash/` next to the notes; neither holds
    anything the user would call a note.
    """
    for p in sorted(directory.rglob("*.md")):
        rel = p.relative_to(directory)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p.is_file():
            yield p


def mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def name_score(stem: str, query: str, tokens: list[str]) -> int:
    """Rank a file name against a query: higher is a better match, 0 is no match."""
    stem = stem.lower()
    if stem == query:
        return 4
    if stem.startswith(query):
        return 3
    if query in stem:
        return 2
    if tokens and all(t in stem for t in tokens):
        return 1
    return 0


def find_notes(directory: Path, query: str, limit: int = DEFAULT_LIMIT) -> list[Path]:
    """Notes whose file name matches `query`, best match first, then newest."""
    query = query.strip().lower().removesuffix(".md").strip()
    tokens = [t for t in re.split(r"\s+", query) if t]
    scored = []
    for p in iter_notes(directory):
        score = name_score(p.stem, query, tokens)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda sp: (-sp[0], -mtime(sp[1]), str(sp[1])))
    return [p for _, p in scored[:limit]]


def search_notes(
    directory: Path, text: str, limit: int = DEFAULT_LIMIT
) -> list[tuple[Path, int, str]]:
    """Lines containing `text` (case-insensitive), at most one hit per note."""
    needle = text.strip().lower()
    hits: list[tuple[Path, int, str]] = []
    if not needle:
        return hits
    for p in iter_notes(directory):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if needle in line.lower():
                hits.append((p, lineno, line.strip()[:SNIPPET_LEN]))
                break
    hits.sort(key=lambda h: (-mtime(h[0]), str(h[0])))
    return hits[:limit]


def recent_notes(directory: Path, limit: int = 10) -> list[Path]:
    return sorted(iter_notes(directory), key=lambda p: (-mtime(p), str(p)))[:limit]


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


def has_date_prefix(name: str) -> bool:
    """True when a file name already starts with a yyyy-mm-dd date."""
    return bool(DATE_PREFIX_RE.match(Path(name).stem))


def git_added_date(path: Path) -> str | None:
    """The date the commit that added `path` was authored, or None.

    Cloning or checking out a Git-tracked vault resets every file's birth time
    to the checkout, so for those vaults the first commit is the only honest
    record of when a note was written.
    """
    try:
        r = subprocess.run(
            [
                "git", "-C", str(path.parent),
                "log", "--diff-filter=A", "--follow",
                "--format=%ad", "--date=short",
                "--", path.name,
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    dates = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    # `git log` prints newest first, so the oldest add is the last line.
    return dates[-1] if dates else None


def note_date(path: Path, source: str = "birth") -> str:
    """The yyyy-mm-dd date to put in front of a note's name.

    `source` is "birth" (file creation time, the default), "mtime" (last
    edit), or "git" (the commit that added the file). Both "birth" and "git"
    fall back to the modification time when the platform or the vault cannot
    answer — every filesystem records an mtime.
    """
    if source not in DATE_SOURCES:
        raise ValueError(f"unknown date source {source!r}")
    if source == "git":
        dated = git_added_date(path)
        if dated:
            return dated
    st = path.stat()
    ts = getattr(st, "st_birthtime", None) if source != "mtime" else None
    if ts is None:
        ts = st.st_mtime
    return datetime.date.fromtimestamp(ts).isoformat()


def undated_notes(
    directory: Path,
    recursive: bool = False,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> list[Path]:
    """Notes in `directory` whose file name has no yyyy-mm-dd prefix."""
    if recursive:
        files = list(iter_notes(directory))
    else:
        files = sorted(p for p in directory.glob("*.md") if p.is_file())
    skip = set(excludes)
    return [p for p in files if p.name not in skip and not has_date_prefix(p.name)]


def link_pattern(stem: str) -> re.Pattern:
    """Match links pointing at the note named `stem`.

    Covers Obsidian wikilinks (`[[Note]]`, `[[dir/Note|alias]]`,
    `[[Note#heading]]`, and `![[Note]]` embeds) and Markdown links
    (`](Note.md)`, `](dir/Note%20two.md#heading)`).
    """
    name = re.escape(stem)
    encoded = re.escape(quote(stem))
    return re.compile(
        rf"\[\[(?:[^\[\]|#]*/)?{name}(?=[\]|#])"
        rf"|\]\((?:[^()]*/)?(?:{name}|{encoded})(?:\.md)?(?=[)#])",
        re.IGNORECASE,
    )


def link_refs(directory: Path, target: str) -> list[tuple[Path, int, str]]:
    """Lines anywhere under `directory` that link to the note `target`.

    `target` may be a bare note name or a full path; only its stem matters.
    Links inside the target note itself are left out.
    """
    stem = Path(target).stem
    if not stem:
        return []
    pattern = link_pattern(stem)
    hits: list[tuple[Path, int, str]] = []
    for p in iter_notes(directory):
        if p.stem.lower() == stem.lower():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                hits.append((p, lineno, line.strip()[:SNIPPET_LEN]))
    hits.sort(key=lambda h: (str(h[0]), h[1]))
    return hits


def cmd_resolve_dir(_argv: list[str]) -> None:
    print(resolve_dir())


def cmd_note_path(argv: list[str]) -> None:
    if not argv:
        sys.exit('usage: notes.py note-path "<title>"')
    stem = sanitize_title(argv[0])
    if not stem:
        sys.exit("error: title is empty after sanitizing")
    print(unique_path(resolve_dir(), stem))


def take_limit(argv: list[str], default: int) -> tuple[int, list[str]]:
    """Pull `--limit N` (or `--limit=N`) out of argv; return (limit, rest)."""
    rest: list[str] = []
    limit = default
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--limit":
            if i + 1 >= len(argv):
                sys.exit("error: --limit needs a number")
            value, i = argv[i + 1], i + 2
        elif arg.startswith("--limit="):
            value, i = arg.split("=", 1)[1], i + 1
        else:
            rest.append(arg)
            i += 1
            continue
        if not value.isdigit() or int(value) < 1:
            sys.exit(f"error: --limit must be a positive integer, got {value!r}")
        limit = int(value)
    return limit, rest


def take_repeated(argv: list[str], flag: str) -> tuple[list[str], list[str]]:
    """Pull every `<flag> VALUE` (or `<flag>=VALUE`) out of argv.

    Returns (values in the order given, remaining argv).
    """
    values: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == flag:
            if i + 1 >= len(argv):
                sys.exit(f"error: {flag} needs a value")
            values.append(argv[i + 1])
            i += 2
        elif arg.startswith(f"{flag}="):
            values.append(arg.split("=", 1)[1])
            i += 1
        else:
            rest.append(arg)
            i += 1
    return values, rest


def take_date_source(argv: list[str]) -> tuple[str, list[str]]:
    """Pull `--date-source birth|mtime|git` out of argv; default is "birth"."""
    values, rest = take_repeated(argv, "--date-source")
    source = values[-1] if values else "birth"
    if source not in DATE_SOURCES:
        sys.exit(
            f"error: --date-source must be one of {', '.join(DATE_SOURCES)}, "
            f"got {source!r}"
        )
    return source, rest


def dir_from(argv: list[str]) -> Path:
    return Path(argv[0]).expanduser() if argv else resolve_dir()


def cmd_find(argv: list[str]) -> None:
    limit, rest = take_limit(argv, DEFAULT_LIMIT)
    if not rest:
        sys.exit('usage: notes.py find "<query>" [--limit N] [dir]')
    for p in find_notes(dir_from(rest[1:]), rest[0], limit):
        print(p)


def cmd_search(argv: list[str]) -> None:
    limit, rest = take_limit(argv, DEFAULT_LIMIT)
    if not rest:
        sys.exit('usage: notes.py search "<text>" [--limit N] [dir]')
    for path, lineno, line in search_notes(dir_from(rest[1:]), rest[0], limit):
        print(f"{path}:{lineno}: {line}")


def cmd_recent(argv: list[str]) -> None:
    limit, rest = take_limit(argv, 10)
    for p in recent_notes(dir_from(rest), limit):
        print(p)


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


def cmd_undated_list(argv: list[str]) -> None:
    source, argv = take_date_source(argv)
    extra, argv = take_repeated(argv, "--exclude")
    recursive = "--recursive" in argv
    rest = [a for a in argv if a != "--recursive"]
    if len(rest) > 1:
        sys.exit(
            "usage: notes.py undated-list [--recursive] [--exclude NAME] "
            "[--date-source birth|mtime|git] [dir]"
        )
    directory = dir_from(rest)
    excludes = DEFAULT_EXCLUDES + tuple(extra)
    for p in undated_notes(directory, recursive=recursive, excludes=excludes):
        print(f"{note_date(p, source)}\t{p}")


def cmd_date_prefix(argv: list[str]) -> None:
    source, argv = take_date_source(argv)
    given, argv = take_repeated(argv, "--date")
    if len(argv) != 1:
        sys.exit(
            "usage: notes.py date-prefix <path> [--date yyyy-mm-dd] "
            "[--date-source birth|mtime|git]"
        )
    src = Path(argv[0]).expanduser()
    if not src.is_file():
        sys.exit(f"error: {src} does not exist")
    if has_date_prefix(src.name):
        sys.exit(f"error: {src.name!r} already starts with a date")
    if given:
        date = given[-1]
        if not ISO_DATE_RE.match(date):
            sys.exit(f"error: --date must be yyyy-mm-dd, got {date!r}")
    else:
        date = note_date(src, source)
    dst = unique_path(src.parent, f"{date} {src.stem}", src.suffix)
    move(src, dst)
    print(dst)


def cmd_link_refs(argv: list[str]) -> None:
    dirs, targets = take_repeated(argv, "--dir")
    if not targets:
        sys.exit("usage: notes.py link-refs <name|path> ... [--dir DIR]")
    directory = Path(dirs[-1]).expanduser() if dirs else resolve_dir()
    for target in targets:
        for path, lineno, line in link_refs(directory, target):
            print(f"{Path(target).stem}\t{path}:{lineno}: {line}")


def cmd_sanitize(argv: list[str]) -> None:
    if not argv:
        sys.exit('usage: notes.py sanitize "<title>"')
    print(sanitize_title(argv[0]))


COMMANDS = {
    "resolve-dir": cmd_resolve_dir,
    "note-path": cmd_note_path,
    "find": cmd_find,
    "search": cmd_search,
    "recent": cmd_recent,
    "daily-list": cmd_daily_list,
    "daily-rename": cmd_daily_rename,
    "undated-list": cmd_undated_list,
    "date-prefix": cmd_date_prefix,
    "link-refs": cmd_link_refs,
    "sanitize": cmd_sanitize,
}


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(f"usage: notes.py {{{'|'.join(COMMANDS)}}} ...")
    COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
