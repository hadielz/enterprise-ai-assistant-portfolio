from app.core.config import settings
from app.rag import vector_store


def test_vector_store_dispatches_chroma(monkeypatch):
    class Backend:
        @staticmethod
        def search_similar_chunks(question, top_k=3):
            return {"context": question, "sources": [str(top_k)]}

    monkeypatch.setattr(settings, "vector_store_backend", "chroma")
    monkeypatch.setattr(vector_store, "_backend_module", lambda: Backend)
    result = vector_store.search_similar_chunks("hello", top_k=2)
    assert result == {"context": "hello", "sources": ["2"]}


def test_vector_store_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr(settings, "vector_store_backend", "unsupported")
    try:
        vector_store._backend_module()
    except ValueError as exc:
        assert "Unsupported vector backend" in str(exc)
    else:
        raise AssertionError("Expected unsupported vector backend to fail")
