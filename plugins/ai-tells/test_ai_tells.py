#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

"""Tests for the ai-tells plugin's helper script.

Nothing here downloads the Vale styles or shells out to Vale. The tests cover
the parts this script owns: where the cache lives, what the generated config
says, when a sync is needed, argument handling, and the failure messages.
"""

import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "scripts" / "ai_tells.py"

ai_tells = SourceFileLoader("ai_tells", str(SCRIPT)).load_module()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Keep the developer's own cache settings out of the tests."""
    monkeypatch.delenv("AI_TELLS_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)


class TestHomeDir:
    def test_ai_tells_home_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_TELLS_HOME", str(tmp_path / "chosen"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        assert ai_tells.home_dir() == tmp_path / "chosen"

    def test_falls_back_to_xdg_cache_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        assert ai_tells.home_dir() == tmp_path / "xdg" / "vale-ai-tells"

    def test_defaults_to_dot_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert ai_tells.home_dir() == tmp_path / ".cache" / "vale-ai-tells"

    def test_expands_tilde(self, monkeypatch):
        monkeypatch.setenv("AI_TELLS_HOME", "~/somewhere")
        assert ai_tells.home_dir() == Path.home() / "somewhere"


class TestRenderConfig:
    def test_styles_path_is_absolute(self, tmp_path):
        config = ai_tells.render_config(tmp_path)
        assert f"StylesPath = {tmp_path / 'styles'}" in config

    def test_pins_the_package_version(self, tmp_path):
        config = ai_tells.render_config(tmp_path)
        assert ai_tells.PACKAGE_VERSION in config
        assert ai_tells.RELEASE_URL in config

    def test_enables_only_the_prose_style(self, tmp_path):
        config = ai_tells.render_config(tmp_path)
        assert "BasedOnStyles = ai-tells" in config
        assert "ai-tells-commits" not in config
        assert "ai-tells-experimental" not in config

    def test_scopes_rules_to_markdown(self, tmp_path):
        assert "[*.md]" in ai_tells.render_config(tmp_path)


class TestWriteConfig:
    def test_writes_when_absent(self, tmp_path):
        assert ai_tells.write_config(tmp_path) is True
        assert ai_tells.config_path(tmp_path).exists()

    def test_creates_missing_parent_directories(self, tmp_path):
        home = tmp_path / "a" / "b"
        assert ai_tells.write_config(home) is True
        assert ai_tells.config_path(home).exists()

    def test_keeps_user_edits(self, tmp_path):
        ai_tells.write_config(tmp_path)
        edited = ai_tells.render_config(tmp_path) + "ai-tells.EmDashUsage = NO\n"
        ai_tells.config_path(tmp_path).write_text(edited, encoding="utf-8")

        assert ai_tells.write_config(tmp_path) is False
        assert "EmDashUsage = NO" in ai_tells.config_path(tmp_path).read_text()

    def test_force_overwrites(self, tmp_path):
        ai_tells.write_config(tmp_path)
        ai_tells.config_path(tmp_path).write_text("junk\n", encoding="utf-8")

        assert ai_tells.write_config(tmp_path, force=True) is True
        assert "junk" not in ai_tells.config_path(tmp_path).read_text()


def _fake_styles(home: Path, version: str) -> None:
    (ai_tells.styles_path(home) / ai_tells.PACKAGE_NAME).mkdir(parents=True)
    ai_tells.stamp_path(home).write_text(version + "\n", encoding="utf-8")


class TestSyncState:
    def test_needs_sync_when_nothing_downloaded(self, tmp_path):
        assert ai_tells.synced_version(tmp_path) is None
        assert ai_tells.needs_sync(tmp_path) is True

    def test_no_sync_needed_at_pinned_version(self, tmp_path):
        _fake_styles(tmp_path, ai_tells.PACKAGE_VERSION)
        assert ai_tells.needs_sync(tmp_path) is False

    def test_needs_sync_after_a_version_bump(self, tmp_path):
        _fake_styles(tmp_path, "v0.0.1")
        assert ai_tells.synced_version(tmp_path) == "v0.0.1"
        assert ai_tells.needs_sync(tmp_path) is True

    def test_needs_sync_when_styles_vanish(self, tmp_path):
        # A stamp on its own does not prove the styles are there; `vale sync`
        # wipes StylesPath, so a half-finished sync must not look complete.
        ai_tells.stamp_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        ai_tells.stamp_path(tmp_path).write_text(ai_tells.PACKAGE_VERSION)
        assert ai_tells.needs_sync(tmp_path) is True


class TestSplitOutputFlag:
    def test_default_is_line(self):
        assert ai_tells.split_output_flag(["a.md"]) == ("line", ["a.md"])

    def test_equals_form(self):
        assert ai_tells.split_output_flag(["--output=JSON", "a.md"]) == (
            "JSON",
            ["a.md"],
        )

    def test_separate_value_form(self):
        assert ai_tells.split_output_flag(["--output", "CLI", "a.md"]) == (
            "CLI",
            ["a.md"],
        )

    def test_flag_after_paths(self):
        assert ai_tells.split_output_flag(["a.md", "--output=CLI"]) == (
            "CLI",
            ["a.md"],
        )

    def test_missing_value_exits(self):
        with pytest.raises(SystemExit):
            ai_tells.split_output_flag(["--output"])


class TestRelabel:
    def test_replaces_the_temporary_path(self):
        line = "/tmp/x/draft.md:1:6:ai-tells.EmDashUsage:AI punctuation"
        relabelled = ai_tells.relabel(line, "/tmp/x/draft.md", "draft")
        assert relabelled.startswith("draft:1:6:")

    def test_leaves_other_text_alone(self):
        assert ai_tells.relabel("no paths here", "/tmp/x/draft.md", "draft") == (
            "no paths here"
        )


class TestRequireVale:
    def test_explains_how_to_install(self, monkeypatch):
        monkeypatch.setattr(ai_tells.shutil, "which", lambda _: None)
        with pytest.raises(SystemExit) as excinfo:
            ai_tells.require_vale()
        assert "brew install vale" in str(excinfo.value)

    def test_returns_the_path_when_present(self, monkeypatch):
        monkeypatch.setattr(ai_tells.shutil, "which", lambda _: "/usr/bin/vale")
        assert ai_tells.require_vale() == "/usr/bin/vale"


def run_cli(*args: str, home: Path, stdin: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ, AI_TELLS_HOME=str(home))
    env.pop("XDG_CACHE_HOME", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        input=stdin,
        env=env,
    )


class TestCommandLine:
    def test_config_path_reports_the_cache_location(self, tmp_path):
        result = run_cli("config-path", home=tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == str(tmp_path / "vale.ini")

    def test_status_reports_a_missing_download(self, tmp_path):
        result = run_cli("status", home=tmp_path)
        assert result.returncode == 0
        assert "not downloaded yet" in result.stdout

    def test_status_reports_a_stale_download(self, tmp_path):
        _fake_styles(tmp_path, "v0.0.1")
        result = run_cli("status", home=tmp_path)
        assert "run sync" in result.stdout

    def test_help_lists_the_subcommands(self, tmp_path):
        result = run_cli("--help", home=tmp_path)
        assert result.returncode == 0
        assert "check-text" in result.stdout

    def test_unknown_command_fails(self, tmp_path):
        result = run_cli("frobnicate", home=tmp_path)
        assert result.returncode != 0
        assert "Unknown command" in result.stderr

    def test_check_without_paths_fails(self, tmp_path):
        result = run_cli("check", home=tmp_path)
        assert result.returncode != 0
        assert "at least one file" in result.stderr

    def test_check_names_a_missing_file(self, tmp_path):
        result = run_cli("check", str(tmp_path / "nope.md"), home=tmp_path)
        assert result.returncode != 0
        assert "No such file" in result.stderr

    def test_check_text_rejects_file_arguments(self, tmp_path):
        result = run_cli("check-text", "a.md", home=tmp_path, stdin="hello")
        assert result.returncode != 0
        assert "reads stdin" in result.stderr

    def test_check_text_rejects_empty_input(self, tmp_path):
        result = run_cli("check-text", home=tmp_path, stdin="   \n")
        assert result.returncode != 0
        assert "no text on stdin" in result.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
