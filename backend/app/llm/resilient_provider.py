"""
Resilient LLM provider.

Architecture Notes
------------------
Purpose:
    Try the configured primary provider first and automatically fall
    back to alternative providers when it is unavailable.

Why:
    Cloud providers can fail because of quotas, rate limits, network
    problems, authentication errors, or temporary service outages.

Provider identity:
    generate_with_metadata() exposes the identity of the provider that
    successfully generated a non-streaming response. The existing generate()
    contract remains unchanged and still returns only the response string.

Important boundary:
    Fallback is triggered by provider execution exceptions. A provider that
    successfully returns malformed higher-level protocol text has still
    succeeded at the provider layer; parsing/validation belongs to the caller.

Streaming:
    Fallback is safe before the first output chunk is emitted. If a provider
    fails after partial
    text has already reached the user, switching providers could duplicate or
    contradict the response.
"""

import logging

from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.observability.tracing import start_span
from app.observability.logging import log_event
from app.llm.provider_selection import (
    ProviderGenerationResult,
    SelectedProvider,
)


logger = logging.getLogger(__name__)


class ResilientLLMProvider(BaseLLMProvider):
    """
    Wrap several providers in priority order.
    """

    def __init__(
        self,
        providers: list[tuple[str, BaseLLMProvider]],
    ):
        if not providers:
            raise ValueError(
                "At least one LLM provider is required."
            )

        self.providers = providers

    def iter_provider_candidates(self):
        """
        Yield configured providers with request-safe selection metadata.
        """

        for index, (configured_name, provider) in enumerate(
            self.providers
        ):
            yield SelectedProvider(
                provider=provider,
                provider_name=getattr(
                    provider,
                    "provider_name",
                    configured_name,
                ),
                model_name=getattr(
                    provider,
                    "model_name",
                    "unknown",
                ),
                fallback_used=index > 0,
            )

    def generate_with_metadata(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> ProviderGenerationResult:
        """
        Generate using the first successful provider and return its identity.

        Provider exceptions trigger the next configured candidate. If every
        candidate fails, the existing application-level LLMProviderError is
        raised with the established aggregate failure semantics.
        """

        failures = []

        for selection in self.iter_provider_candidates():
            try:
                with start_span(
                    "ai.provider.generate",
                    **{
                        "ai.provider": selection.provider_name,
                        "ai.model": selection.model_name,
                        "ai.fallback": selection.fallback_used,
                    },
                ) as span:
                    content = selection.provider.generate(message, history)
                    span.set_attribute("ai.provider.outcome", "success")
                log_event(
                    logger, logging.INFO, "llm_provider_succeeded",
                    provider=selection.provider_name,
                    model=selection.model_name,
                    fallback_used=selection.fallback_used,
                )

                return ProviderGenerationResult(
                    content=content,
                    provider_name=selection.provider_name,
                    model_name=selection.model_name,
                    fallback_used=selection.fallback_used,
                )

            except Exception as exc:
                log_event(
                    logger, logging.WARNING, "llm_provider_failed",
                    provider=selection.provider_name,
                    model=selection.model_name,
                    fallback_used=selection.fallback_used,
                    error_class=type(exc).__name__,
                )

                failures.append(
                    f"{selection.provider_name}: {exc}"
                )

        raise LLMProviderError(
            "All configured LLM providers failed. "
            + " | ".join(failures)
        )

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Generate a response using the first successful provider.

        The public provider contract remains unchanged: callers receive only
        the response text.
        """

        return self.generate_with_metadata(
            message,
            history,
        ).content

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        """
        Stream from the first successful provider.

        A fallback provider may be attempted only when the current
        provider fails before emitting any output.
        """

        failures = []

        for selection in self.iter_provider_candidates():
            emitted_output = False

            try:
                with start_span(
                    "ai.provider.stream",
                    **{
                        "ai.provider": selection.provider_name,
                        "ai.model": selection.model_name,
                        "ai.fallback": selection.fallback_used,
                    },
                ) as span:
                    for token in selection.provider.stream(
                        message,
                        history,
                    ):
                        emitted_output = True
                        yield token

                    span.set_attribute("ai.provider.outcome", "success")

                log_event(
                    logger, logging.INFO, "llm_stream_provider_succeeded",
                    provider=selection.provider_name,
                    model=selection.model_name,
                    fallback_used=selection.fallback_used,
                )
                return

            except Exception as exc:
                log_event(
                    logger, logging.WARNING, "llm_stream_provider_failed",
                    provider=selection.provider_name,
                    model=selection.model_name,
                    fallback_used=selection.fallback_used,
                    emitted_output=emitted_output,
                    error_class=type(exc).__name__,
                )

                # Once output has reached the browser, silently switching
                # providers could create a corrupted mixed response.
                if emitted_output:
                    raise LLMProviderError(
                        "Provider "
                        f"{selection.provider_name} "
                        f"model={selection.model_name} failed after "
                        "streaming had started."
                    ) from exc

                failures.append(
                    f"{selection.provider_name}: {exc}"
                )

        raise LLMProviderError(
            "All configured streaming providers failed. "
            + " | ".join(failures)
        )
