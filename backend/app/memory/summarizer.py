"""
Automatic PostgreSQL-backed conversation summarizer.

Long conversations are summarized so recent context and important
older information can be supplied without sending every message
to the LLM.
"""

from sqlalchemy.orm import Session

from app.database.conversation_repository import (
    get_full_history,
    get_summary,
    set_summary,
)
from app.llm.factory import get_llm_provider
from app.prompts.registry import CONVERSATION_SUMMARY_PROMPT


SUMMARY_TRIGGER_MESSAGES = 10


def maybe_summarize_conversation(
    session: Session,
    user_id: int,
    conversation_id: str,
) -> None:
    """
    Update the summary when a conversation reaches the threshold.
    """

    full_history = get_full_history(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
    )

    if len(full_history) < SUMMARY_TRIGGER_MESSAGES:
        return

    existing_summary = get_summary(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
    )

    llm_provider = get_llm_provider()

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in full_history
    )

    prompt = CONVERSATION_SUMMARY_PROMPT.template.format(
        existing_summary=existing_summary,
        history_text=history_text,
    )

    updated_summary = llm_provider.generate(prompt)

    set_summary(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
        summary=updated_summary,
    )