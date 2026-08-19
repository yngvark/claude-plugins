#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import os
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


def _vault(tmp_path: Path, names_to_body: dict[str, str]) -> Path:
    """Create a vault of notes; earlier keys get older mtimes."""
    for i, (name, body) in enumerate(names_to_body.items()):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
    return tmp_path


class TestIterNotes:
    def test_skips_hidden_folders(self, tmp_path: Path):
        _vault(
            tmp_path,
            {
                "Note.md": "x",
                "sub/Nested.md": "x",
                ".obsidian/plugin.md": "x",
                ".trash/Deleted.md": "x",
            },
        )
        found = {p.name for p in notes.iter_notes(tmp_path)}
        assert found == {"Note.md", "Nested.md"}


class TestFindNotes:
    def test_exact_name_beats_partial(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff extra.md": "x", "Handoff.md": "x"})
        found = notes.find_notes(tmp_path, "Handoff")
        assert [p.name for p in found] == ["Handoff.md", "Handoff extra.md"]

    def test_ignores_md_suffix_in_query(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff.md": "x"})
        assert notes.find_notes(tmp_path, "Handoff.md")[0].name == "Handoff.md"

    def test_case_insensitive(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff Renovate.md": "x"})
        assert notes.find_notes(tmp_path, "renovate")

    def test_matches_words_out_of_order(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff - Renovate automerge working hours.md": "x"})
        assert notes.find_notes(tmp_path, "renovate handoff")

    def test_no_match_returns_empty(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff.md": "x"})
        assert notes.find_notes(tmp_path, "kubernetes") == []

    def test_newest_first_among_equal_scores(self, tmp_path: Path):
        _vault(tmp_path, {"a idea.md": "x", "b idea.md": "x"})
        found = notes.find_notes(tmp_path, "idea")
        assert [p.name for p in found] == ["b idea.md", "a idea.md"]

    def test_respects_limit(self, tmp_path: Path):
        _vault(tmp_path, {f"idea {i}.md": "x" for i in range(5)})
        assert len(notes.find_notes(tmp_path, "idea", limit=2)) == 2

    def test_finds_notes_in_subfolders(self, tmp_path: Path):
        _vault(tmp_path, {"sub/Deep idea.md": "x"})
        assert notes.find_notes(tmp_path, "deep")[0].name == "Deep idea.md"


class TestSearchNotes:
    def test_finds_text_in_body(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "nothing", "B.md": "line one\nautomerge hours\n"})
        hits = notes.search_notes(tmp_path, "AUTOMERGE")
        assert [(p.name, n) for p, n, _ in hits] == [("B.md", 2)]
        assert hits[0][2] == "automerge hours"

    def test_one_hit_per_note(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "dup\ndup\ndup\n"})
        assert len(notes.search_notes(tmp_path, "dup")) == 1

    def test_empty_query_finds_nothing(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "text"})
        assert notes.search_notes(tmp_path, "  ") == []

    def test_truncates_long_lines(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "needle " + "x" * 500})
        assert len(notes.search_notes(tmp_path, "needle")[0][2]) == notes.SNIPPET_LEN


class TestRecentNotes:
    def test_newest_first(self, tmp_path: Path):
        _vault(tmp_path, {"old.md": "x", "mid.md": "x", "new.md": "x"})
        assert [p.name for p in notes.recent_notes(tmp_path)] == [
            "new.md",
            "mid.md",
            "old.md",
        ]

    def test_respects_limit(self, tmp_path: Path):
        _vault(tmp_path, {f"n{i}.md": "x" for i in range(5)})
        assert len(notes.recent_notes(tmp_path, limit=2)) == 2


class TestTakeLimit:
    def test_separate_value(self):
        assert notes.take_limit(["q", "--limit", "3"], 20) == (3, ["q"])

    def test_equals_form(self):
        assert notes.take_limit(["q", "--limit=3"], 20) == (3, ["q"])

    def test_default_when_absent(self):
        assert notes.take_limit(["q"], 20) == (20, ["q"])


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


class TestFindCli:
    def test_prints_paths_from_env_dir(self, tmp_path: Path):
        _vault(tmp_path, {"Handoff Renovate.md": "x", "Other.md": "x"})
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path)}
        r = _run("find", "renovate", cwd=tmp_path, env=env)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == str(tmp_path / "Handoff Renovate.md")

    def test_dir_argument_overrides_env(self, tmp_path: Path):
        vault = _vault(tmp_path / "vault", {"Idea.md": "x"})
        r = _run("find", "idea", str(vault), cwd=tmp_path, env={"PATH": ""})
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == str(vault / "Idea.md")

    def test_no_match_prints_nothing_and_succeeds(self, tmp_path: Path):
        _vault(tmp_path, {"Idea.md": "x"})
        r = _run("find", "nope", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_requires_a_query(self, tmp_path: Path):
        r = _run("find", cwd=tmp_path, env={"PATH": ""})
        assert r.returncode != 0
        assert "usage" in r.stderr

    def test_rejects_bad_limit(self, tmp_path: Path):
        r = _run("find", "q", "--limit", "0", cwd=tmp_path, env={"PATH": ""})
        assert r.returncode != 0
        assert "positive integer" in r.stderr


class TestSearchCli:
    def test_prints_path_line_and_snippet(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "intro\nautomerge hours\n"})
        r = _run("search", "automerge", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == f"{tmp_path / 'A.md'}:2: automerge hours"


class TestRecentCli:
    def test_lists_newest_first(self, tmp_path: Path):
        _vault(tmp_path, {"old.md": "x", "new.md": "x"})
        r = _run("recent", "--limit", "1", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == str(tmp_path / "new.md")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
