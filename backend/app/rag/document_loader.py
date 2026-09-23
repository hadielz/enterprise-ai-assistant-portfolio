"""
Document loader for RAG.

Supports:
- .txt documents
- .pdf documents

Each document is split into chunks for retrieval.
"""

from pathlib import Path
from pypdf import PdfReader


DOCUMENTS_DIR = Path("data/documents")


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))

    return chunks


def read_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def read_pdf(file_path: Path) -> str:
    """
    Extract text from a PDF file.
    """

    reader = PdfReader(str(file_path))
    pages_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    return "\n".join(pages_text)


def load_document_chunks() -> list[dict]:
    chunks = []

    supported_files = list(DOCUMENTS_DIR.glob("*.txt")) + list(DOCUMENTS_DIR.glob("*.pdf"))

    for file_path in supported_files:
        if file_path.suffix == ".txt":
            content = read_txt(file_path)
        elif file_path.suffix == ".pdf":
            content = read_pdf(file_path)
        else:
            continue

        for index, chunk in enumerate(chunk_text(content)):
            chunks.append(
                {
                    "source": file_path.name,
                    "chunk_id": index,
                    "content": chunk,
                }
            )

    return chunks