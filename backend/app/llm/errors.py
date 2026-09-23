"""
LLM-specific application exceptions.

Provider SDK exceptions should not leak throughout the application.
This module gives the rest of the backend one stable error type.
"""


class LLMProviderError(RuntimeError):
    """
    Raised when every configured LLM provider fails.
    """