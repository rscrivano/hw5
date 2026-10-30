"""Campus Customs MCP server (FastMCP, stdio).

The ONLY way the agents (and Claude Code via .mcp.json) touch shop data. Every tool reads or
writes the WORKING copy, data/campus_customs_new.db (path set in core/config.py), through
mcp_server/shop_db.py, where the store rules are enforced. Tools return stored values or an
error - never a guess.

Problem 3 tools (one per ticket): check_stock (101), get_lease (102), check_margin (103).
Problem 5 adds the tools the agent team needs to work the tickets end to end.

Human-only tools (approve_and_pay, reject_request, reset_database) need the approval secret
in the CC_APPROVAL_SECRET env var, which only the human approval CLI/backend sets. The agent
team never gets these tools, and without the secret they refuse - so no agent can move money.

Run standalone (e.g. with MCP Inspector):  python mcp_server/server.py
"""
from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server import shop_db as shop  # noqa: E402

mcp = FastMCP("campus-customs")
HUMAN_ONLY_TOOLS = {"approve_and_pay", "reject_request", "reset_database", "record_sale", "receive_purchase_order"}


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except shop.ShopError as e:
        return {"ok": False, "error": str(e)}


def _check_secret(secret: str) -> bool:
    expected = os.environ.get("CC_APPROVAL_SECRET", "")
    return bool(expected) and hmac.compare_digest(secret or "", expected)


# ============================================================ Problem 3 ticket tools
@mcp.tool()
def check_stock(sku: str, size: str = "") -> list | dict:
    """On-hand stock from the inventory table for a SKU - one size, or every size if size is blank.
    Returns sku, name, size, qty and location exactly as stored."""
    return _safe(shop.check_stock, sku, size or None)


@mcp.tool()
def get_lease(lease_id: int) -> dict:
    """One lease from the leases table (space, landlord, monthly_rent, next_due), plus
    days_until_due and overdue measured against desk.date_today - the shop's 'today'."""
    return _safe(shop.get_lease, lease_id)


@mcp.tool()
def check_margin(sku: str, unit_price: float, qty: int = 1) -> dict:
    """Margin math from the pricing table for selling qty units of a SKU at unit_price:
    unit_cost, list_price, discount %, unit margin, margin %, order revenue and gross profit.
    below_cost is true if unit_price is under unit_cost."""
    return _safe(shop.check_margin, sku, unit_price, qty)


# ============================================================ shared board / desk
@mcp.tool()
def get_today() -> dict:
    """The shop's 'today' (desk.date_today). Use it - not the computer clock - to judge what is overdue."""
    return shop.get_today()


@mcp.tool()
def list_tickets(status: str = "") -> list | dict:
    """Tickets on the board, optionally filtered by status (open, in_progress, awaiting_approval, blocked, resolved)."""
    return _safe(shop.list_tickets, status or None)


@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """One ticket with its update history, linked payment approvals and drafts."""
    return _safe(shop.get_ticket, ticket_id)


@mcp.tool()
def update_ticket(ticket_id: int, status: str, note: str, author: str = "Boss",
                  assigned_to: str = "", resolution: str = "") -> dict:
    """Set a ticket's status (open | in_progress | awaiting_approval | blocked | resolved) and add a note.
    Use resolution for the final summary when resolving."""
    return _safe(shop.update_ticket, ticket_id, status, note, author, assigned_to or None, resolution or None)


@mcp.tool()
def get_cash() -> dict:
    """Checking balance, total of pending payment requests, and the balance if all pending were paid."""
    return shop.get_cash()


# ============================================================ inventory
@mcp.tool()
def list_inventory() -> list:
    """Every SKU/size with qty, location, unit cost and list price."""
    return shop.list_inventory()


@mcp.tool()
def inventory_health_check(low_stock_threshold: int = 3) -> dict:
    """Scan all stock: out-of-stock / low flags, open-ticket demand, coverage after demand, units on order,
    and for anything that needs reordering a suggested qty, cost and restock vendors with ETAs."""
    return shop.inventory_health_check(low_stock_threshold)


@mcp.tool()
def check_shortfall(sku: str, size: str, qty_needed: int) -> dict:
    """How many units are missing to fill an order, and what the restock costs at unit cost."""
    return _safe(shop.check_shortfall, sku, size, qty_needed)


@mcp.tool()
def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, reserved_by: str = "Inventory") -> dict:
    """Pull units off the shelf for a ticket (decrements inventory). Fails if not enough on hand."""
    return _safe(shop.reserve_stock, ticket_id, sku, size, qty, reserved_by)


@mcp.tool()
def list_vendors() -> list:
    """All vendors with specialty, lead_days, open invoices, whether they will ship, and ETA if ordered today."""
    return shop.list_vendors()


@mcp.tool()
def vendor_status(vendor_id: int) -> dict:
    """One vendor's lead time, open invoices and whether it will ship (a vendor with an open invoice won't)."""
    return _safe(shop.vendor_status, vendor_id)


@mcp.tool()
def find_restock_vendor(sku: str) -> dict:
    """Vendors whose specialty matches the SKU, with lead time, ship status and ETA."""
    return shop.find_restock_vendor(sku)


# ============================================================ accounting
@mcp.tool()
def list_invoices(status: str = "") -> list:
    """Vendor invoices with overdue flags computed against desk.date_today."""
    return shop.list_invoices(status or None)


@mcp.tool()
def list_payments() -> list:
    """Payments already made (each one approved by a named human)."""
    return shop.list_payments()


@mcp.tool()
def books_tie_out(month: str = "") -> dict:
    """Month-end check (YYYY-MM, default the current shop month): opening cash - payments = balance, every
    paid approval/invoice/PO has its payment row, no negative cash, plus a cash-basis P&L. Lists the
    P&L lines the database does not record (labor, SG&A, interest, taxes, D&A) instead of estimating them."""
    return shop.books_tie_out(month)


@mcp.tool()
def record_price_decision(ticket_id: int, sku: str, qty: int, unit_price: float, decision: str,
                          rationale: str, decided_by: str = "Boss") -> dict:
    """Record the final call on a price/discount request (approved | countered | declined). Refuses below-cost prices."""
    return _safe(shop.record_price_decision, ticket_id, sku, qty, unit_price, decision, rationale, decided_by)


@mcp.tool()
def request_invoice_payment(invoice_id: int, reason: str, ticket_id: int = 0, requested_by: str = "Accounting") -> dict:
    """Prepare payment of a vendor invoice FOR HUMAN APPROVAL. Does not move money."""
    return _safe(shop.request_invoice_payment, ticket_id or None, invoice_id, reason, requested_by)


@mcp.tool()
def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int, reason: str, ticket_id: int = 0,
                           requested_by: str = "Accounting") -> dict:
    """Prepare a prepaid restock purchase order FOR HUMAN APPROVAL. Refused if the vendor has an open unpaid invoice."""
    return _safe(shop.request_purchase_order, ticket_id or None, vendor_id, sku, size, qty, reason, requested_by)


@mcp.tool()
def list_approvals(status: str = "") -> list:
    """Payment / purchase-order requests and their status (pending | paid | rejected | refused)."""
    return shop.list_approvals(status or None)


# ============================================================ facilities
@mcp.tool()
def list_leases() -> list:
    """All leases with monthly rent, next due date and days until due."""
    return shop.list_leases()


@mcp.tool()
def request_rent_payment(lease_id: int, reason: str, ticket_id: int = 0, requested_by: str = "Facilities") -> dict:
    """Prepare a rent payment FOR HUMAN APPROVAL. Does not move money."""
    return _safe(shop.request_rent_payment, ticket_id or None, lease_id, reason, requested_by)


# ============================================================ customer service
@mcp.tool()
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str,
                           author: str = "Customer Service") -> dict:
    """Save a customer/vendor message as a DRAFT on the board. Nothing is ever emailed or sent."""
    return _safe(shop.draft_customer_message, ticket_id, recipient, subject, body, author)


@mcp.tool()
def list_drafts() -> list:
    """All drafted messages on the board."""
    return shop.list_drafts()


# ============================================================ sales & deliveries (read)
@mcp.tool()
def list_sales(ticket_id: int = 0) -> list | dict:
    """Recorded sales (cash in): customer, sku/size, qty, unit price, revenue, COGS and the human cashier."""
    return _safe(shop.list_sales, ticket_id or None)


@mcp.tool()
def list_purchase_orders(status: str = "") -> list | dict:
    """Purchase orders with vendor, qty, ETA and status (ordered | received)."""
    return _safe(shop.list_purchase_orders, status or None)


# ============================================================ HUMAN ONLY
@mcp.tool()
def record_sale(customer: str, sku: str, size: str, qty: int, unit_price: float, cashier: str, secret: str,
                ticket_id: int = 0) -> dict:
    """HUMAN ONLY (the cashier). A customer paid: adds cash and takes the units out of stock
    (this ticket's reserved units first). Refuses below-cost prices and more units than available."""
    if not _check_secret(secret):
        return {"ok": False, "error": "Refused: human secret missing or wrong. Only a cashier can record a sale."}
    return _safe(shop.record_sale, ticket_id or None, customer, sku, size, qty, unit_price, cashier)


@mcp.tool()
def receive_purchase_order(po_id: int, received_by: str, secret: str) -> dict:
    """HUMAN ONLY. The ordered boxes arrived: adds the units to inventory and marks the PO received."""
    if not _check_secret(secret):
        return {"ok": False, "error": "Refused: human secret missing or wrong."}
    return _safe(shop.receive_purchase_order, po_id, received_by)


@mcp.tool()
def approve_and_pay(approval_id: int, approver: str, secret: str) -> dict:
    """HUMAN ONLY. Pays a pending request if cash allows, and updates payments, cash and the invoice/lease/PO."""
    if not _check_secret(secret):
        return {"ok": False, "error": "Refused: human approval secret missing or wrong. Agents cannot pay."}
    return _safe(shop.approve_and_pay, approval_id, approver)


@mcp.tool()
def reject_request(approval_id: int, approver: str, reason: str, secret: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request; no money moves."""
    if not _check_secret(secret):
        return {"ok": False, "error": "Refused: human approval secret missing or wrong."}
    return _safe(shop.reject_request, approval_id, approver, reason)


@mcp.tool()
def reset_database(secret: str) -> dict:
    """HUMAN ONLY. Copy campus_customs.db over campus_customs_new.db (fresh start)."""
    if not _check_secret(secret):
        return {"ok": False, "error": "Refused: human approval secret missing or wrong."}
    return shop.reset_database()


if __name__ == "__main__":
    mcp.run()  # stdio transport
