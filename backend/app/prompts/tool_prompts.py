"""
Versioned tool-selection prompt construction.
"""

from app.prompts.registry import TOOL_SELECTION_PROMPT


AVAILABLE_TOOLS = """
Available tools:

1. calculator
Use when the user asks for arithmetic calculations.
Input should be only the mathematical expression.

2. ticket_creator
Use when the user asks to create/open/report an IT issue or support
ticket.
Input should be the ticket description.

3. none
Use when no tool is needed.
""".strip()


def build_tool_selection_prompt(message: str) -> str:
    """
    Build the prompt used for LLM-based tool selection.
    """

    return TOOL_SELECTION_PROMPT.template.format(
        available_tools=AVAILABLE_TOOLS,
        message=message,
    )