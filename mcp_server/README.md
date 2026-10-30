# Campus Customs MCP Server

## What it's for
This MCP server is the only gateway between the Campus Customs agent team and the shop's data. Claude Code (the vibe coder) uses it too, through `.mcp.json`. The five agents (Boss, Inventory, Accounting, Facilities, Customer Service) never open the database themselves. They call tools on this server, and each tool runs a fixed, parameterized query in `shop_db.py`, where the store rules are enforced. This means:

- Agents work only from facts that are actually in the database. A tool returns stored rows, or an error such as "No inventory rows for sku=…". It never returns a guessed value.
- Dates are measured against `desk.date_today` (the shop's "today"), not the computer clock.
- An open invoice blocks that vendor from shipping. The pay step refuses any payment that would make cash negative. Customer messages are saved as drafts only.
- **Payments need a human.** Agents can only call `request_*` tools, which create a *pending* approval. Money moves only in `approve_and_pay`, which requires the approval secret in `CC_APPROVAL_SECRET`. Only the human approval desk (`python -m backend.approve`) sets that secret, so neither the agents nor Claude Code can pay.

The server is built with **FastMCP** (`mcp.server.fastmcp`) and uses the stdio transport. To run it on its own, for example with MCP Inspector, use `python mcp_server/server.py`.

| File | Purpose |
|---|---|
| `server.py` | FastMCP tool definitions |
| `shop_db.py` | The SQL and store rules behind each tool. Only this server (and `reset_db.py`) imports it |

## Which database it uses
- **`data/campus_customs_new.db`** is the working copy, and every query goes here. The path is set once, in `core/config.py` (`WORKING_DB`).
- `data/campus_customs.db` is the original. It is never written to. It is only copied over the working copy on a reset (`python reset_db.py`).

## Tools

### The three ticket tools (Problem 3)
| Tool | Reads | Returns | Unlocks |
|---|---|---|---|
| `check_stock(sku, size="")` | `inventory` | On-hand `qty` and `location` for a SKU, either for one size or for all sizes | **Ticket 101**: CC-TEE-WHITE size S has qty 0, so the order needs a restock |
| `get_lease(lease_id)` | `leases`, plus `desk.date_today` | `monthly_rent`, `landlord`, `next_due`, `today`, days until due, and an overdue flag | **Ticket 102**: lease 1 rent is $2,400, due 2026-09-02 (2 days out) |
| `check_margin(sku, unit_price, qty=1)` | `pricing` | `unit_cost`, `list_price`, discount %, unit margin, margin %, order gross profit, and a `below_cost` flag | **Ticket 103**: bulk-discount math for 20 × CC-HOOD-NAVY (cost $22, list $58) |

### Tools added for the agent team (Problem 5)
| Area | Tool | Tables |
|---|---|---|
| Board | `get_today` | desk |
| | `list_tickets(status)` | tickets |
| | `get_ticket(ticket_id)` | tickets, ticket_updates, approvals, drafts |
| | `update_ticket(ticket_id, status, note, …)` | tickets, ticket_updates (write) |
| Inventory | `list_inventory` | inventory, pricing |
| | `inventory_health_check(low_stock_threshold)` | inventory, pricing, tickets, purchase_orders, vendors, invoices |
| | `check_shortfall(sku, size, qty_needed)` | inventory, pricing, stock_reservations |
| | `reserve_stock(ticket_id, sku, size, qty)` | inventory, stock_reservations (write) |
| | `list_vendors`, `vendor_status(vendor_id)`, `find_restock_vendor(sku)` | vendors, invoices, desk |
| Accounting | `get_cash` | cash_accounts, approvals |
| | `list_invoices(status)` | invoices, vendors, desk |
| | `list_payments` | payments |
| | `books_tie_out(month)` | cash_opening, cash_accounts, payments, sales, approvals, invoices, purchase_orders (opening + sales − payments = balance) |
| | `record_price_decision(…)` | pricing, price_decisions (write). Refuses below-cost prices |
| | `request_invoice_payment(invoice_id, reason)` | invoices, approvals (write: pending, for a human) |
| | `request_purchase_order(vendor_id, sku, size, qty, reason)` | vendors, invoices, pricing, approvals (write: pending). Refused while the vendor has an open invoice |
| | `list_approvals(status)` | approvals |
| Facilities | `list_leases` | leases, desk |
| | `request_rent_payment(lease_id, reason)` | leases, approvals (write: pending, for a human) |
| Customer Service | `draft_customer_message(ticket_id, recipient, subject, body)` | drafts (write; never sent) |
| | `list_drafts` | drafts |
| Sales & deliveries | `list_sales(ticket_id)` | sales |
| | `list_purchase_orders(status)` | purchase_orders, vendors |
| **Human only** | `approve_and_pay(approval_id, approver, secret)` | approvals, cash_accounts, payments, invoices, leases, purchase_orders |
| | `record_sale(customer, sku, size, qty, unit_price, cashier, secret, ticket_id)` | sales, cash_accounts (cash **in**), inventory, stock_reservations, ticket_updates |
| | `receive_purchase_order(po_id, received_by, secret)` | purchase_orders, inventory, ticket_updates |
| | `reject_request(approval_id, approver, reason, secret)` | approvals, ticket_updates |
| | `reset_database(secret)` | copies the original over the working copy |
