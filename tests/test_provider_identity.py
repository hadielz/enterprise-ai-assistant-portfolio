"""
Provider identity and fallback-candidate tests.
"""

from app.llm.base import BaseLLMProvider
from app.llm.resilient_provider import (
    ResilientLLMProvider,
)


class TestProvider(BaseLLMProvider):
    """
    Deterministic provider used only by this test module.
    """

    def __init__(
        self,
        provider_name: str,
        model_name: str,
    ):
        self.provider_name = provider_name
        self.model_name = model_name

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        return f"{self.provider_name}: {message}"


def test_provider_candidates_include_identity():
    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                TestProvider(
                    "primary-provider",
                    "primary-model",
                ),
            ),
            (
                "fallback",
                TestProvider(
                    "fallback-provider",
                    "fallback-model",
                ),
            ),
        ]
    )

    candidates = list(
        resilient.iter_provider_candidates()
    )

    assert candidates[0].provider_name == (
        "primary-provider"
    )

    assert candidates[0].model_name == (
        "primary-model"
    )

    assert candidates[0].fallback_used is False

    assert candidates[1].provider_name == (
        "fallback-provider"
    )

    assert candidates[1].fallback_used is True