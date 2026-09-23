from dataclasses import replace

import pytest

from app.core.config import settings


def test_local_defaults_keep_chroma_and_local_mcp_auth():
    assert settings.vector_store_backend in {"chroma", "pgvector"}
    assert settings.mcp_auth_mode in {"none", "google_identity"}


def test_runtime_rejects_unknown_vector_backend():
    candidate = replace(settings, vector_store_backend="unknown")
    with pytest.raises(ValueError, match="VECTOR_STORE_BACKEND"):
        candidate.validate_runtime()


def test_pgvector_requires_release_embedding_dimensions():
    candidate = replace(
        settings,
        vector_store_backend="pgvector",
        embedding_dimensions=1024,
    )
    with pytest.raises(ValueError, match="1536"):
        candidate.validate_runtime()


def test_google_identity_requires_mcp_audience():
    candidate = replace(settings, mcp_auth_mode="google_identity", mcp_audience="")
    with pytest.raises(ValueError, match="MCP_AUDIENCE"):
        candidate.validate_runtime()


def test_production_rejects_wildcard_cors_origin():
    candidate = replace(settings, environment="production", allowed_origins="*")
    with pytest.raises(ValueError, match="explicit origins"):
        candidate.validate_backend_http_runtime()


def test_rate_limit_values_must_be_positive():
    candidate = replace(settings, rate_limit_chat_limit=0)
    with pytest.raises(ValueError, match="RATE_LIMIT_CHAT_LIMIT"):
        candidate.validate_runtime()


def test_production_rejects_non_https_cors_origin():
    candidate = replace(
        settings,
        environment="production",
        allowed_origins="http://frontend.example",
    )
    with pytest.raises(ValueError, match="HTTPS origins only"):
        candidate.validate_backend_http_runtime()


def test_production_rejects_trailing_slash_cors_origin():
    candidate = replace(
        settings,
        environment="production",
        allowed_origins="https://frontend.example/",
    )
    with pytest.raises(ValueError, match="HTTPS origins only"):
        candidate.validate_backend_http_runtime()


def test_production_accepts_explicit_https_cors_origin():
    candidate = replace(
        settings,
        environment="production",
        allowed_origins="https://frontend.example",
    )
    candidate.validate_backend_http_runtime()


def test_general_production_runtime_validation_does_not_require_backend_cors():
    candidate = replace(settings, environment="production", allowed_origins="")
    candidate.validate_runtime()
