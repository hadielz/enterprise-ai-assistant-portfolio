"""Production ticket tool adapter.

R2 replaces the old timestamp simulator. The assistant now reaches the bounded
persisted ticket capability through an actual MCP client/transport.
"""

from app.mcp.client import create_ticket_via_mcp
from app.tools.execution_context import ToolExecutionContext


def create_ticket(
    description: str,
    *,
    execution_context: ToolExecutionContext,
) -> dict:
    return create_ticket_via_mcp(
        description,
        execution_context=execution_context,
    )
