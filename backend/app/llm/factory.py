"""
LLM provider factory.

Creates vendor-specific providers and wraps them with automatic fallback.

Architecture Notes
------------------
Provider SDK imports are intentionally lazy. Controlled offline tests can
construct providers without importing or initializing OpenAI, Gemini, or
Ollama integrations. Production behavior is unchanged when a configured
provider is actually created.
"""

import logging
from collections.abc import Callable

from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.resilient_provider import ResilientLLMProvider


logger = logging.getLogger(__name__)


ProviderCreator = Callable[[str], BaseLLMProvider]


def create_provider(provider_name: str) -> BaseLLMProvider:
    """Create one provider by configuration name."""

    normalized_name = provider_name.strip().lower()

    if normalized_name == "mock":
        from app.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()

    if normalized_name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()

    if normalized_name == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider()

    if normalized_name == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider()

    raise ValueError(f"Unsupported LLM provider: {provider_name}")


def get_llm_provider(
    *,
    provider_creator: ProviderCreator | None = None,
    configured_provider_names: list[str] | None = None,
) -> BaseLLMProvider:
    """
    Build the primary provider followed by configured fallbacks.

    Controlled tests may inject provider construction and provider names.
    Production callers omit both arguments and retain existing behavior.

    Duplicate provider names are removed while preserving order.
    Providers that cannot be initialized are skipped and logged.
    """

    configured_names = (
        configured_provider_names
        if configured_provider_names is not None
        else [
            settings.llm_provider,
            *settings.llm_fallback_providers.split(","),
        ]
    )

    create = provider_creator or create_provider

    unique_names = []
    for name in configured_names:
        normalized_name = name.strip().lower()

        if normalized_name and normalized_name not in unique_names:
            unique_names.append(normalized_name)

    providers = []

    for provider_name in unique_names:
        try:
            providers.append(
                (provider_name, create(provider_name))
            )
        except Exception as exc:
            logger.warning(
                "Could not initialize provider=%s: %s",
                provider_name,
                exc,
            )

    return ResilientLLMProvider(providers)
