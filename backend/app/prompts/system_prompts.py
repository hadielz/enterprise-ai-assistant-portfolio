"""
General assistant system prompt.

Compatibility module:
    Existing provider code imports this constant. Its value now comes
    from the versioned prompt registry.
"""

from app.prompts.registry import ASSISTANT_SYSTEM_PROMPT


ENTERPRISE_ASSISTANT_SYSTEM_PROMPT = (
    ASSISTANT_SYSTEM_PROMPT.template
)