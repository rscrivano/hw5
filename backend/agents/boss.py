"""Boss - reads each ticket, routes the work, makes the final calls and sets the ticket status."""
from backend.models import AgentRole

ROLE = AgentRole(
    name="Boss",
    prompt_file="boss.md",
    description="manager: routes tickets, makes final calls (incl. discounts), sets ticket status",
    mcp_tools=frozenset({"get_today", "get_ticket", "list_tickets", "get_cash", "list_approvals", "list_sales",
                         "update_ticket", "record_price_decision"}),
)
