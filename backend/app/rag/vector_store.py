"""Configured vector-store facade.

R3 keeps ChromaDB for simple local development and adds PostgreSQL/pgvector as
the durable Cloud Run-compatible backend. The application-facing functions are
unchanged.
"""

from app.core.config import settings
from app.observability.tracing import start_span


def _backend_module():
    if settings.vector_store_backend == "chroma":
        from app.rag import chroma_store as backend
        return backend
    if settings.vector_store_backend == "pgvector":
        from app.rag import pgvector_store as backend
        return backend
    raise ValueError(f"Unsupported vector backend: {settings.vector_store_backend}")


def index_documents() -> int:
    with start_span(
        "rag.index",
        **{"rag.vector_backend": settings.vector_store_backend},
    ) as span:
        count = _backend_module().index_documents()
        span.set_attribute("rag.indexed_chunks", count)
        return count


def search_similar_chunks(question: str, top_k: int = 3) -> dict:
    with start_span(
        "rag.retrieve",
        **{
            "rag.vector_backend": settings.vector_store_backend,
            "rag.top_k": top_k,
        },
    ) as span:
        result = _backend_module().search_similar_chunks(question, top_k=top_k)
        span.set_attribute("rag.result_count", len(result.get("sources", [])))
        span.set_attribute("rag.outcome", "results" if result.get("context") else "no_result")
        return result
