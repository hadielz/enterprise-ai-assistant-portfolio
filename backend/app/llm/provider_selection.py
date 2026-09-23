"""
Provider-selection metadata.

Architecture Notes
------------------
Purpose:
    Keep provider identity metadata explicit and request-safe.

Provider generation metadata:
    ProviderGenerationResult records which provider successfully produced
    one non-streaming response. ResilientLLMProvider.generate() keeps the
    common string return type; controlled evaluations may call
    generate_with_metadata() when provider identity is part of the contract.

Boundary:
    This metadata describes provider execution only. It does not classify
    whether a successfully returned string obeys a higher-level protocol such
    as the tool-selection JSON contract.
"""

from dataclasses import dataclass

from app.llm.base import BaseLLMProvider


@dataclass(frozen=True)
class SelectedProvider:
    """
    One provider candidate from a fallback chain.
    """

    provider: BaseLLMProvider
    provider_name: str
    model_name: str
    fallback_used: bool


@dataclass(frozen=True)
class ProviderGenerationResult:
    """
    Successful non-streaming provider execution with identity metadata.

    content:
        Raw text returned by the successful provider.

    provider_name / model_name:
        Identity exposed by that provider instance.

    fallback_used:
        False for the first attempted provider candidate, True when success
        came from a later candidate in the configured fallback chain.
    """

    content: str
    provider_name: str
    model_name: str
    fallback_used: bool
