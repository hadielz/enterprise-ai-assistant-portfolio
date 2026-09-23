"""
Versioned prompt registry.

Architecture Notes
------------------
Purpose:
    Give every important prompt a stable identity and version.

Why:
    Generated behavior cannot be investigated reliably if we cannot
    determine which instructions produced an answer.

Versioning rule:
    When the meaning or expected behavior of a prompt changes, increment
    its version. Formatting-only changes do not necessarily require a
    new version.

Examples:
    assistant.system.v1
    rag.answer.v1
    tool.selection.v1
    conversation.summary.v1
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptDefinition:
    """
    One immutable prompt definition.

    name:
        Stable logical identity.

    version:
        Integer behavior version.

    template:
        Prompt text or formatting template.
    """

    name: str
    version: int
    template: str

    @property
    def prompt_id(self) -> str:
        """
        Return a human-readable versioned identifier.
        """

        return f"{self.name}.v{self.version}"


ASSISTANT_SYSTEM_PROMPT = PromptDefinition(
    name="assistant.system",
    version=1,
    template="""
You are an enterprise AI assistant.

Your role:
- Answer clearly and professionally.
- Be concise unless the user asks for details.
- Use internal company context when provided.
- Do not invent internal policies.
- If the answer is not present in the provided context, say so.
""".strip(),
)


RAG_ANSWER_PROMPT = PromptDefinition(
    name="rag.answer",
    version=1,
    template="""
Use the following internal company context to answer the user question.

Internal context:
{context}

User question:
{user_message}

Instructions:
- Answer based on the internal context when relevant.
- If the context does not contain the answer, say that the information
  is not available in the internal documents.
- Do not invent company policies.
""".strip(),
)


TOOL_SELECTION_PROMPT = PromptDefinition(
    name="tool.selection",
    version=1,
    template="""
You are a tool selection system.

Your task is to decide whether the user request requires a tool.

{available_tools}

User message:
{message}

Return ONLY valid JSON with this format:
{{
  "tool_name": "calculator | ticket_creator | none",
  "tool_input": "input for the selected tool"
}}
""".strip(),
)


CONVERSATION_SUMMARY_PROMPT = PromptDefinition(
    name="conversation.summary",
    version=1,
    template="""
You summarize conversations for an enterprise AI assistant.

Existing summary:
{existing_summary}

Conversation messages:
{history_text}

Create an updated concise summary that preserves:
- user preferences
- important facts
- ongoing tasks
- decisions already made

Return only the updated summary.
""".strip(),
)


TOOL_ANSWER_PROMPT = PromptDefinition(
    name="tool.answer",
    version=1,
    template="""
The user asked:

{message}

A tool was executed.

Tool name:
{tool_name}

Tool result:
{tool_result}

Answer the user clearly using the verified tool result.
""".strip(),
)