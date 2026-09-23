"""Embedding boundary shared by local Chroma and durable pgvector backends."""

from openai import OpenAI

from app.core.config import settings
from app.observability.tracing import start_span


def get_openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to your runtime secrets.")
    return OpenAI(api_key=settings.openai_api_key)


def embed_text(text: str) -> list[float]:
    with start_span(
        "rag.embedding",
        **{
            "ai.embedding.provider": "openai",
            "ai.embedding.model": settings.embedding_model,
        },
    ):
        result = get_openai_client().embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimensions,
        )
        return result.data[0].embedding
