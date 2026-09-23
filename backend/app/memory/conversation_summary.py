"""
Conversation summarization.

When conversations become long, we do not want to send every old
message to the LLM. Instead, we summarize older context.
"""


def build_history_context(summary: str | None, recent_history: list[dict]) -> list[dict]:
    """
    Combine a summary of older messages with recent messages.

    The summary is added as a system message so the LLM knows
    important past context without receiving the full conversation.
    """

    messages = []

    if summary:
        messages.append(
            {
                "role": "system",
                "content": f"Conversation summary so far: {summary}",
            }
        )

    messages.extend(recent_history)

    return messages