"""Unit tests for git history extraction.

Split in two: `parse_log` is tested against literal git output, which is
fast and pins the format exactly; the rest is tested against real
repositories built with fixed commit timestamps, because the parts that
break in practice are the ones that talk to git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from archdogma.history import (
    _REC,
    FileHistory,
    RepoHistory,
    _parse_numstat_path,
    load_history,
    parse_log,
    repo_root,
)

# Fixed instants so age assertions are exact.
JAN_2020 = 1577836800
JAN_2021 = 1609459200
JAN_2024 = 1704067200


def record(sha: str, ts: int, author: str, files: list[tuple[str, str, str]]) -> str:
    """Build one git-log record in the format `parse_log` expects."""
    header = f"{_REC}{sha}\x02{ts}\x02{author}"
    body = "".join(f"\n{a}\t{d}\t{p}" for a, d, p in files)
    return header + body


# ---------------------------------------------------------------------------
# parse_log
# ---------------------------------------------------------------------------


def test_parse_empty_output() -> None:
    files, as_of, _co = parse_log("")
    assert files == {}
    assert as_of == 0


def test_parse_single_commit() -> None:
    files, as_of, _co = parse_log(record("abc", JAN_2020, "Ada", [("10", "2", "a.py")]))
    assert as_of == JAN_2020
    assert files["a.py"].commits == 1
    assert files["a.py"].lines_added == 10
    assert files["a.py"].lines_deleted == 2
    assert files["a.py"].authors == frozenset({"Ada"})


def test_parse_accumulates_across_commits() -> None:
    log = record("a", JAN_2020, "Ada", [("10", "0", "a.py")]) + record(
        "b", JAN_2021, "Bob", [("5", "3", "a.py")]
    )
    files, as_of, _co = parse_log(log)
    entry = files["a.py"]
    assert entry.commits == 2
    assert entry.lines_added == 15
    assert entry.lines_deleted == 3
    assert entry.authors == frozenset({"Ada", "Bob"})
    assert entry.first_commit == JAN_2020
    assert entry.last_commit == JAN_2021
    assert as_of == JAN_2021


def test_parse_as_of_is_the_newest_commit_regardless_of_order() -> None:
    log = record("new", JAN_2024, "Ada", [("1", "0", "a.py")]) + record(
        "old", JAN_2020, "Ada", [("1", "0", "a.py")]
    )
    _files, as_of, _co = parse_log(log)
    assert as_of == JAN_2024


def test_parse_multiple_files_in_one_commit() -> None:
    log = record("a", JAN_2020, "Ada", [("1", "0", "a.py"), ("2", "0", "b.py")])
    files, _as_of, _co = parse_log(log)
    assert set(files) == {"a.py", "b.py"}


def test_parse_binary_file_counts_commit_not_lines() -> None:
    files, _as_of, _co = parse_log(record("a", JAN_2020, "Ada", [("-", "-", "logo.png")]))
    assert files["logo.png"].commits == 1
    assert files["logo.png"].lines_added == 0


def test_parse_ignores_malformed_header() -> None:
    files, _as_of, _co = parse_log(f"{_REC}only-a-sha\n1\t0\ta.py")
    assert files == {}


def test_parse_ignores_non_integer_timestamp() -> None:
    files, _as_of, _co = parse_log(f"{_REC}abc\x02not-a-number\x02Ada\n1\t0\ta.py")
    assert files == {}


def test_parse_handles_path_with_spaces() -> None:
    files, _as_of, _co = parse_log(record("a", JAN_2020, "Ada", [("1", "0", "my dir/x.py")]))
    assert "my dir/x.py" in files


# ---------------------------------------------------------------------------
# Rename notation
# ---------------------------------------------------------------------------


def test_plain_path_is_unchanged() -> None:
    assert _parse_numstat_path("src/app.py") == "src/app.py"


def test_simple_rename_keeps_destination() -> None:
    assert _parse_numstat_path("old.py => new.py") == "new.py"


def test_braced_rename_keeps_destination() -> None:
    assert _parse_numstat_path("src/{old => new}/app.py") == "src/new/app.py"


def test_braced_rename_at_leaf() -> None:
    assert _parse_numstat_path("src/{a.py => b.py}") == "src/b.py"


# ---------------------------------------------------------------------------
# RepoHistory arithmetic
# ---------------------------------------------------------------------------


def _history(**files: FileHistory) -> RepoHistory:
    return RepoHistory(
        root=Path("/repo"),
        as_of=JAN_2024,
        files={f.path: f for f in files.values()},
    )


def test_days_since_change_uses_as_of_not_wall_clock() -> None:
    hist = _history(
        a=FileHistory(path="a.py", commits=1, first_commit=JAN_2021, last_commit=JAN_2021)
    )
    expected = (JAN_2024 - JAN_2021) // 86400
    assert hist.days_since_change(Path("/repo/a.py")) == expected


def test_days_since_change_unknown_file_is_none() -> None:
    assert _history().days_since_change(Path("/repo/nope.py")) is None


def test_churn_percentile_orders_files() -> None:
    hist = _history(
        low=FileHistory(path="low.py", commits=1, first_commit=1, last_commit=1),
        mid=FileHistory(path="mid.py", commits=5, first_commit=1, last_commit=1),
        high=FileHistory(path="high.py", commits=50, first_commit=1, last_commit=1),
    )
    assert hist.churn_percentile(Path("/repo/high.py")) == 1.0
    assert hist.churn_percentile(Path("/repo/low.py")) < 0.5


def test_churn_percentile_unknown_file_is_none() -> None:
    assert _history().churn_percentile(Path("/repo/nope.py")) is None


def test_author_count_derives_from_the_set() -> None:
    entry = FileHistory(
        path="a.py",
        commits=3,
        first_commit=1,
        last_commit=2,
        authors=frozenset({"Ada", "Bob"}),
    )
    assert entry.author_count == 2


# ---------------------------------------------------------------------------
# Real repositories
# ---------------------------------------------------------------------------


def git(root: Path, *args: str, when: int | None = None, author: str = "Ada") -> None:
    env_args = [
        "-c",
        f"user.name={author}",
        "-c",
        f"user.email={author.lower()}@example.com",
    ]
    env = None
    if when is not None:
        import os

        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = f"{when} +0000"
        env["GIT_COMMITTER_DATE"] = f"{when} +0000"
    subprocess.run(
        ["git", "-C", str(root), *env_args, *args],
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "-C", str(root), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    return root


def commit(
    root: Path, name: str, content: str, when: int, author: str = "Ada"
) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-q", "-m", f"touch {name}", when=when, author=author)


def test_repo_root_finds_the_work_tree(repo: Path) -> None:
    commit(repo, "a.py", "x = 1\n", JAN_2020)
    nested = repo / "pkg"
    nested.mkdir(exist_ok=True)
    assert repo_root(nested) == repo.resolve()


def test_repo_root_outside_a_repository_is_none(tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    # A parent of tmp_path is not a git repo on any supported platform.
    assert repo_root(outside) is None


def test_load_history_on_empty_repo_is_none(repo: Path) -> None:
    assert load_history(repo) is None


def test_load_history_reads_commits(repo: Path) -> None:
    commit(repo, "a.py", "x = 1\n", JAN_2020)
    commit(repo, "a.py", "x = 2\n", JAN_2021)
    hist = load_history(repo)
    assert hist is not None
    assert hist.files["a.py"].commits == 2
    assert hist.as_of == JAN_2021


def test_load_history_tracks_distinct_authors(repo: Path) -> None:
    commit(repo, "a.py", "x = 1\n", JAN_2020, author="Ada")
    commit(repo, "a.py", "x = 2\n", JAN_2021, author="Bob")
    hist = load_history(repo)
    assert hist is not None
    assert hist.files["a.py"].author_count == 2


def test_load_history_age_is_measured_from_newest_commit(repo: Path) -> None:
    commit(repo, "old.py", "x = 1\n", JAN_2020)
    commit(repo, "new.py", "y = 1\n", JAN_2024)
    hist = load_history(repo)
    assert hist is not None
    assert hist.days_since_change(repo / "new.py") == 0
    assert hist.days_since_change(repo / "old.py") == (JAN_2024 - JAN_2020) // 86400


def test_load_history_declares_it_does_not_follow_renames(repo: Path) -> None:
    commit(repo, "a.py", "x = 1\n", JAN_2020)
    hist = load_history(repo)
    assert hist is not None
    assert hist.follows_renames is False
