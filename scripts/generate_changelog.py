#!/usr/bin/env python3
"""
Generate CHANGELOG.md from Git history, grouped by SemVer tags and Conventional
Commit prefixes. No external dependencies.

- Groups commits by release (vX.Y.Z tags). Non‑SemVer tags are ignored.
- Adds an "Unreleased" section (commits since the latest SemVer tag).
- Categorizes commits by common Conventional Commit types.

Usage:
  python scripts/generate_changelog.py > CHANGELOG.md

Environment:
  GIT_DIR (optional) — defaults to current repository.

Notes:
- This script reads commit subjects (first line).
- It ignores merge commits and empty messages.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
TYPE_RE = re.compile(r"^(feat|fix|docs|chore|refactor|perf|test|ci|build|revert)(?:\(.+?\))?:\s*(.+)$",
                     re.IGNORECASE)

CATEGORY_ORDER = [
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("ci", "CI"),
    ("build", "Build"),
    ("chore", "Chores"),
    ("revert", "Reverts"),
    ("other", "Other"),
]


@dataclass(order=True, frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> Optional["SemVer"]:
        m = SEMVER_TAG_RE.match(s)
        if not m:
            return None
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class Tag:
    name: str  # e.g., v1.2.3
    semver: SemVer
    date: str  # YYYY-MM-DD


@dataclass
class Release:
    tag: Optional[Tag]  # None for Unreleased
    commits_by_type: Dict[str, List[str]]


# ---- Git helpers -------------------------------------------------------------

def _git(*args: str, cwd: Optional[str] = None) -> str:
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[changelog] git {' '.join(args)} failed: {e.stderr}", file=sys.stderr)
        raise


def get_semver_tags() -> List[Tag]:
    # Get tags sorted by creation date ascending
    out = _git(
        "for-each-ref",
        "--sort=creatordate",
        "--format=%(refname:short)|%(creatordate:short)",
        "refs/tags",
    )
    tags: List[Tag] = []
    if not out:
        return tags
    for line in out.splitlines():
        try:
            name, date = line.split("|", 1)
        except ValueError:
            continue
        # Normalize like setuptools_scm: allow leading 'v'
        if not SEMVER_TAG_RE.match(name):
            continue
        semver = SemVer.parse(name)
        if not semver:
            continue
        # Use taggerdate if available; otherwise derive from tag commit
        if not date or date == "":
            date = _git("log", "-1", "--format=%ad", "--date=short", name)
        tags.append(Tag(name=name, semver=semver, date=date))
    # Ensure semver ascending order
    tags.sort(key=lambda t: (t.semver.major, t.semver.minor, t.semver.patch))
    return tags


def get_commits(range_expr: str) -> List[str]:
    # Return commit subject lines for non-merge commits in the given range
    if range_expr:
        args = ["log", "--no-merges", "--pretty=%s", range_expr]
    else:
        args = ["log", "--no-merges", "--pretty=%s"]
    out = _git(*args)
    commits = [line.strip() for line in out.splitlines() if line.strip()]
    return commits


def categorize(commits: Iterable[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {k: [] for k, _ in CATEGORY_ORDER}
    for msg in commits:
        m = TYPE_RE.match(msg)
        if m:
            type_key = m.group(1).lower()
            summary = m.group(2).strip()
            buckets[type_key].append(summary)
        else:
            buckets["other"].append(msg)
    return buckets


# ---- Build releases from tags -----------------------------------------------

def build_releases(tags: List[Tag]) -> List[Release]:
    releases: List[Release] = []

    # Unreleased: from last tag (if any) to HEAD
    if tags:
        last_tag = tags[-1].name
        unreleased_commits = get_commits(f"{last_tag}..HEAD")
    else:
        unreleased_commits = get_commits("HEAD")
    if unreleased_commits:
        releases.append(Release(tag=None, commits_by_type=categorize(unreleased_commits)))

    # Each tagged release: commits between previous tag (exclusive) and tag (inclusive)
    prev: Optional[Tag] = None
    for tag in tags:
        if prev is None:
            # From root to first tag
            # Using the tag commit only is not sufficient; include all reachable commits up to tag
            commits = get_commits(tag.name)
        else:
            commits = get_commits(f"{prev.name}..{tag.name}")
        releases.append(Release(tag=tag, commits_by_type=categorize(commits)))
        prev = tag

    # Sort releases: Unreleased first, then descending by semver
    def rel_key(r: Release) -> Tuple[int, int, int, int]:
        if r.tag is None:
            return (1, 0, 0, 0)  # Unreleased comes first by custom key (highest)
        s = r.tag.semver
        return (0, s.major, s.minor, s.patch)

    releases.sort(key=rel_key, reverse=True)
    return releases


# ---- Render Markdown ---------------------------------------------------------

def render(releases: List[Release]) -> str:
    lines: List[str] = []
    lines.append("# Changelog")
    lines.append("")
    lines.append("All notable changes to this project are documented here.")
    lines.append("This file is auto-generated from Git history. Do not edit by hand.")
    lines.append("")

    for rel in releases:
        if rel.tag is None:
            header = f"## [Unreleased]"
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            sub = f"(as of {date_str})"
            lines.append(f"{header} {sub}")
        else:
            header = f"## {rel.tag.name} - {rel.tag.date}"
            lines.append(header)
        # Categories
        empty = True
        for key, title in CATEGORY_ORDER:
            items = rel.commits_by_type.get(key, [])
            if not items:
                continue
            empty = False
            lines.append(f"### {title}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
        if empty:
            lines.append("(no notable changes)")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    # Ensure we are in a Git repo
    try:
        _git("rev-parse", "--git-dir")
    except Exception:
        print("This script must be run inside a Git repository.", file=sys.stderr)
        return 2

    tags = get_semver_tags()
    releases = build_releases(tags)
    md = render(releases)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
