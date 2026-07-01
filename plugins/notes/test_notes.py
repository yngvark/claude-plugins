#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

notes = SourceFileLoader(
    "notes", str(Path(__file__).parent / "scripts" / "notes.py")
).load_module()


class TestSanitizeTitle:
    def test_keeps_spaces_and_case(self):
        assert notes.sanitize_title("Meeting with team") == "Meeting with team"

    def test_strips_illegal_chars(self):
        assert notes.sanitize_title('a/b:c*d?"e<f>g|h\\i') == "a b c d e f g h i"

    def test_collapses_whitespace_and_newlines(self):
        assert notes.sanitize_title("a\n  b\t c") == "a b c"

    def test_strips_leading_trailing_dots(self):
        assert notes.sanitize_title("...title...") == "title"

    def test_truncates_to_max_len(self):
        out = notes.sanitize_title("x" * 200)
        assert len(out) == notes.MAX_TITLE_LEN

    def test_empty_when_only_illegal(self):
        assert notes.sanitize_title("///") == ""


class TestUniquePath:
    def test_first_use_no_suffix(self, tmp_path: Path):
        assert notes.unique_path(tmp_path, "Idea") == tmp_path / "Idea.md"

    def test_collision_appends_number(self, tmp_path: Path):
        (tmp_path / "Idea.md").write_text("x")
        assert notes.unique_path(tmp_path, "Idea") == tmp_path / "Idea 2.md"

    def test_second_collision_increments(self, tmp_path: Path):
        (tmp_path / "Idea.md").write_text("x")
        (tmp_path / "Idea 2.md").write_text("x")
        assert notes.unique_path(tmp_path, "Idea") == tmp_path / "Idea 3.md"


class TestDailyRegex:
    @pytest.mark.parametrize("name", ["2026-07-01.md", "1999-12-31.md"])
    def test_matches_bare_daily(self, name: str):
        assert notes.DAILY_RE.match(name)

    @pytest.mark.parametrize(
        "name",
        ["2026-07-01 title.md", "2026-7-1.md", "note.md", "2026-07-01.txt"],
    )
    def test_rejects_others(self, name: str):
        assert not notes.DAILY_RE.match(name)


def _run(*args: str, cwd: Path, env: dict | None = None):
    script = Path(__file__).parent / "scripts" / "notes.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


class TestResolveDirCli:
    def test_errors_when_unset(self, tmp_path: Path):
        r = _run("resolve-dir", cwd=tmp_path, env={"PATH": ""})
        assert r.returncode != 0
        assert "not set" in r.stderr

    def test_errors_when_missing_dir(self, tmp_path: Path):
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path / "nope")}
        r = _run("resolve-dir", cwd=tmp_path, env=env)
        assert r.returncode != 0
        assert "not an existing directory" in r.stderr

    def test_prints_dir(self, tmp_path: Path):
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path)}
        r = _run("resolve-dir", cwd=tmp_path, env=env)
        assert r.returncode == 0
        assert r.stdout.strip() == str(tmp_path)

    def test_fallback_notes_dir(self, tmp_path: Path):
        env = {"NOTES_DIR": str(tmp_path)}
        r = _run("resolve-dir", cwd=tmp_path, env=env)
        assert r.returncode == 0
        assert r.stdout.strip() == str(tmp_path)


class TestDailyListCli:
    def test_lists_only_bare_daily(self, tmp_path: Path):
        (tmp_path / "2026-07-01.md").write_text("x")
        (tmp_path / "2026-07-02 titled.md").write_text("x")
        (tmp_path / "other.md").write_text("x")
        r = _run("daily-list", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0
        listed = {Path(p).name for p in r.stdout.split()}
        assert listed == {"2026-07-01.md"}


class TestDailyRenameCli:
    def test_renames_with_title(self, tmp_path: Path):
        src = tmp_path / "2026-07-01.md"
        src.write_text("meeting stuff")
        r = _run("daily-rename", str(src), "Meeting with team", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        dst = tmp_path / "2026-07-01 Meeting with team.md"
        assert dst.is_file()
        assert not src.exists()
        assert r.stdout.strip() == str(dst)

    def test_rejects_non_daily(self, tmp_path: Path):
        src = tmp_path / "note.md"
        src.write_text("x")
        r = _run("daily-rename", str(src), "Title", cwd=tmp_path)
        assert r.returncode != 0
        assert "not a bare daily note" in r.stderr

    def test_uses_git_mv_when_tracked(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        src = tmp_path / "2026-07-01.md"
        src.write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
        r = _run("daily-rename", str(src), "Titled", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        staged = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
        ).stdout
        # git mv stages a rename (R), not add+delete
        assert "R" in staged

    def test_collision_gets_suffix(self, tmp_path: Path):
        (tmp_path / "2026-07-01 Titled.md").write_text("existing")
        src = tmp_path / "2026-07-01.md"
        src.write_text("x")
        r = _run("daily-rename", str(src), "Titled", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert (tmp_path / "2026-07-01 Titled 2.md").is_file()


class TestNotePathCli:
    def test_prints_unique_path(self, tmp_path: Path):
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path)}
        r = _run("note-path", "My idea", cwd=tmp_path, env=env)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == str(tmp_path / "My idea.md")

    def test_errors_on_empty_title(self, tmp_path: Path):
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path)}
        r = _run("note-path", "///", cwd=tmp_path, env=env)
        assert r.returncode != 0
        assert "empty" in r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
