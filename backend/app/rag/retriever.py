"""
Retriever for RAG.

This version uses embeddings + ChromaDB instead of simple word overlap.

Architecture Notes
------------------
Dependency seam:
    Offline evaluations may supply a deterministic search function.
    Production callers omit it and continue using ChromaDB-backed search.

Lazy import:
    The vector-store module is imported only when production retrieval is
    requested. Controlled tests therefore do not import ChromaDB or create
    embedding clients merely by importing the retriever interface.
"""

from collections.abc import Callable


ChunkSearcher = Callable[..., dict]


def _production_searcher(question: str, *, top_k: int) -> dict:
    from app.rag.vector_store import search_similar_chunks

    return search_similar_chunks(question, top_k=top_k)


def retrieve_context(
    question: str,
    top_k: int = 3,
    *,
    searcher: ChunkSearcher | None = None,
) -> dict:
    """Retrieve semantically relevant context."""

    search = searcher or _production_searcher
    return search(question, top_k=top_k)
