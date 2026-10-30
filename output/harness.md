# Campus Customs: Agent Harness

This file describes the harness the agent team runs inside: the data, the tools, and the rules. It grows with each problem.

- **Original database:** `data/campus_customs.db`. This is never written to. It exists so the shop can be reset.
- **Working copy:** `data/campus_customs_new.db`. The MCP server and the backend read and write only this file (`core/config.py`). Reset it with `python reset_db.py`.
- **Today for the shop:** `desk.date_today` = **2026-08-31**. All overdue and due-soon math uses this date, not the computer clock.

---

## Problem 2: The database

### Tables and fields

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | Holds the shop's "today" (2026-08-31). Every agent uses it to decide what is overdue or due soon. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | This is the work board. Boss reads it to route each ticket, and the `sku`/`size`/`lease_id`/`invoice_id` columns are the foreign keys that link a ticket to the other tables. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` | Shows on-hand stock per SKU and size. Inventory uses it to see whether an order can be filled or is short. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Holds cost and list price per SKU. Accounting uses it for margin checks on discounts and to cost restocks. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Lists who can restock what and how long it takes. Inventory picks a restock vendor here, and `lead_days` is the only source of lead times. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Covers the shop space. Facilities uses it to see what rent is owed and when it is due. |
| `cash_accounts` | `name`, `balance`, `date` | The money the shop has (checking = $3,400). Accounting checks it before any payment, and the pay tool refuses anything that would go negative. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The ledger of money that actually went out (empty at start). A row is written only after a human approves, and `approved_by` records who approved it. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Bills the shop owes vendors. Accounting tracks them, and an `open` invoice blocks that vendor from shipping new product. |

> The reset step also adds bookkeeping tables to the **working copy only** (`approvals`, `purchase_orders`, `drafts`, `ticket_updates`, `price_decisions`, `stock_reservations`, `cash_opening`). These hold pending human approvals, drafts, decisions and the opening cash balance. The original file keeps only the nine tables above.

### Starting data (snapshot of the original)

- **Cash:** checking $3,400.00 (as of 2026-08-31). **Payments:** none.
- **Invoices:** #501, Bulldog Print Co (vendor 1), $840.00, due 2026-08-28, `open`, "Rush reprint CC-TEE-WHITE S". This invoice is **3 days overdue**.
- **Vendors:** 1 Bulldog Print Co (apparel reprint, 5 days) · 2 Elm City Gifts (mugs and small goods, 3 days) · 3 QuickShip CT (local courier, 1 day).
- **Lease:** #1 Chapel Street shop, Elm City Properties, $2,400.00/month, next due 2026-09-02 (2 days away).
- **Pricing:** HOOD-NAVY $22 cost / $58 list · TEE-WHITE $8 / $28 · HAT-BLUE $6 / $22 · MUG-CREST $3.50 / $14.
- **Inventory:** HOOD-NAVY S4 M8 L14 XL6 · TEE-WHITE S0 M5 L3 XL2 · HAT-BLUE OS40 · MUG-CREST OS0.

### The three open tickets and how they link

| Ticket | What it asks | Links to | What the data says |
|---|---|---|---|
| **101** `customer_order` (Tauhid Zaman) | 1 × Bulldog tee, size S | `inventory` (CC-TEE-WHITE, S) → `pricing` → `vendors` (Bulldog Print Co does apparel) → `invoices` (`invoice_id` = 501) | Stock is **0**, so the order can't ship from the shelf. The apparel vendor, Bulldog Print Co, has open invoice #501 for $840 that was due 08-28, so it **won't ship** until that invoice is paid with human approval. After payment, a reprint takes 5 lead days. |
| **102** `rent_notice` (Elm City Properties) | "Shop rent due in 2 days" | `leases` (`lease_id` = 1) → `cash_accounts` | Rent is $2,400, due 2026-09-02, so it is due in 2 days and not yet overdue. Facilities prepares the payment for human approval, and cash ($3,400) covers it. |
| **103** `price_override` (Yale AI Club) | 20 hoodies, size M, bulk discount | `inventory` (CC-HOOD-NAVY, M) → `pricing` → `vendors` | Only **8** are on hand, so the shop is **12 short**. List price is $58 and cost is $22, so any discount has to stay above $22 per unit. The 12-unit restock also comes from Bulldog Print Co, which is blocked by invoice #501. |

**Cash constraint across tickets:** paying invoice #501 ($840) and rent ($2,400) uses $3,240 of the $3,400. That leaves **$160**, which is not enough for a 12-hoodie restock (12 × $22 = $264). No revenue comes in, so the agents have to prioritize.

---

## Problem 3: MCP server tools

Server: `mcp_server/server.py` (FastMCP, server name `campus-customs`). It reads only `data/campus_customs_new.db`. As of Problem 3 it had exactly these three tools. Every agent gets its tools from this server. Each tool returns rows exactly as they are stored in the database, or an error if the row doesn't exist. No tool makes up values.

### The three ticket tools

| # | Tool | Table it reads | Ticket it unlocks |
|---|---|---|---|
| 1 | `check_stock(sku, size)` | `inventory` | **101** |
| 2 | `get_lease(lease_id)` | `leases` (plus `desk.date_today` for days until due) | **102** |
| 3 | `check_margin(sku, unit_price, qty)` | `pricing` | **103** |

1. **`check_stock`, which reads `inventory`, unlocks ticket 101.** Ticket 101 is an order for `CC-TEE-WHITE` size `S`. `check_stock("CC-TEE-WHITE", "S")` returns the actual on-hand qty (0), and that 0 is the fact that turns this order into a restock problem tied to invoice #501.
2. **`get_lease`, which reads `leases`, unlocks ticket 102.** Ticket 102 carries `lease_id = 1`. `get_lease(1)` returns the real rent ($2,400), the landlord and `next_due` (2026-09-02), plus days until due measured from `desk.date_today`. Facilities needs exactly those numbers to confirm the landlord's "due in 2 days" email and set up the rent payment.
3. **`check_margin`, which reads `pricing`, unlocks ticket 103.** Ticket 103 asks for a bulk discount on 20 × `CC-HOOD-NAVY`. `check_margin("CC-HOOD-NAVY", price, 20)` takes `unit_cost` ($22) and `list_price` ($58) from `pricing` and returns the discount %, the per-unit margin and the order's gross profit. That lets Boss and Accounting choose a discount that never sells below cost. It also returns a `below_cost` flag.

Problem 5 adds the rest of the tools (see below).

---

## Problem 4: MCP server connected to the vibe coder

- **Connection file:** `.mcp.json` at the project root registers the `campus-customs` stdio server. The command is `.venv\Scripts\python.exe mcp_server\server.py`. Claude Code loads it when a session starts in the Homework 5 folder.
- **Evidence:** `output/mcp_smoke.json`, produced by `tests/mcp_smoke.py`. The test launches the server exactly as `.mcp.json` describes and calls each of the three tools over MCP. It then checks every output against a direct read-only SQL query of `data/campus_customs_new.db`. All three match (`all_match_database: true`).

---

## Problem 5: The agent team

All five agents are PydanticAI `Agent`s on **gpt-6-luna through Portkey**. They use the OpenAI Responses API, with reasoning effort set to low. Each agent has its prompt in `backend/prompts/`, its role file in `backend/agents/`, and is built in `backend/team.py`. The team is **fully connected**: every agent has a `delegate(teammate, task)` tool that can reach any other agent. The `store_rules.md` prompt is shared by all of them.

| Agent | Job | MCP tools it may use |
|---|---|---|
| **Boss** | Reads each ticket, routes work with clear outcomes (not step-by-step orders), makes final calls including discounts, and sets ticket status | `get_today`, `get_ticket`, `list_tickets`, `get_cash`, `list_approvals`, `update_ticket`, `record_price_decision` |
| **Inventory** | Checks stock by SKU and size, checks overall stock health once per ticket, flags shortfalls, reserves stock, and picks the restock vendor and timing so items are reordered before they run out | `get_today`, `get_ticket`, `check_stock`, `list_inventory`, `inventory_health_check`, `check_shortfall`, `reserve_stock`, `list_vendors`, `vendor_status`, `find_restock_vendor` |
| **Accounting** | Tracks cash, invoices and margins, ties out the books, flags errors early, and prepares invoice payments and POs **for human approval** | `get_today`, `get_ticket`, `get_cash`, `list_invoices`, `list_payments`, `books_tie_out`, `check_margin`, `vendor_status`, `list_approvals`, `request_invoice_payment`, `request_purchase_order` |
| **Facilities** | Handles the shop space (leases, rent), acts before rent is overdue, and prepares rent payments **for human approval** | `get_today`, `get_ticket`, `get_lease`, `list_leases`, `list_approvals`, `request_rent_payment` |
| **Customer Service** | Drafts prompt, respectful, honest messages that calm problems down. Drafts are never sent | `get_today`, `get_ticket`, `check_stock`, `draft_customer_message`, `list_drafts` |

**Agent loop.** Each agent runs through `Agent.iter`. Every step is appended to `output/audit_trail.json`, and the file is never wiped. Each record holds a timestamp, run id, ticket, step number, agent, delegation chain, depth, step kind, model, data and running token usage. Step kinds are: run start, prompt, model request, model response (text and tool calls), each MCP tool call with the exact arguments sent, each tool result, delegation (or a refused delegation), final structured report, errors and run end. Every agent returns an `AgentReport` (defined in `backend/models.py`).

**How to run it:**
- `python -m backend.run --ticket 102` works one ticket.
- `python -m backend.run --all` is a full run: it resets the database, then works every open ticket.
- `python -m backend.approve list|approve|reject` is the human approval desk.

### Every MCP tool and the tables it uses

| Tool | Tables (R = read, W = write) | Used by |
|---|---|---|
| `check_stock` | inventory (R) | Inventory, Customer Service |
| `get_lease` | leases, desk (R) | Facilities |
| `check_margin` | pricing (R) | Accounting |
| `get_today` | desk (R) | all |
| `list_tickets` | tickets (R) | Boss |
| `get_ticket` | tickets, ticket_updates, approvals, drafts (R) | all |
| `update_ticket` | tickets (W), ticket_updates (W) | Boss |
| `get_cash` | cash_accounts, approvals (R) | Boss, Accounting |
| `list_inventory` | inventory, pricing (R) | Inventory |
| `inventory_health_check` | inventory, pricing, tickets, purchase_orders, vendors, invoices, desk (R) | Inventory |
| `check_shortfall` | inventory, pricing, stock_reservations (R) | Inventory |
| `reserve_stock` | inventory (R/W), stock_reservations (W) | Inventory |
| `list_vendors` | vendors, invoices, desk (R) | Inventory |
| `vendor_status` | vendors, invoices, desk (R) | Inventory, Accounting |
| `find_restock_vendor` | vendors, invoices, desk (R) | Inventory |
| `list_invoices` | invoices, vendors, desk (R) | Accounting |
| `list_payments` | payments (R) | Accounting |
| `books_tie_out` | cash_opening, cash_accounts, payments, approvals, invoices, purchase_orders, desk (R) | Accounting |
| `record_price_decision` | pricing (R), price_decisions (W) | Boss |
| `request_invoice_payment` | invoices, vendors, cash_accounts (R), approvals (W) | Accounting |
| `request_purchase_order` | vendors, invoices, pricing, inventory, cash_accounts (R), approvals (W) | Accounting |
| `list_approvals` | approvals (R) | Boss, Accounting, Facilities |
| `list_leases` | leases, desk (R) | Facilities |
| `request_rent_payment` | leases, cash_accounts (R), approvals (W) | Facilities |
| `draft_customer_message` | drafts (W) | Customer Service |
| `list_drafts` | drafts (R) | Customer Service |
| `approve_and_pay` **(human only)** | approvals, cash_accounts, payments, invoices, leases, vendors, purchase_orders, ticket_updates (R/W) | human approval desk only |
| `reject_request` **(human only)** | approvals, ticket_updates (W) | human approval desk only |
| `reset_database` **(human only)** | copies campus_customs.db over the working copy | human only |

Tables marked as bookkeeping (`approvals`, `purchase_orders`, `drafts`, `ticket_updates`, `price_decisions`, `stock_reservations`, `cash_opening`) are created in the working copy at reset. `cash_opening` stores the starting balance so the books can be tied out.

### Safety: guardrails for real customers and real money

**Already enforced in this build:**
- **A human approves every payment.** Agents can only *request* payments. `approve_and_pay` is filtered out of every agent's toolset. It also requires a secret that only the human approval desk generates, and the agents' MCP process never receives it. Every payment row records `approved_by`.
- **No negative cash.** The pay step refuses any amount over the balance and records the refusal.
- **Vendor block.** A purchase order to a vendor with an open invoice is refused, both when it is requested and again when it is paid.
- **No below-cost discounts.** `record_price_decision` refuses any price under unit cost.
- **Nothing leaves the building.** Customer messages are drafts only, and no tool sends email or calls anyone.
- **Agents can't impersonate each other.** Identity fields such as `requested_by`, `author` and `decided_by` are filled in by the backend, not by the model.
- **Facts only from the database.** Tools return stored rows or an error. Categories that aren't in the database (labor, SG&A, interest, taxes, D&A) are flagged, not estimated.
- **Full audit trail.** Every agent-loop step is appended to `output/audit_trail.json`. The original database is never written, and every full run starts from a reset.

**Token limits (all in `core/config.py`, adjustable in `.env`):**
- One model only (`gpt-6-luna`) with **low reasoning effort**.
- At most **4,000 output tokens per response**.
- Per ticket, across all agents: **40 model requests** and **120,000 total tokens**. When a budget runs out, the run stops cleanly with a blocker.
- Delegation depth is capped at **3**. An agent can't delegate to itself or to anyone already in the chain, which prevents loops.
- Each agent takes at most **3 tasks per ticket**, so no one is overloaded.
- The Boss prompt says to delegate outcomes once and trust the reports, not to micro-manage.
- Ticket 102 used about 11k tokens in testing.

**What a real business should add on top:**
- **Daily physical cash audit.** Count the drawer and reconcile the bank feed against `cash_accounts` and `payments` every day, with two people signing off. Run `books_tie_out` monthly and stop all payments if it doesn't tie.
- **Inventory analysis on a schedule.** Do cycle counts so the shelf matches `inventory`, run a weekly `inventory_health_check`, and set reorder points from real sales velocity and vendor lead times.
- **Payment controls.** Use spending limits per approver, require two approvers above a set amount, check for duplicate payments, verify vendor bank details by phone before the first payment, and keep separation of duties so whoever requests a payment can't approve it.
- **Customer experience.** A human reviews every customer message before it is sent, uses a tone guide, responds within one business day, and follows up after the issue is resolved. Track repeat visits and complaints so people want to come back.
- **Privacy and access.** Keep customer data to the minimum needed, give agents read-only access wherever possible, use least-privilege API keys and rotate them, and never put secrets in prompts or logs.
- **Monitoring.** Set alerts on unusual spending, refusals and token spikes, have a kill switch to pause the agents, and review the audit trail regularly.

---

## Problem 7: Backend routes (`backend/main.py`, FastAPI)

Start it from `backend/` with `uvicorn main:app --reload --port 8000`. CORS allows the Vite page at `http://localhost:5173`. Every route reads or writes through the MCP server. The agents' MCP connection has no approval secret. The approve, reject and reset routes use a separate desk connection that holds a fresh secret for each server process.

| Method · URL | What it does |
|---|---|
| `GET /api/tickets` | The three tickets, each with its DB status plus `state`: open / running / resolved (resolved means Boss finished: resolved, awaiting_approval or blocked) |
| `GET /api/tickets/{id}` | One ticket with its update history, linked approvals and drafts |
| `POST /api/tickets/{id}/run` | Starts the agent team on that ticket in the background (one ticket at a time; 409 if busy). Returns the run id |
| `GET /api/runs` | Status of each run started since the server came up (running / finished / error) |
| `GET /api/events?after=N&ticket_id=` | Recent agent events from `output/audit_trail.json`: what each agent said, the tools it called (with args and results), hand-offs and final reports. Poll with the last id you saw |
| `GET /api/tickets/{id}/summary` | Recap of the ticket's latest run: delegation path, each agent's tasks, tools used, final report, and tokens |
| `GET /api/approvals?status=` | Payment and purchase-order requests the agents prepared (pending / paid / rejected / refused) |
| `POST /api/approvals/{id}/approve` | **Human clicked Approve.** Pays it with `approve_and_pay`. This is the only route that changes cash. It needs an `approver` name and refuses anything that would make cash negative |
| `POST /api/approvals/{id}/reject` | Human rejects a request. No money moves |
| `GET /api/cash` | Checking balance from `cash_accounts`, plus pending total, balance if all pending are paid, and opening balance |
| `GET /api/drafts` | Customer Service drafts (never sent) |
| `POST /api/reset` | Copies `campus_customs.db` over the working copy for a fresh run (refused while a run is going) |
| `GET /api/health` | Up check: model name and which ticket is running |

**Fixes made while wiring the API:** In testing, Boss sometimes answered in free text instead of the structured report, and that response ran on until it hit the token cap. Agents now use native structured output: the final answer must match the `AgentReport` schema. The per-response cap is 6,000 tokens, including reasoning. Measured on a scratch copy of the DB: ticket 102 took about 28k tokens over 17 model calls; ticket 101 took about 39k tokens over 19 calls, with the path Boss → Inventory, Accounting, Customer Service (matching the plan in `desk_tickets.html`).

## Problem 8: Agent dashboard (`frontend/`, React + Vite + TypeScript)

`cd frontend` then `npm run dev` opens http://localhost:5173. It talks to the backend at `http://localhost:8000` (change it with `VITE_API_URL`). The layout and design choices are explained in `output/design.md`.

Fix during Problem 9: the desk called `http://localhost:8000`. Browsers can resolve "localhost" to IPv6 (`::1`), while `uvicorn main:app --port 8000` listens on IPv4 only, so requests intermittently failed with `ERR_CONNECTION_REFUSED`. The desk now calls `http://127.0.0.1:8000` by default (`frontend/src/api.ts`). The Approve button also no longer fails silently: with no approver name it highlights the name box.

---

## Problem 9: The full run (results)

The database was reset with `POST /api/reset` (start: **$3,400.00**). Each ticket was run from the desk, then run again after each human decision, for 8 passes in total. Full details are in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json` and `output/resolved_board.html`, all built by `scripts/build_resolved_outputs.py` from the DB and `output/audit_trail.json`.

| Ticket | Passes · tokens · calls | Human decisions | Cash change | Final status |
|---|---|---|---|---|
| 101 | 3 · 105,892 · 47 | #1 invoice 501 $840 **paid**; #3 PO 4 tees $32 **paid** (ETA 2026-09-05) | −$872.00 | blocked until stock arrives |
| 102 | 2 · 44,704 · 25 | #2 rent $2,400 **paid** (next due 2026-10-02) | −$2,400.00 | **resolved** |
| 103 | 3 · 127,587 · 53 | #4 PO 12 hoodies $264 **rejected** (only $160 free) | $0.00 | blocked on cash |

**Cash:** $3,400.00 − $840.00 − $2,400.00 − $32.00 = **$128.00**, which matches `cash_accounts`. There are 3 payment rows, each with `approved_by` = Ryan, and nothing is pending.

**Fixes made during Problem 9:**
- **Desk connection:** the desk now calls the backend at `http://127.0.0.1:8000`, ending the IPv6 connection-refused errors.
- **Approve button:** it explains a missing name instead of sitting silently disabled. There's also a browser-free `approve.bat`.
- **Ticket facts with every hand-off:** `get_ticket` re-reads fell from 10 to 0.
- **Boss rules:** one hand-off for single-area tickets, Customer Service last, offers recorded as `countered`, and no delegating back up the chain.
- **Purchase-order cash guard:** a PO is refused when it's requested if it doesn't fit in checking after pending requests. This was added after 103's $264 request.
- **Scratch test from the same starting data:** 118k → 83k tokens (−30%).

**Revenue:** not part of the Problem 9 run, per the homework rules (cash only goes out). Inventory purchases do reduce cash (payment #3). Sales tracking was added afterwards; see "Extension: Sales tracking" below.

## Summary: what this harness covers

| Area | Where |
|---|---|
| Tables and fields (9 original + 7 bookkeeping) | Problem 2 section above; bookkeeping tables in `mcp_server/shop_db.py` |
| MCP tools (29) with tables and users | Problem 3 and Problem 5 sections; `mcp_server/README.md` |
| The five agents, their prompts and tool slices | Problem 5 section; `backend/prompts/`, `backend/agents/` |
| API routes | Problem 7 section; `backend/main.py` |
| Dashboard | Problem 8 section; `output/design.md`; `frontend/` |
| Safety rules and token limits | "Safety" under Problem 5 |
| Evidence | `output/audit_trail.json` (append-only), `output/mcp_smoke.json`, `output/desk_tickets.html`, `output/resolved_tickets.json`, `output/resolved_board.html` |

### Safety rules in force (summary)
1. **Only a human moves money.** Agents call `request_*` tools, which create pending approvals. `approve_and_pay`, `record_sale` and `receive_purchase_order` are never offered to an agent, need a per-process secret held only by the human desk connection, and record the human's name.
2. **No negative cash.** The pay step refuses any payment larger than the balance.
3. **Vendor block and cash guard.** No purchase order goes to a vendor with an open invoice, or when it doesn't fit in checking after other pending requests. Both are checked when the PO is requested; the vendor block is checked again when it's paid.
4. **No below-cost prices.** `record_price_decision` refuses them.
5. **Drafts only.** Nothing is emailed or sent. Customer messages stay on the board.
6. **No impersonation.** Identity fields (`requested_by`, `author`, `decided_by`) are filled in by the backend.
7. **Facts only from the database.** Missing data is flagged, never estimated.
8. **One model.** Every agent uses gpt-6-luna through Portkey, with low reasoning effort and structured final answers.
9. **Token and loop limits.** At most 6,000 output tokens per response; per ticket, 40 model calls and 120k tokens; delegation depth of 3; no self-delegation and no delegating to anyone already in the chain; at most 3 tasks per agent per ticket.
10. **Audit and reset.** Every agent step is appended to `output/audit_trail.json`, which is never wiped. The original database is never written, and reset needs confirmation and is refused while a run is in progress.

---

## Extension: Sales tracking (added after Problem 9, on request)

The homework rules model cash going **out** only, and the Problem 9 results above follow them. Sales tracking was added afterwards so the books can also show cash coming **in**:

| Piece | What it does |
|---|---|
| `sales` table (working copy) | One row per sale: customer, SKU/size, qty, unit price, revenue, COGS (qty × unit cost), units taken from reserved stock, sale date (`desk.date_today`), human cashier |
| `record_sale` MCP tool (**human only**) | Adds the revenue to `cash_accounts`, takes units from this ticket's reserved stock first and then the shelf, and writes a ticket update. Refuses below-cost prices, more units than available, and a missing cashier name |
| `receive_purchase_order` MCP tool (**human only**) | A person confirms the boxes arrived: adds the PO's units to `inventory` and marks it `received` |
| `list_sales`, `list_purchase_orders` (read) | Boss and Accounting can read sales; Inventory and Accounting can read purchase orders |
| `books_tie_out` | Now checks **opening + sales − payments = balance** and reports revenue, COGS, gross profit and net cash change |
| Routes | `GET/POST /api/sales`, `GET /api/purchase_orders`, `POST /api/purchase_orders/{id}/receive`, `GET /api/inventory`, `GET /api/pricing/{ticket_id}` (prefills the sale: agreed price, else list price) |
| Desk | **Register** panel (record a sale; deliveries with "Mark received"). The cash vault shows "Sales in" and "Paid out" and whether the books tie out |

**Why sales are human-only:** no agent can know a customer actually paid, because every agent message is a draft. A sale is a real-world event, so the cashier records it, just as only a human can approve a payment.

**Tested on a scratch copy of the current data** (your real DB was not changed):
- Receiving PO #1 added 4 tees.
- Selling 1 tee to Tauhid at $28 took cash from $128 to $156, and the books tie out.
- Selling 8 hoodies to the Yale AI Club at $49 brought cash to $548. Opening $3,400 + sales $420 − payments $3,272 = $548 ✓.
- An over-sale, a below-cost price and a missing cashier name were all refused.

---

## Owner's note: what I'd build first for a real business

If Campus Customs were a real shop, **full accounting would be the top priority** before scaling the agent team:
- Expense tables for labor/payroll, other SG&A, interest, taxes, depreciation and amortization, so the P&L reaches EBITDA and net income.
- Accrual bookkeeping: inventory carried as an asset (expensed as COGS when sold), vendor invoices as payables, revenue recognized when earned.
- A scheduled month-end close that produces the P&L and a balance sheet and must tie out before any new spending.
- Scheduled inventory analysis and cash audits, not only when a ticket runs.

Today the system is **cash-basis**: it records cash when it actually moves, and it ties out exactly.
