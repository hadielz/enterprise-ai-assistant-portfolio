from sqlalchemy import select

from app.database.models import DocumentChunk
from app.rag import pgvector_store


def test_pgvector_index_and_search_with_controlled_embeddings(db_session, monkeypatch):
    # Keep this test deterministic and offline. It exercises the real pgvector
    # column/query path without any external embedding provider.
    chunks = [
        {"source": "policy.txt", "chunk_id": 0, "content": "hotel limit 150"},
        {"source": "policy.txt", "chunk_id": 1, "content": "meal limit 30"},
    ]
    vectors = {
        "hotel limit 150": [0.0] * 1536,
        "meal limit 30": [1.0] + [0.0] * 1535,
        "hotel question": [0.0] * 1536,
    }

    monkeypatch.setattr(pgvector_store, "load_document_chunks", lambda: chunks)
    monkeypatch.setattr(pgvector_store, "embed_text", lambda text: vectors[text])

    # Reuse the test transaction instead of the production SessionLocal.
    class SessionContext:
        def __enter__(self):
            return db_session
        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pgvector_store, "SessionLocal", SessionContext)
    assert pgvector_store.index_documents() == 2
    assert len(db_session.scalars(select(DocumentChunk)).all()) == 2

    result = pgvector_store.search_similar_chunks("hotel question", top_k=1)
    assert result["sources"] == ["policy.txt#chunk-0"]
    assert "hotel limit 150" in result["context"]
