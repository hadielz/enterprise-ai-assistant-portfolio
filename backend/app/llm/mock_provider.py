"""
Mock LLM provider.

This provider does not call a real AI model.
It is useful for:
- testing
- development without API keys
- verifying the application flow
"""

from app.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """
    Fake LLM provider used during development.
    """

    def __init__(self):
        self.provider_name = "mock"
        self.model_name = "deterministic-mock-v1"

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Return a simple fake AI response.
        """

        history_count = len(history or [])

        return (
            f"Mock AI response with {history_count} previous messages. "
            f"Your message was: '{message}'"
        )