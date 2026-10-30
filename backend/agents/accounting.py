"""Accounting - cash, invoices, margins, books tie-out; prepares payments and POs for human approval."""
from backend.models import AgentRole

ROLE = AgentRole(
    name="Accounting",
    prompt_file="accounting.md",
    description="cash, invoices, margins, books tie-out; prepares invoice payments and purchase orders for human approval",
    mcp_tools=frozenset({"get_today", "get_ticket", "get_cash", "list_invoices", "list_payments", "books_tie_out",
                         "check_margin", "vendor_status", "list_approvals", "request_invoice_payment",
                         "request_purchase_order", "list_sales", "list_purchase_orders"}),
)
