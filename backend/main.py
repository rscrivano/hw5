"""Campus Customs desk API (FastAPI) - what the React dashboard calls.

Start it from the backend/ folder:
    uvicorn main:app --reload --port 8000

Every shop fact goes through the MCP server. The app keeps two MCP connections open:
  * `team.mcp` - the agents' connection (no approval secret, so it can never pay or reset)
  * `desk`     - the human desk's connection, holding a fresh approval secret for this process.
                 Only the approve / reject / reset routes use the human-only tools on it.
Agent events come from the append-only output/audit_trail.json the agents write as they run.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `uvicorn main:app` works from backend/

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402

from backend.mcp_tools import mcp_client  # noqa: E402
from backend.team import Team, new_run_id  # noqa: E402
from core.config import AUDIT_TRAIL, MODEL  # noqa: E402

APPROVAL_SECRET = secrets.token_urlsafe(32)
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
CLOSED_STATUSES = {"resolved", "awaiting_approval", "blocked"}  # Boss has finished working the ticket

state: dict = {"team": None, "desk": None, "runs": {}, "lock": asyncio.Lock()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    team = Team()
    desk = MCPToolset(mcp_client(approval_secret=APPROVAL_SECRET))
    async with team.session(), desk:
        state["team"], state["desk"] = team, desk
        yield


app = FastAPI(title="Campus Customs Desk API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])


async def mcp(tool: str, args: dict | None = None):
    """Call an MCP tool on the human desk connection. Shop rule refusals come back as 400s."""
    result = await state["desk"].direct_call_tool(tool, args or {})
    if isinstance(result, dict) and result.get("ok") is False:
        raise HTTPException(400, result.get("error") or "Refused")
    return result


def as_list(value) -> list:
    # A one-row list comes back from MCP as a bare object.
    return value if isinstance(value, list) else [] if value in (None, "") else [value]


def busy() -> int | None:
    return next((tid for tid, r in state["runs"].items() if r["status"] == "running"), None)


# ===================================================================== tickets
@app.get("/api/tickets")
async def tickets():
    """The tickets on the board, each marked open or resolved."""
    rows = as_list(await mcp("list_tickets"))
    out = []
    for t in rows:
        run = state["runs"].get(t["id"])
        running = bool(run and run["status"] == "running")
        out.append({**t, "running": running,
                    "state": "running" if running else "resolved" if t["status"] in CLOSED_STATUSES else "open",
                    "last_run": run})
    return out


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int):
    return await mcp("get_ticket", {"ticket_id": ticket_id})


async def _run(ticket_id: int, run_id: str) -> None:
    run = state["runs"][ticket_id]
    try:
        report = await state["team"].run_ticket(ticket_id, run_id=run_id)
        run.update(status="finished", report=report.model_dump())
    except Exception as e:  # noqa: BLE001
        run.update(status="error", error=f"{type(e).__name__}: {e}")
    finally:
        run["finished_at"] = datetime.now().isoformat(timespec="seconds")


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    """Start the agent team on one ticket. Returns at once; watch /api/events for progress."""
    async with state["lock"]:
        if (other := busy()) is not None:
            raise HTTPException(409, f"The team is already working ticket {other}. One ticket at a time.")
        await mcp("get_ticket", {"ticket_id": ticket_id})  # 400 if it doesn't exist
        run_id = new_run_id()
        state["runs"][ticket_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                                    "started_at": datetime.now().isoformat(timespec="seconds")}
        asyncio.create_task(_run(ticket_id, run_id))
    return state["runs"][ticket_id]


@app.get("/api/runs")
async def runs():
    return list(state["runs"].values())


# ===================================================================== agent events
SHOWN_KINDS = {"run_start", "model_response", "tool_call", "tool_result", "delegate", "delegate_refused",
               "final_output", "error", "run_end"}


def _read_audit() -> list[dict]:
    try:
        records = json.loads(AUDIT_TRAIL.read_text(encoding="utf-8"))
        return records if isinstance(records, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _short(value, n: int = 400) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


def _event(i: int, r: dict) -> dict | None:
    kind, data = r["kind"], r.get("data") or {}
    if kind not in SHOWN_KINDS:
        return None
    e = {"id": i, "ts": r["ts"], "run_id": r["run_id"], "ticket_id": r["ticket_id"], "agent": r["agent"],
         "chain": r["chain"], "kind": kind, "text": "", "tool": None, "detail": None}
    if kind == "run_start":
        e["text"] = data.get("task", "")
    elif kind == "model_response":
        e["text"] = " ".join(t for t in data.get("text", []) if t).strip()
        if not e["text"]:
            return None  # tool calls are shown by their own tool_call events
    elif kind in ("tool_call", "tool_result"):
        e["tool"] = data.get("tool")
        e["detail"] = _short(data.get("args") if kind == "tool_call" else data.get("result"))
    elif kind in ("delegate", "delegate_refused"):
        e["tool"] = "delegate"
        e["text"] = data.get("task", "")
        e["detail"] = data.get("to") if kind == "delegate" else data.get("reason")
    elif kind == "final_output":
        e["text"] = data.get("summary", "")
        e["detail"] = data
    elif kind == "error":
        e["text"] = data.get("error", "")
    elif kind == "run_end":
        e["text"] = (data.get("report") or {}).get("summary", "")
        e["detail"] = {"usage": r.get("usage"), "tasks_per_agent": data.get("tasks_per_agent")}
    return e


@app.get("/api/events")
async def events(after: int = -1, ticket_id: int | None = None, limit: int = 300):
    """Recent agent events (what each agent said, which tools it used) after event id `after`."""
    records = _read_audit()
    out = []
    for i in range(max(after + 1, 0), len(records)):
        r = records[i]
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        if (e := _event(i, r)) is not None:
            out.append(e)
    return {"events": out[-limit:], "last_id": len(records) - 1}


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int):
    """What each agent did on the ticket's latest run: tasks, tools used, final report, tokens."""
    records = [r for r in _read_audit() if r.get("ticket_id") == ticket_id]
    if not records:
        return {"ticket_id": ticket_id, "run_id": None, "agents": [], "usage": None, "finished": False}
    run_id = records[-1]["run_id"]
    agents: dict[str, dict] = {}
    usage, finished, delegations = None, False, []
    for r in (r for r in records if r["run_id"] == run_id):
        a = agents.setdefault(r["agent"], {"agent": r["agent"], "tasks": 0, "tools": {}, "summary": "",
                                           "actions": [], "approvals": []})
        data = r.get("data") or {}
        if r["kind"] == "run_start":
            a["tasks"] += 1
        elif r["kind"] == "tool_call":
            a["tools"][data.get("tool")] = a["tools"].get(data.get("tool"), 0) + 1
        elif r["kind"] == "delegate":
            delegations.append({"from": r["agent"], "to": data.get("to"), "task": data.get("task")})
        elif r["kind"] == "final_output":
            a["summary"] = data.get("summary", "")
            a["actions"] = data.get("actions_taken", [])
            a["approvals"] = data.get("approvals_requested", [])
        elif r["kind"] == "run_end":
            usage, finished = r.get("usage"), True
    return {"ticket_id": ticket_id, "run_id": run_id, "finished": finished, "usage": usage, "model": MODEL,
            "delegations": delegations, "agents": list(agents.values())}


# ===================================================================== approvals & cash
class Decision(BaseModel):
    approver: str = Field(min_length=1, description="Name of the human approving or rejecting")
    reason: str = ""


@app.get("/api/approvals")
async def approvals(status: str = ""):
    return as_list(await mcp("list_approvals", {"status": status}))


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: Decision):
    """A human clicked Approve: pay the request. This is the only route that moves cash."""
    result = await state["desk"].direct_call_tool(
        "approve_and_pay", {"approval_id": approval_id, "approver": body.approver.strip(), "secret": APPROVAL_SECRET})
    if isinstance(result, dict) and result.get("ok") is False and not result.get("refused"):
        raise HTTPException(400, result.get("error") or "Refused")
    return result  # a cash refusal (would go negative) is returned with refused: true


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: Decision):
    return await mcp("reject_request", {"approval_id": approval_id, "approver": body.approver.strip(),
                                        "reason": body.reason or "Rejected on the desk", "secret": APPROVAL_SECRET})


@app.get("/api/cash")
async def cash():
    """The checking balance from cash_accounts, plus what is waiting for approval and cash in / out so far."""
    books = await mcp("books_tie_out")
    return {**await mcp("get_cash"), "opening_balance": books["cash"]["opening_balance"],
            "total_sales": books["cash"]["total_sales"], "total_payments": books["cash"]["total_payments"],
            "ties_out": books["ties_out"]}


# ===================================================================== sales & deliveries
class Sale(BaseModel):
    cashier: str = Field(min_length=1, description="Name of the human recording the sale")
    customer: str = Field(min_length=1)
    sku: str
    size: str
    qty: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    ticket_id: int | None = None


class Receipt(BaseModel):
    received_by: str = Field(min_length=1)


@app.get("/api/sales")
async def sales():
    return as_list(await mcp("list_sales"))


@app.post("/api/sales")
async def record_sale(body: Sale):
    """A human cashier rang up a sale: cash goes up, stock goes down. Refuses below-cost or over-stock sales."""
    return await mcp("record_sale", {"customer": body.customer.strip(), "sku": body.sku, "size": body.size,
                                     "qty": body.qty, "unit_price": body.unit_price, "cashier": body.cashier.strip(),
                                     "ticket_id": body.ticket_id or 0, "secret": APPROVAL_SECRET})


@app.get("/api/purchase_orders")
async def purchase_orders():
    return as_list(await mcp("list_purchase_orders"))


@app.post("/api/purchase_orders/{po_id}/receive")
async def receive(po_id: int, body: Receipt):
    """A human confirms the order arrived: the units are added to inventory."""
    return await mcp("receive_purchase_order", {"po_id": po_id, "received_by": body.received_by.strip(),
                                                "secret": APPROVAL_SECRET})


@app.get("/api/inventory")
async def inventory():
    return as_list(await mcp("list_inventory"))


@app.get("/api/pricing/{ticket_id}")
async def ticket_price(ticket_id: int):
    """The agreed price for a ticket (latest price decision), else the list price - prefills the sale form."""
    t = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not t.get("sku"):
        return {"ticket_id": ticket_id, "sku": None}
    item = next((i for i in as_list(await mcp("list_inventory"))
                 if i["sku"] == t["sku"] and i["size"] == t["size"]), None)
    agreed = [d for d in t.get("price_decisions") or [] if d["decision"] in ("approved", "countered")]
    sold = sum(s["qty"] for s in t.get("sales") or [])
    return {"ticket_id": ticket_id, "customer": t["requester"], "sku": t["sku"], "size": t["size"],
            "qty": t["qty"], "already_sold": sold, "on_shelf": item["qty"] if item else 0,
            "list_price": item["list_price"] if item else None, "unit_cost": item["unit_cost"] if item else None,
            "agreed_price": agreed[-1]["unit_price"] if agreed else None}


@app.get("/api/drafts")
async def drafts():
    return as_list(await mcp("list_drafts"))


# ===================================================================== reset
@app.post("/api/reset")
async def reset():
    """Copy the original campus_customs.db over the working copy for a fresh run."""
    if (other := busy()) is not None:
        raise HTTPException(409, f"Wait for ticket {other} to finish before resetting.")
    result = await mcp("reset_database", {"secret": APPROVAL_SECRET})
    state["runs"].clear()
    return result


@app.get("/api/health")
async def health():
    return {"ok": True, "model": MODEL, "running": busy()}
