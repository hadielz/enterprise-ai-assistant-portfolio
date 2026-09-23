"""
Ollama LLM provider.

Architecture Notes
------------------
Purpose:
    Connect the application to local/self-hosted LLMs through Ollama.

Why this class exists:
    The rest of the application should not know whether responses come
    from OpenAI, Gemini, Ollama, or another provider.

Design:
    Ollama exposes a local HTTP API. We call its /api/chat endpoint and
    adapt the response to our common BaseLLMProvider interface.

Future:
    This provider can later support:
    - local embeddings
    - local tool-calling models
    - fully offline RAG
"""

import json

import requests

from app.core.config import settings
from app.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Local LLM provider using Ollama.
    """

    def __init__(self):
        self.provider_name = "ollama"
        self.model_name = settings.ollama_model

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        payload = {
            "model": self.model_name,
            "messages": self.build_messages(
                message,
                history,
            ),
            "stream": False,
        }

        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()

        return data.get(
            "message",
            {},
        ).get(
            "content",
            "",
        )

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        payload = {
            "model": self.model_name,
            "messages": self.build_messages(
                message,
                history,
            ),
            "stream": True,
        }

        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            data = json.loads(
                line.decode("utf-8")
            )

            token = data.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )

            if token:
                yield token