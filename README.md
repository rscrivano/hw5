# Campus Customs: Multi-Agent Operations (Homework 5)

Five AI agents (Boss, Inventory, Accounting, Facilities, Customer Service) work the shop's ticket board. They read and write the shop database only through an **MCP server**. A **FastAPI** backend runs the team, and a **React** desk lets a human watch them and approve every payment.

```
 React desk (frontend/, :5173) ──HTTP──▶ FastAPI (backend/main.py, :8000) ──MCP (stdio)──▶ MCP server ──▶ data/campus_customs_new.db
                                          └─ agent team (PydanticAI, gpt-6-luna via Portkey)
```

| Piece | Path |
|---|---|
| MCP server (FastMCP, 33 tools; store rules in `shop_db.py`) | `mcp_server/` (see `mcp_server/README.md`) |
| Agent team: prompts, roles, data types, agent loop | `backend/prompts/`, `backend/agents/`, `backend/models.py`, `backend/team.py` |
| FastAPI routes for the desk | `backend/main.py` |
| React + Vite + TypeScript desk | `frontend/` |
| Write-ups and evidence | `output/` (harness, plan vs. actual, design, resolved tickets, audit trail) |
| Prompt log | `AI_prompts.md` |

**Model:** every agent uses `gpt-6-luna` through Portkey. The name appears once, in `core/config.py`.

---

## 0. One-time setup

You need Python 3.11+, Node 18+, and a Portkey API key.

```
python -m venv .venv
.venv\Scripts\activate              (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cd frontend && npm install && cd ..
copy .env.example .env              (macOS/Linux: cp .env.example .env)
```
Put your key in `.env` as `PORTKEY_API_KEY=...`. `.env` is git-ignored and never committed. On Windows, `setup.bat` does the Python steps for you.

## 1. Copy the original DB to the working copy (clean run)

`data/campus_customs.db` is the **original** and is never written to. Everything runs on `data/campus_customs_new.db`, the **working copy**. To start clean, copy the original over the working copy:
```
python reset_db.py
```
This copies the file and adds the bookkeeping tables (approvals, drafts, sales and so on) to the working copy only. You can also click **Reset DB** on the desk, or call `POST /api/reset`.

## 2. Start the MCP server

The backend **starts the MCP server for you** (stdio), so in normal use you skip this step. To run or inspect it on its own:
```
python mcp_server/server.py
```
To use it from Claude Code, `.mcp.json` registers the same server; on macOS/Linux, change `.venv/Scripts/python.exe` to `.venv/bin/python`. `python tests/mcp_smoke.py` calls the tools over MCP and checks them against the database (writes `output/mcp_smoke.json`).

## 3. Start the FastAPI backend

```
cd backend
uvicorn main:app --reload --port 8000
```
The backend runs at http://localhost:8000 (`/api/health`) and allows the Vite page at `http://localhost:5173`. Every route is listed in `output/harness.md`.

## 4. Start the React board

In a second terminal:
```
cd frontend
npm run dev
```
This opens http://localhost:5173. Pick a ticket and press **Start team** to watch the agents. Type your name under **Needs your OK** to approve or reject the payments they prepare; nothing is paid without you. The **Register** records a sale or marks a delivery received.

## 5. Reset the DB before a full three-ticket run

Always start a full run from the original data:
1. Click **Reset DB** on the desk (or run `python reset_db.py`). Checking goes back to **$3,400.00**.
2. Run tickets **101**, **102** and **103** (Start team on each, one at a time).
3. Approve or reject each payment request, then press **Run again** so Boss can close the ticket.

From the command line instead: `python -m backend.run --all` resets and runs all three, and `python -m backend.approve interactive` (or double-click `approve.bat`) is a console approval desk.

---

## Store rules (enforced in `mcp_server/shop_db.py`)
- `desk.date_today` (2026-08-31) is "today"; anything due before it is overdue. Vendor lead times come from `vendors.lead_days`.
- A vendor won't ship while it has an open unpaid invoice.
- **A human approves every payment.** Agents only create pending requests. Paying needs a secret that only the human desk holds, and each payment records `approved_by`.
- No negative cash. Purchase orders that don't fit in available cash are refused when they're requested.
- Customer messages are drafts only; nothing is sent.
- Sales and receiving deliveries are recorded by a human (an extension; the graded run models cash going out only).

## Results
See `output/desk_tickets.html` (plan vs. actual, cash, reflection), `output/resolved_board.html` (desk screenshots) and `output/resolved_tickets.json`. After the full run: 102 is resolved, 101 is blocked until its restock arrives (ETA 2026-09-05), and 103 is blocked on cash. Checking went from **$3,400.00 to $128.00** (invoice $840, rent $2,400, tee restock $32, all human-approved), which matches `cash_accounts`.
