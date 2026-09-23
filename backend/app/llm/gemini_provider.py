"""
Gemini LLM provider.

This provider allows the application to use Google Gemini models.
It follows the same interface as OpenAIProvider and MockLLMProvider.
"""

from google import genai
from google.genai import types

from app.core.config import settings
from app.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """
    Real LLM provider using Google Gemini.
    """

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing. Add it to your .env file."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

        self.provider_name = "gemini"
        self.model_name = settings.gemini_model

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Generate a full Gemini response.
        """

        prompt = self.build_text_prompt(
            message,
            history,
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )

        return response.text or ""

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        """
        Stream a Gemini response chunk by chunk.
        """

        prompt = self.build_text_prompt(
            message,
            history,
        )

        stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )

        for chunk in stream:
            if chunk.text:
                yield chunk.text