"""
Versioned RAG prompt construction.
"""

from app.prompts.registry import RAG_ANSWER_PROMPT


def build_rag_prompt(
    user_message: str,
    context: str,
) -> str:
    """
    Build the prompt used for a grounded RAG answer.
    """

    return RAG_ANSWER_PROMPT.template.format(
        user_message=user_message,
        context=context,
    )