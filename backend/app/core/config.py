"""Application configuration.

Centralizes runtime settings and secrets. Secrets are read from environment
variables or Cloud Run secret injection; they are never hardcoded in source.
"""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Enterprise AI Assistant")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    environment: str = os.getenv("APP_ENV", "local")

    # HTTP/browser configuration.
    allowed_origins: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:5175",
    )

    # Bounded R4 request-rate baseline. This is process-local by design; the
    # cloud deployment enables it explicitly and also keeps max instances bounded.
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", False)
    rate_limit_register_limit: int = int(os.getenv("RATE_LIMIT_REGISTER_LIMIT", "20"))
    rate_limit_register_window_seconds: int = int(
        os.getenv("RATE_LIMIT_REGISTER_WINDOW_SECONDS", "600")
    )
    rate_limit_login_global_limit: int = int(
        os.getenv("RATE_LIMIT_LOGIN_GLOBAL_LIMIT", "60")
    )
    rate_limit_login_global_window_seconds: int = int(
        os.getenv("RATE_LIMIT_LOGIN_GLOBAL_WINDOW_SECONDS", "60")
    )
    rate_limit_login_user_limit: int = int(
        os.getenv("RATE_LIMIT_LOGIN_USER_LIMIT", "10")
    )
    rate_limit_login_user_window_seconds: int = int(
        os.getenv("RATE_LIMIT_LOGIN_USER_WINDOW_SECONDS", "300")
    )
    rate_limit_chat_limit: int = int(os.getenv("RATE_LIMIT_CHAT_LIMIT", "30"))
    rate_limit_chat_window_seconds: int = int(
        os.getenv("RATE_LIMIT_CHAT_WINDOW_SECONDS", "60")
    )
    rate_limit_rag_index_limit: int = int(
        os.getenv("RATE_LIMIT_RAG_INDEX_LIMIT", "3")
    )
    rate_limit_rag_index_window_seconds: int = int(
        os.getenv("RATE_LIMIT_RAG_INDEX_WINDOW_SECONDS", "3600")
    )
    rate_limit_ticket_status_limit: int = int(
        os.getenv("RATE_LIMIT_TICKET_STATUS_LIMIT", "30")
    )
    rate_limit_ticket_status_window_seconds: int = int(
        os.getenv("RATE_LIMIT_TICKET_STATUS_WINDOW_SECONDS", "60")
    )

    # Which LLM backend to use: mock, openai, gemini, or ollama.
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_fallback_providers: str = os.getenv(
        "LLM_FALLBACK_PROVIDERS",
        "openai,ollama",
    )

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL",
        "http://host.docker.internal:11434",
    )
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    # Embeddings and vector retrieval.
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    vector_store_backend: str = os.getenv("VECTOR_STORE_BACKEND", "chroma")
    vector_distance_threshold: float = _env_float(
        "VECTOR_DISTANCE_THRESHOLD",
        1.2,
    )
    chroma_path: str = os.getenv("CHROMA_PATH", "data/chroma")

    # Authentication settings.
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Relational database used by the running application.
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://enterprise_ai:enterprise_ai"
        "@postgres:5432/enterprise_ai",
    )
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    database_max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "2"))
    database_pool_timeout: int = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
    database_pool_recycle: int = int(os.getenv("DATABASE_POOL_RECYCLE", "1800"))

    test_database_url: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://enterprise_ai_test:"
        "enterprise_ai_test@postgres-test:5432/"
        "enterprise_ai_test",
    )

    # Internal MCP ticket capability.
    mcp_ticket_url: str = os.getenv(
        "MCP_TICKET_URL",
        "http://mcp-server:8001/mcp",
    )
    mcp_auth_mode: str = os.getenv("MCP_AUTH_MODE", "none")
    mcp_audience: str = os.getenv("MCP_AUDIENCE", "")
    mcp_server_host: str = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    mcp_server_port: int = int(os.getenv("MCP_SERVER_PORT", "8001"))

    # Observability. R3 exports traces through OTLP and writes JSON logs to
    # stdout so Cloud Run can ingest them as structured Cloud Logging entries.
    otel_enabled: bool = _env_bool("OTEL_ENABLED", False)
    otel_service_name: str = os.getenv(
        "OTEL_SERVICE_NAME",
        "enterprise-ai-backend",
    )
    otel_exporter: str = os.getenv("OTEL_EXPORTER", "console")
    otel_endpoint: str = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "https://telemetry.googleapis.com:443/v1/traces",
    )
    otel_sample_ratio: float = _env_float("OTEL_SAMPLE_RATIO", 0.1)
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [
            value.strip()
            for value in self.allowed_origins.split(",")
            if value.strip()
        ]

    def validate_runtime(self) -> None:
        """Reject unsafe/unsupported runtime combinations early."""

        if self.vector_store_backend not in {"chroma", "pgvector"}:
            raise ValueError(
                "VECTOR_STORE_BACKEND must be 'chroma' or 'pgvector'."
            )

        if self.embedding_dimensions != 1536 and self.vector_store_backend == "pgvector":
            raise ValueError(
                "The R3 pgvector schema is fixed at 1536 dimensions. "
                "Use EMBEDDING_DIMENSIONS=1536 for this release."
            )

        if self.mcp_auth_mode not in {"none", "google_identity"}:
            raise ValueError(
                "MCP_AUTH_MODE must be 'none' or 'google_identity'."
            )

        if self.mcp_auth_mode == "google_identity" and not self.mcp_audience:
            raise ValueError(
                "MCP_AUDIENCE is required when MCP_AUTH_MODE=google_identity."
            )

        if not 0.0 <= self.otel_sample_ratio <= 1.0:
            raise ValueError("OTEL_SAMPLE_RATIO must be between 0 and 1.")

        rate_values = {
            "RATE_LIMIT_REGISTER_LIMIT": self.rate_limit_register_limit,
            "RATE_LIMIT_REGISTER_WINDOW_SECONDS": self.rate_limit_register_window_seconds,
            "RATE_LIMIT_LOGIN_GLOBAL_LIMIT": self.rate_limit_login_global_limit,
            "RATE_LIMIT_LOGIN_GLOBAL_WINDOW_SECONDS": self.rate_limit_login_global_window_seconds,
            "RATE_LIMIT_LOGIN_USER_LIMIT": self.rate_limit_login_user_limit,
            "RATE_LIMIT_LOGIN_USER_WINDOW_SECONDS": self.rate_limit_login_user_window_seconds,
            "RATE_LIMIT_CHAT_LIMIT": self.rate_limit_chat_limit,
            "RATE_LIMIT_CHAT_WINDOW_SECONDS": self.rate_limit_chat_window_seconds,
            "RATE_LIMIT_RAG_INDEX_LIMIT": self.rate_limit_rag_index_limit,
            "RATE_LIMIT_RAG_INDEX_WINDOW_SECONDS": self.rate_limit_rag_index_window_seconds,
            "RATE_LIMIT_TICKET_STATUS_LIMIT": self.rate_limit_ticket_status_limit,
            "RATE_LIMIT_TICKET_STATUS_WINDOW_SECONDS": self.rate_limit_ticket_status_window_seconds,
        }
        invalid_rate_values = [name for name, value in rate_values.items() if value < 1]
        if invalid_rate_values:
            raise ValueError(
                "Rate-limit settings must be positive integers: "
                + ", ".join(invalid_rate_values)
            )

    def validate_backend_http_runtime(self) -> None:
        """Reject unsafe browser/CORS configuration for the public backend."""

        if self.environment != "production":
            return

        origins = self.allowed_origin_list
        if not origins or "*" in origins:
            raise ValueError(
                "Production ALLOWED_ORIGINS must contain explicit origins and cannot use '*'."
            )

        invalid_origins = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path != ""
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                invalid_origins.append(origin)

        if invalid_origins:
            raise ValueError(
                "Production ALLOWED_ORIGINS must contain HTTPS origins only "
                "(scheme + host, no credentials/path/query/fragment): "
                + ", ".join(invalid_origins)
            )


settings = Settings()
