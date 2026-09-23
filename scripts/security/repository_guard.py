#!/usr/bin/env python3
"""Fail on common committed secret shapes or non-synthetic demo PDF metadata.

This is a bounded public-repository guard, not a DLP engine or a replacement for
GitHub/Google secret-scanning capabilities.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]

TEXT_SUFFIXES = {
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".ps1",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "evals/results",
}
SYNTHETIC_PDF_AUTHORS = {"", "Enterprise AI Assistant Demo"}
SYNTHETIC_PDF_CREATORS = {"", "Enterprise AI Assistant"}

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "GitHub token": re.compile(
        r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pour]_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9._-]{36,})\b"
    ),
}


def _excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(part in rel.split("/") for part in EXCLUDED_PARTS) or rel.startswith(
        "evals/results/"
    )


def scan_text() -> list[str]:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _excluded(path):
            continue
        if path.name == ".env.example" or path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    failures.append(
                        f"{path.relative_to(ROOT)}: possible committed {label}"
                    )
    return failures


def scan_pdf_metadata() -> list[str]:
    failures: list[str] = []
    for path in (ROOT / "data" / "documents").glob("*.pdf"):
        metadata = PdfReader(str(path)).metadata or {}
        author = str(metadata.get("/Author") or "").strip()
        creator = str(metadata.get("/Creator") or "").strip()
        if author not in SYNTHETIC_PDF_AUTHORS:
            failures.append(
                f"{path.relative_to(ROOT)}: PDF Author metadata is not synthetic"
            )
        if creator not in SYNTHETIC_PDF_CREATORS:
            failures.append(
                f"{path.relative_to(ROOT)}: PDF Creator metadata is not synthetic"
            )
    return failures


def main() -> int:
    failures = scan_text() + scan_pdf_metadata()
    if failures:
        print("Public repository guard failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Public repository guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
