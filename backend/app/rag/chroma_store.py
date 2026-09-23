"""Local-development ChromaDB vector backend."""

import chromadb

from app.core.config import settings
from app.rag.document_loader import load_document_chunks
from app.rag.embeddings import embed_text


def get_collection():
    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(name="enterprise_documents")


def index_documents() -> int:
    collection = get_collection()
    chunks = load_document_chunks()

    for chunk in chunks:
        chunk_id = f'{chunk["source"]}-chunk-{chunk["chunk_id"]}'
        embedding = embed_text(chunk["content"])
        collection.upsert(
            ids=[chunk_id],
            documents=[chunk["content"]],
            embeddings=[embedding],
            metadatas=[
                {"source": chunk["source"], "chunk_id": chunk["chunk_id"]}
            ],
        )
    return len(chunks)


def search_similar_chunks(question: str, top_k: int = 3) -> dict:
    collection = get_collection()
    query_embedding = embed_text(question)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    selected_documents = []
    sources = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        if distance <= settings.vector_distance_threshold:
            selected_documents.append(document)
            sources.append(f'{metadata["source"]}#chunk-{metadata["chunk_id"]}')

    return {"context": "\n\n".join(selected_documents), "sources": sources}
