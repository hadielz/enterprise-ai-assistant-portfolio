"""
Versioned prompt-registry tests.
"""

from app.prompts.rag_prompts import build_rag_prompt
from app.prompts.registry import (
    ASSISTANT_SYSTEM_PROMPT,
    CONVERSATION_SUMMARY_PROMPT,
    RAG_ANSWER_PROMPT,
    TOOL_ANSWER_PROMPT,
    TOOL_SELECTION_PROMPT,
)
from app.prompts.tool_prompts import (
    build_tool_selection_prompt,
)


def test_prompt_ids_are_stable_and_versioned():
    assert (
        ASSISTANT_SYSTEM_PROMPT.prompt_id
        == "assistant.system.v1"
    )

    assert (
        RAG_ANSWER_PROMPT.prompt_id
        == "rag.answer.v1"
    )

    assert (
        TOOL_SELECTION_PROMPT.prompt_id
        == "tool.selection.v1"
    )

    assert (
        CONVERSATION_SUMMARY_PROMPT.prompt_id
        == "conversation.summary.v1"
    )

    assert (
        TOOL_ANSWER_PROMPT.prompt_id
        == "tool.answer.v1"
    )


def test_prompt_registry_names_are_unique():
    prompts = [
        ASSISTANT_SYSTEM_PROMPT,
        RAG_ANSWER_PROMPT,
        TOOL_SELECTION_PROMPT,
        CONVERSATION_SUMMARY_PROMPT,
        TOOL_ANSWER_PROMPT,
    ]

    prompt_ids = [
        prompt.prompt_id
        for prompt in prompts
    ]

    assert len(prompt_ids) == len(set(prompt_ids))


def test_rag_prompt_contains_question_and_context():
    prompt = build_rag_prompt(
        user_message=(
            "What is the hotel reimbursement limit?"
        ),
        context=(
            "Hotel reimbursement is limited to "
            "150 euros per night."
        ),
    )

    assert (
        "What is the hotel reimbursement limit?"
        in prompt
    )

    assert "150 euros per night" in prompt
    assert "Do not invent company policies" in prompt


def test_tool_selection_prompt_requires_json():
    prompt = build_tool_selection_prompt(
        "Please calculate 20 * 5."
    )

    assert '"tool_name"' in prompt
    assert '"tool_input"' in prompt
    assert "calculator" in prompt