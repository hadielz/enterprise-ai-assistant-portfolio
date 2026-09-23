"""Public repository demo data must use synthetic document metadata."""

from pathlib import Path

from pypdf import PdfReader

from scripts.security.repository_guard import SECRET_PATTERNS


ALLOWED_AUTHORS = {"", "Enterprise AI Assistant Demo"}
ALLOWED_CREATORS = {"", "Enterprise AI Assistant"}


def test_demo_pdf_author_metadata_is_synthetic():
    pdfs = sorted(Path("data/documents").glob("*.pdf"))
    assert pdfs

    for pdf in pdfs:
        metadata = PdfReader(str(pdf)).metadata or {}
        author = str(metadata.get("/Author") or "").strip()
        creator = str(metadata.get("/Creator") or "").strip()
        assert author in ALLOWED_AUTHORS, f"Non-synthetic PDF author metadata in {pdf}"
        assert creator in ALLOWED_CREATORS, f"Non-synthetic PDF creator metadata in {pdf}"


def test_repository_guard_recognizes_current_github_token_shapes():
    pattern = SECRET_PATTERNS["GitHub token"]
    samples = [
        "github" + "_pat_" + ("A" * 24),
        "gh" + "p_" + ("B" * 20),
        "gh" + "o_" + ("C" * 20),
        "gh" + "u_" + ("D" * 20),
        "gh" + "r_" + ("E" * 20),
        "gh" + "s_" + ("F" * 36),
        "gh" + "s_" + "12345_" + ("G" * 8) + "." + ("H" * 8) + "_" + ("I" * 8) + "-" + ("J" * 8),
    ]

    for sample in samples:
        assert pattern.search(sample)
