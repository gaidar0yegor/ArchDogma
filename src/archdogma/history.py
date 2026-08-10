"""Git history extraction — the Tier 3 substrate.

Tiers 1 and 2 read the code as it stands. They cannot tell a file that is
load-bearing from a file that is merely large, because that difference is
not in the source — it is in what happened to the source over four years.

This module shells out to `git log` once and turns it into per-file facts:
how often a file changed, when it last changed, how many people have
touched it. Combined with the Tier 2 import graph, that answers the
question a linter structurally cannot ask: *which files does everything
depend on that nobody dares to change?*

Deliberate limits, stated up front:

  - Renames are not followed. `git log --follow` works on one path at a
    time and would turn one subprocess call into one per file. A file
    renamed last month therefore looks one month old. `RepoHistory.follows_
    renames` is False so callers can say so rather than imply otherwise.
  - Merge commits are excluded. Counting a merge as a change to every file
    it touches would make integration branches look like churn.
  - "Now" is the newest commit in the repository, not wall-clock time.
    A scan of the same commit gives the same answer next year, which is
    what makes a CI threshold meaningful. `as_of` carries it explicitly.
  - Whitespace-only and formatter commits count the same as real changes.
    Churn here means "was touched", not "was meaningfully changed".
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Record separator and field separator chosen from control characters that
# cannot appear in a commit header we care about.
_REC = "\x01"
_FLD = "\x02"

_LOG_FORMAT = f"{_REC}%H{_FLD}%at{_FLD}%aN"

SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class FileHistory:
    """Change history of one file, relative to the repository root."""

    path: str
    commits: int
    first_commit: int  # epoch seconds
    last_commit: int  # epoch seconds
    authors: frozenset[str] = frozenset()
    lines_added: int = 0
    lines_deleted: int = 0

    @property
    def author_count(self) -> int:
        return len(self.authors)


@dataclass(frozen=True)
class RepoHistory:
    """Per-file history for a whole repository, plus the reference instant."""

    root: Path
    as_of: int  # epoch of the newest commit — the "now" all ages are measured from
    files: dict[str, FileHistory] = field(default_factory=dict)
    follows_renames: bool = False

    def for_path(self, path: Path) -> FileHistory | None:
        """Look up history by absolute or repo-relative path."""
        try:
            rel = str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            rel = str(path)
        return self.files.get(rel)

    def days_since_change(self, path: Path) -> int | None:
        """Whole days between the file's last commit and `as_of`."""
        entry = self.for_path(path)
        if entry is None:
            return None
        return max(0, (self.as_of - entry.last_commit) // SECONDS_PER_DAY)

    def commit_counts(self) -> list[int]:
        """Every file's commit count, ascending — the repo's churn distribution."""
        return sorted(f.commits for f in self.files.values())

    def churn_percentile(self, path: Path) -> float | None:
        """Where this file sits in the repo's churn distribution, 0.0–1.0.

        Repo-relative on purpose: "20 commits" means something different in
        a three-month project than in a ten-year one, so an absolute churn
        threshold does not transfer between codebases. A percentile does.
        """
        entry = self.for_path(path)
        if entry is None:
            return None
        counts = self.commit_counts()
        if not counts:
            return None
        at_or_below = sum(1 for c in counts if c <= entry.commits)
        return at_or_below / len(counts)


class GitUnavailable(RuntimeError):
    """Raised when a path is not a git work tree, or git is not installed."""


def _run_git(root: Path, args: list[str], timeout: int = 120) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:  # git not on PATH
        raise GitUnavailable("git executable not found on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise GitUnavailable(f"git timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise GitUnavailable(proc.stderr.strip() or "git exited non-zero")
    return proc.stdout


def repo_root(path: Path) -> Path | None:
    """Repository root containing `path`, or None if it is not in a work tree."""
    start = path if path.is_dir() else path.parent
    try:
        out = _run_git(start, ["rev-parse", "--show-toplevel"])
    except GitUnavailable:
        return None
    top = out.strip()
    return Path(top).resolve() if top else None


def _parse_numstat_path(raw: str) -> str:
    """Normalise a numstat path, resolving git's inline rename notation.

    git writes renames as `old => new` or `pkg/{old => new}/file.py`. We keep
    the destination, which is the path the file has today.
    """
    if "=>" not in raw:
        return raw
    if "{" in raw and "}" in raw:
        prefix, rest = raw.split("{", 1)
        inner, suffix = rest.split("}", 1)
        new = inner.split("=>", 1)[1].strip()
        return f"{prefix}{new}{suffix}".replace("//", "/")
    return raw.split("=>", 1)[1].strip()


def parse_log(output: str) -> tuple[dict[str, FileHistory], int]:
    """Parse `git log --numstat` output into per-file history.

    Returns (files, as_of) where `as_of` is the newest commit timestamp seen.
    Binary files (numstat writes `-` for both counts) contribute a commit but
    no line counts.
    """
    commits: dict[str, int] = {}
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    authors: dict[str, set[str]] = {}
    added: dict[str, int] = {}
    deleted: dict[str, int] = {}
    newest = 0

    for record in output.split(_REC):
        record = record.strip("\n")
        if not record:
            continue
        header, _, body = record.partition("\n")
        parts = header.split(_FLD)
        if len(parts) < 3:
            continue
        _sha, ts_raw, author = parts[0], parts[1], parts[2]
        try:
            timestamp = int(ts_raw)
        except ValueError:
            continue
        newest = max(newest, timestamp)

        for line in body.splitlines():
            if not line.strip():
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            add_raw, del_raw, raw_path = cols[0], cols[1], "\t".join(cols[2:])
            path = _parse_numstat_path(raw_path.strip())
            if not path:
                continue

            commits[path] = commits.get(path, 0) + 1
            authors.setdefault(path, set()).add(author)
            if path not in first or timestamp < first[path]:
                first[path] = timestamp
            if path not in last or timestamp > last[path]:
                last[path] = timestamp
            if add_raw != "-":
                added[path] = added.get(path, 0) + int(add_raw)
            if del_raw != "-":
                deleted[path] = deleted.get(path, 0) + int(del_raw)

    files = {
        path: FileHistory(
            path=path,
            commits=count,
            first_commit=first[path],
            last_commit=last[path],
            authors=frozenset(authors.get(path, ())),
            lines_added=added.get(path, 0),
            lines_deleted=deleted.get(path, 0),
        )
        for path, count in commits.items()
    }
    return files, newest


def load_history(path: Path, timeout: int = 120) -> RepoHistory | None:
    """Read the git history for the repository containing `path`.

    Returns None when there is no repository, when git is unavailable, or
    when the repository has no commits. None means "we do not know", and
    Tier 3 detectors stay silent rather than guessing — a fresh clone with
    `--depth 1` must not make every file look brand new and unowned.
    """
    root = repo_root(path)
    if root is None:
        return None
    try:
        output = _run_git(
            root,
            ["log", "--no-merges", "--numstat", f"--format=format:{_LOG_FORMAT}"],
            timeout=timeout,
        )
    except GitUnavailable:
        return None

    files, as_of = parse_log(output)
    if not files:
        return None
    return RepoHistory(root=root, as_of=as_of, files=files)
