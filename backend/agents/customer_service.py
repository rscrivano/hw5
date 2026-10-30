"""Customer Service - drafts respectful, accurate messages to customers and requesters (never sent)."""
from backend.models import AgentRole

ROLE = AgentRole(
    name="Customer Service",
    prompt_file="customer_service.md",
    description="drafts messages to customers/requesters (saved as drafts, never sent)",
    mcp_tools=frozenset({"get_today", "get_ticket", "check_stock", "draft_customer_message", "list_drafts"}),
)
