"""Durable PostgreSQL/pgvector RAG backend used by the R3 cloud deployment."""

from sqlalchemy import delete, select

from app.core.config import settings
from app.database.models import DocumentChunk
from app.database.session import SessionLocal
from app.rag.document_loader import load_document_chunks
from app.rag.embeddings import embed_text


def index_documents() -> int:
    chunks = load_document_chunks()
    with SessionLocal() as session:
        for chunk in chunks:
            embedding = embed_text(chunk["content"])
            statement = select(DocumentChunk).where(
                DocumentChunk.source == chunk["source"],
                DocumentChunk.chunk_id == chunk["chunk_id"],
            )
            row = session.scalar(statement)
            if row is None:
                row = DocumentChunk(
                    source=chunk["source"],
                    chunk_id=chunk["chunk_id"],
                    content=chunk["content"],
                    embedding=embedding,
                )
                session.add(row)
            else:
                row.content = chunk["content"]
                row.embedding = embedding

        indexed_keys = {(c["source"], c["chunk_id"]) for c in chunks}
        existing = session.scalars(select(DocumentChunk)).all()
        for row in existing:
            if (row.source, row.chunk_id) not in indexed_keys:
                session.delete(row)

        session.commit()
    return len(chunks)


def search_similar_chunks(question: str, top_k: int = 3) -> dict:
    query_embedding = embed_text(question)
    distance = DocumentChunk.embedding.l2_distance(query_embedding).label("distance")

    with SessionLocal() as session:
        rows = session.execute(
            select(DocumentChunk, distance)
            .order_by(distance)
            .limit(top_k)
        ).all()

    selected_documents: list[str] = []
    sources: list[str] = []
    for row, row_distance in rows:
        if float(row_distance) <= settings.vector_distance_threshold:
            selected_documents.append(row.content)
            sources.append(f"{row.source}#chunk-{row.chunk_id}")

    return {"context": "\n\n".join(selected_documents), "sources": sources}
