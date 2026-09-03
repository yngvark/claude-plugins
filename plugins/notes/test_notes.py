#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import datetime
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


class TestDatePrefixRegex:
    @pytest.mark.parametrize(
        "name", ["2026-07-01.md", "2026-07-01 Standup.md", "1999-12-31 x y.md"]
    )
    def test_matches_dated_names(self, name: str):
        assert notes.has_date_prefix(name)

    @pytest.mark.parametrize(
        "name",
        ["Standup.md", "2026-7-1 Standup.md", "20260701 Standup.md", "x 2026-07-01.md"],
    )
    def test_rejects_undated_names(self, name: str):
        assert not notes.has_date_prefix(name)

    def test_rejects_date_glued_to_title(self):
        # A space (or nothing) must follow the date, so this is not a prefix.
        assert not notes.has_date_prefix("2026-07-01Standup.md")


class TestNoteDate:
    def test_mtime_source(self, tmp_path: Path):
        p = tmp_path / "n.md"
        p.write_text("x")
        stamp = datetime.datetime(2026, 3, 4, 12, 0).timestamp()
        os.utime(p, (stamp, stamp))
        assert notes.note_date(p, "mtime") == "2026-03-04"

    def test_birth_falls_back_to_mtime(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "n.md"
        p.write_text("x")
        stamp = datetime.datetime(2026, 3, 4, 12, 0).timestamp()
        os.utime(p, (stamp, stamp))
        real_stat = Path.stat

        class NoBirthTime:
            """A stat result on a filesystem that records no creation time."""

            def __init__(self, st):
                self.st_mtime = st.st_mtime

        monkeypatch.setattr(Path, "stat", lambda self, **kw: NoBirthTime(real_stat(self)))
        assert notes.note_date(p, "birth") == "2026-03-04"

    def test_rejects_unknown_source(self, tmp_path: Path):
        p = tmp_path / "n.md"
        p.write_text("x")
        with pytest.raises(ValueError):
            notes.note_date(p, "nonsense")

    def test_git_source_uses_adding_commit(self, tmp_path: Path):
        _git_init(tmp_path)
        p = tmp_path / "n.md"
        p.write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "add"],
            cwd=tmp_path,
            check=True,
            env={**os.environ, "GIT_AUTHOR_DATE": "2026-01-15T10:00:00"},
        )
        assert notes.note_date(p, "git") == "2026-01-15"

    def test_git_source_falls_back_when_untracked(self, tmp_path: Path):
        p = tmp_path / "n.md"
        p.write_text("x")
        stamp = datetime.datetime(2026, 3, 4, 12, 0).timestamp()
        os.utime(p, (stamp, stamp))
        # No repository at all, so there is no adding commit to read.
        assert notes.note_date(p, "git") == notes.note_date(p, "birth")


class TestUndatedNotes:
    def test_lists_only_undated(self, tmp_path: Path):
        _vault(tmp_path, {"Standup.md": "x", "2026-07-01 Dated.md": "x"})
        assert [p.name for p in notes.undated_notes(tmp_path)] == ["Standup.md"]

    def test_skips_default_excludes(self, tmp_path: Path):
        _vault(
            tmp_path,
            {"CLAUDE.md": "x", "AGENTS.md": "x", "README.md": "x", "Note.md": "x"},
        )
        assert [p.name for p in notes.undated_notes(tmp_path)] == ["Note.md"]

    def test_extra_excludes(self, tmp_path: Path):
        _vault(tmp_path, {"Keep.md": "x", "Note.md": "x"})
        found = notes.undated_notes(tmp_path, excludes=("Keep.md",))
        assert [p.name for p in found] == ["Note.md"]

    def test_top_level_only_by_default(self, tmp_path: Path):
        _vault(tmp_path, {"Note.md": "x", "sub/Deep.md": "x"})
        assert [p.name for p in notes.undated_notes(tmp_path)] == ["Note.md"]

    def test_recursive_includes_subfolders(self, tmp_path: Path):
        _vault(tmp_path, {"Note.md": "x", "sub/Deep.md": "x"})
        found = notes.undated_notes(tmp_path, recursive=True)
        assert {p.name for p in found} == {"Note.md", "Deep.md"}

    def test_recursive_skips_hidden_folders(self, tmp_path: Path):
        _vault(tmp_path, {"Note.md": "x", ".obsidian/Plugin.md": "x"})
        found = notes.undated_notes(tmp_path, recursive=True)
        assert [p.name for p in found] == ["Note.md"]


class TestLinkRefs:
    @pytest.mark.parametrize(
        "body",
        [
            "see [[Demo]] here",
            "see [[Demo|the demo]]",
            "see [[Demo#Agenda]]",
            "embed ![[Demo]]",
            "see [[ki/Demo]]",
            "see [the demo](Demo.md)",
            "see [the demo](ki/Demo.md#Agenda)",
            "see [the demo](DEMO.md)",
        ],
    )
    def test_finds_link_forms(self, tmp_path: Path, body: str):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": body})
        hits = notes.link_refs(tmp_path, "Demo")
        assert [p.name for p, _, _ in hits] == ["Other.md"]

    def test_finds_percent_encoded_link(self, tmp_path: Path):
        _vault(tmp_path, {"My note.md": "x", "Other.md": "[x](My%20note.md)"})
        assert notes.link_refs(tmp_path, "My note")

    def test_accepts_a_path_as_target(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "[[Demo]]"})
        assert notes.link_refs(tmp_path, str(tmp_path / "Demo.md"))

    def test_ignores_similar_names(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "[[Demo notes]] and [[Predemo]]"})
        assert notes.link_refs(tmp_path, "Demo") == []

    def test_ignores_plain_text_mention(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "the Demo went fine"})
        assert notes.link_refs(tmp_path, "Demo") == []

    def test_skips_the_target_itself(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "[[Demo]] links to itself"})
        assert notes.link_refs(tmp_path, "Demo") == []

    def test_reports_every_line(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "[[Demo]]\nplain\n[[Demo]]\n"})
        assert [n for _, n, _ in notes.link_refs(tmp_path, "Demo")] == [1, 3]


class TestTakeRepeated:
    def test_collects_every_occurrence(self):
        argv = ["--exclude", "a", "x", "--exclude=b"]
        assert notes.take_repeated(argv, "--exclude") == (["a", "b"], ["x"])

    def test_absent_flag_returns_empty(self):
        assert notes.take_repeated(["x"], "--exclude") == ([], ["x"])


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


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
    def test_falls_back_to_cwd_when_unset(self, tmp_path: Path):
        r = _run("resolve-dir", cwd=tmp_path, env={"PATH": ""})
        assert r.returncode == 0
        assert Path(r.stdout.strip()).resolve() == tmp_path.resolve()

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
        _git_init(tmp_path)
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


class TestUndatedListCli:
    def test_prints_date_and_path(self, tmp_path: Path):
        p = tmp_path / "Standup.md"
        p.write_text("x")
        (tmp_path / "2026-07-01 Dated.md").write_text("x")
        stamp = datetime.datetime(2026, 3, 4, 12, 0).timestamp()
        os.utime(p, (stamp, stamp))
        r = _run("undated-list", "--date-source", "mtime", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout == f"2026-03-04\t{p}\n"

    def test_rejects_unknown_date_source(self, tmp_path: Path):
        r = _run("undated-list", "--date-source", "guess", str(tmp_path), cwd=tmp_path)
        assert r.returncode != 0
        assert "--date-source must be one of" in r.stderr

    def test_exclude_flag(self, tmp_path: Path):
        (tmp_path / "Keep.md").write_text("x")
        (tmp_path / "Note.md").write_text("x")
        r = _run("undated-list", "--exclude", "Keep.md", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert [line.split("\t")[1] for line in r.stdout.splitlines()] == [
            str(tmp_path / "Note.md")
        ]

    def test_uses_env_dir_when_no_dir_given(self, tmp_path: Path):
        (tmp_path / "Note.md").write_text("x")
        env = {"OBSIDIAN_NOTES_DIR": str(tmp_path)}
        r = _run("undated-list", cwd=tmp_path, env=env)
        assert r.returncode == 0, r.stderr
        assert str(tmp_path / "Note.md") in r.stdout


class TestDatePrefixCli:
    def test_renames_with_file_date(self, tmp_path: Path):
        src = tmp_path / "Standup.md"
        src.write_text("x")
        stamp = datetime.datetime(2026, 3, 4, 12, 0).timestamp()
        os.utime(src, (stamp, stamp))
        r = _run("date-prefix", str(src), "--date-source", "mtime", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        dst = tmp_path / "2026-03-04 Standup.md"
        assert dst.is_file()
        assert not src.exists()
        assert r.stdout.strip() == str(dst)

    def test_explicit_date_wins(self, tmp_path: Path):
        src = tmp_path / "Standup.md"
        src.write_text("x")
        r = _run("date-prefix", str(src), "--date", "2020-01-02", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert (tmp_path / "2020-01-02 Standup.md").is_file()

    def test_rejects_malformed_date(self, tmp_path: Path):
        src = tmp_path / "Standup.md"
        src.write_text("x")
        r = _run("date-prefix", str(src), "--date", "2/1/2020", cwd=tmp_path)
        assert r.returncode != 0
        assert "must be yyyy-mm-dd" in r.stderr
        assert src.is_file()

    def test_refuses_already_dated_file(self, tmp_path: Path):
        src = tmp_path / "2026-07-01 Standup.md"
        src.write_text("x")
        r = _run("date-prefix", str(src), cwd=tmp_path)
        assert r.returncode != 0
        assert "already starts with a date" in r.stderr
        assert src.is_file()

    def test_errors_on_missing_file(self, tmp_path: Path):
        r = _run("date-prefix", str(tmp_path / "nope.md"), cwd=tmp_path)
        assert r.returncode != 0
        assert "does not exist" in r.stderr

    def test_collision_gets_suffix(self, tmp_path: Path):
        (tmp_path / "2020-01-02 Standup.md").write_text("existing")
        src = tmp_path / "Standup.md"
        src.write_text("x")
        r = _run("date-prefix", str(src), "--date", "2020-01-02", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert (tmp_path / "2020-01-02 Standup 2.md").read_text() == "x"
        assert (tmp_path / "2020-01-02 Standup.md").read_text() == "existing"

    def test_uses_git_mv_when_tracked(self, tmp_path: Path):
        _git_init(tmp_path)
        src = tmp_path / "Standup.md"
        src.write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
        r = _run("date-prefix", str(src), "--date", "2020-01-02", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        staged = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
        ).stdout
        assert "R" in staged


class TestLinkRefsCli:
    def test_prints_target_path_line_and_snippet(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "intro\nsee [[Demo]] here\n"})
        r = _run("link-refs", "Demo", "--dir", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == (
            f"Demo\t{tmp_path / 'Other.md'}:2: see [[Demo]] here"
        )

    def test_several_targets_at_once(self, tmp_path: Path):
        _vault(tmp_path, {"A.md": "x", "B.md": "x", "C.md": "[[A]] and [[B]]"})
        r = _run("link-refs", "A", "B", "--dir", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert [line.split("\t")[0] for line in r.stdout.splitlines()] == ["A", "B"]

    def test_no_links_prints_nothing_and_succeeds(self, tmp_path: Path):
        _vault(tmp_path, {"Demo.md": "x", "Other.md": "no links"})
        r = _run("link-refs", "Demo", "--dir", str(tmp_path), cwd=tmp_path)
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_requires_a_target(self, tmp_path: Path):
        r = _run("link-refs", "--dir", str(tmp_path), cwd=tmp_path)
        assert r.returncode != 0
        assert "usage" in r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
