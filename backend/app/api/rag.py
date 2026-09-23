"""
RAG API routes.

These endpoints manage document indexing and retrieval.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.authorization import require_support_user
from app.rag.vector_store import index_documents
from app.core.config import settings
from app.security.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/index")
def index_rag_documents(
    support_user: Annotated[dict, Depends(require_support_user)],
):
    """
    Index local documents into the configured vector store.

    R1 treats indexing as a privileged administrative capability. R4 also
    applies a small per-instance rate limit because indexing can trigger
    external embedding work.
    """

    enforce_rate_limit(
        scope="rag.index.user",
        key=str(support_user["id"]),
        limit=settings.rate_limit_rag_index_limit,
        window_seconds=settings.rate_limit_rag_index_window_seconds,
    )

    indexed_count = index_documents()

    return {
        "message": "Documents indexed successfully",
        "indexed_chunks": indexed_count,
    }