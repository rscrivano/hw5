"""Facilities - the shop space: leases and rent; prepares rent payments for human approval."""
from backend.models import AgentRole

ROLE = AgentRole(
    name="Facilities",
    prompt_file="facilities.md",
    description="the shop space: leases, rent due dates; prepares rent payments for human approval",
    mcp_tools=frozenset({"get_today", "get_ticket", "get_lease", "list_leases", "list_approvals",
                         "request_rent_payment"}),
)
