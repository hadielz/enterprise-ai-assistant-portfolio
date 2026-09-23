"""
OpenAI LLM provider.

This provider calls a real OpenAI chat model.
It implements the same interface as MockLLMProvider.
"""

from openai import OpenAI

from app.core.config import settings
from app.llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """
    Real LLM provider using OpenAI.
    """

    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is missing. Add it to your .env file."
            )

        self.client = OpenAI(
            api_key=settings.openai_api_key
        )

        self.provider_name = "openai"
        self.model_name = settings.openai_model

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Send the user's message plus conversation history to OpenAI.
        """

        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.build_messages(
                message,
                history,
            ),
            temperature=0.2,
        )

        return completion.choices[0].message.content or ""

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        """
        Stream the OpenAI response chunk by chunk.
        """

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.build_messages(
                message,
                history,
            ),
            temperature=0.2,
            stream=True,
        )

        for chunk in stream:
            token = chunk.choices[0].delta.content

            if token:
                yield token