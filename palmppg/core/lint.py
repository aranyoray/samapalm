"""Vocabulary lint: the study never describes anything with the banned terms.

Banned (word-boundary, case-insensitive): validated, medical-grade, diagnos*, generalis*/generaliz*,
"external validation". The lint runs as a unit test over every text file in the repository and over
every generated report. The only files allowed to contain the patterns are this module and the test
that exercises it.
"""
from __future__ import annotations

import re
from pathlib import Path

BANNED_PATTERNS = [
    re.compile(r"\bvalidated\b", re.I),
    re.compile(r"\bmedical[- ]grade\b", re.I),
    re.compile(r"\bdiagnos(?:tic|tics|e|es|ed|is|ing)\b", re.I),
    re.compile(r"\bgenerali[sz](?:e|es|ed|ing|ation|ability|able)\b", re.I),
    re.compile(r"\bexternal validation\b", re.I),
]

ALLOWLIST_FILES = {"palmppg/core/lint.py", "tests/test_core_lint.py"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".txt", ".html", ".csv", ".json", ".sh", ".kt", ".toml", ".cfg", ".ini", ".rst", ".tex"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "mlruns", ".pytest_cache", ".ruff_cache", "work", ".mypy_cache",
             # generated trees: Gradle build output carries vendor strings such as
             # androidx.work.diagnostics that are not ours to reword
             "build", ".gradle"}


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Return (line_no, matched_text, line) for every banned hit."""
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        for pat in BANNED_PATTERNS:
            for m in pat.finditer(line):
                hits.append((i, m.group(0), line.strip()))
    return hits


def scan_path(root: Path, extra_allow: set[str] | None = None) -> dict[str, list[tuple[int, str, str]]]:
    root = Path(root)
    allow = set(ALLOWLIST_FILES) | set(extra_allow or ())
    out: dict[str, list] = {}
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = p.relative_to(root).as_posix()
        if rel in allow:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(text)
        if hits:
            out[rel] = hits
    return out


def assert_clean_text(text: str, label: str = "text") -> None:
    hits = scan_text(text)
    if hits:
        first = hits[0]
        raise ValueError(f"banned vocabulary in {label}: line {first[0]} '{first[1]}' ({len(hits)} hits)")
