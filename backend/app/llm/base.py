"""
Base interface for LLM providers.

All providers follow the same behavior contract and expose enough
identity metadata for logging, evaluation, and debugging.
"""

from abc import ABC, abstractmethod

from app.prompts.system_prompts import (
    ENTERPRISE_ASSISTANT_SYSTEM_PROMPT,
)


class BaseLLMProvider(ABC):
    """
    Common interface for all LLM providers.
    """

    provider_name: str = "unknown"
    model_name: str = "unknown"

    def build_messages(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """
        Build a standard chat-style message list.
        """

        messages = [
            {
                "role": "system",
                "content": ENTERPRISE_ASSISTANT_SYSTEM_PROMPT,
            }
        ]

        if history:
            messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        return messages

    def build_text_prompt(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Build a plain-text prompt for providers that use text input.
        """

        messages = self.build_messages(message, history)

        return "\n\n".join(
            f"{item['role'].upper()}:\n{item['content']}"
            for item in messages
        )

    @abstractmethod
    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Generate a complete response.
        """

        raise NotImplementedError

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        """
        Default streaming implementation.
        """

        yield self.generate(message, history)