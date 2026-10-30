"""Campus Customs shop logic - the database layer BEHIND the MCP server.

Only mcp_server/server.py imports this module (plus reset_db.py for the file copy).
The agents and backend never import it; they reach shop facts through MCP tools.
Every MCP tool is a thin wrapper around a function here, so the rules are
enforced no matter who calls them:

  * desk.date_today is "today"; anything due before it is overdue.
  * Vendor lead times come from vendors.lead_days.
  * A vendor will not ship while it has an open (unpaid) invoice.
  * Agents can only REQUEST payments. Money moves only in approve_and_pay(),
    which needs a human approver and the backend's approval secret.
  * The pay step refuses if the cash account would go negative.
  * Cash only goes out (no revenue is modelled).
  * Customer messages are saved as drafts on the board - never sent.
"""
from __future__ import annotations

import calendar
import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from core.config import ORIGINAL_DB, WORKING_DB

CASH_ACCOUNT = "checking"
TICKET_STATUSES = {"open", "in_progress", "awaiting_approval", "blocked", "resolved"}

# Tables added to the WORKING copy only (the original file is never touched).
_EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoice id / lease id / NULL for new PO
    vendor_id INTEGER,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    details TEXT,                    -- JSON (sku, size, qty, unit_cost ...)
    reason TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | rejected | refused
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL,            -- ordered
    ordered_on TEXT NOT NULL,
    eta TEXT NOT NULL,
    ticket_id INTEGER,
    approval_id INTEGER,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',   -- always 'draft': nothing is sent
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    status TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    list_price REAL NOT NULL,
    unit_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    margin_pct REAL NOT NULL,
    decision TEXT NOT NULL,          -- approved | countered | declined
    rationale TEXT,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    reserved_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Opening cash, copied from cash_accounts at reset, so the books can be tied out:
-- opening_balance + SUM(sales) - SUM(payments) must equal the current balance.
CREATE TABLE IF NOT EXISTS cash_opening AS
    SELECT name, balance AS opening_balance, date AS opening_date FROM cash_accounts;
"""

# Sales (cash in). Kept separate so working copies made before sales tracking get it on connect.
_SALES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    customer TEXT NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    revenue REAL NOT NULL,           -- qty * unit_price, added to cash
    cogs REAL NOT NULL,              -- qty * unit_cost (cost of goods sold)
    from_reserved INTEGER NOT NULL,  -- units taken from this ticket's reservation
    account TEXT NOT NULL,
    sold_on TEXT NOT NULL,           -- desk.date_today
    recorded_by TEXT NOT NULL,       -- the human cashier
    created_at TEXT NOT NULL
);
"""


class ShopError(Exception):
    """A store rule refused the action. The message is shown to the agent/human."""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path | str | None = None):
    path = Path(db_path or WORKING_DB)
    if not path.exists():
        reset_database()
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_sales_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_sales_schema(conn) -> None:
    """Add the sales table / PO receiving column to a working copy that predates them."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='purchase_orders'").fetchone():
        return  # not a prepared working copy (reset adds everything)
    conn.executescript(_SALES_SCHEMA)
    if "received_on" not in {r[1] for r in conn.execute("PRAGMA table_info(purchase_orders)")}:
        conn.execute("ALTER TABLE purchase_orders ADD COLUMN received_on TEXT")
        conn.execute("ALTER TABLE purchase_orders ADD COLUMN received_by TEXT")
        conn.commit()


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None


def reset_database() -> dict:
    """Copy the pristine campus_customs.db over campus_customs_new.db.

    The original is opened read-only; only the working copy is (re)written.
    """
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database not found: {ORIGINAL_DB}")
    WORKING_DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = WORKING_DB.with_suffix(".tmp")
    shutil.copyfile(ORIGINAL_DB, tmp)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(_EXTRA_SCHEMA)
        _ensure_sales_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tickets)")}
        if "resolution" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN resolution TEXT")
        if "assigned_to" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN assigned_to TEXT")
        conn.commit()
    finally:
        conn.close()
    tmp.replace(WORKING_DB)
    return {"ok": True, "working_db": str(WORKING_DB), "copied_from": str(ORIGINAL_DB),
            "today": get_today()["date_today"]}


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def _today(conn) -> date:
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()[0])


def get_today() -> dict:
    with connect() as c:
        row = _one(c.execute("SELECT date_today, notes FROM desk"))
    return row


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
def list_tickets(status: str | None = None) -> list[dict]:
    with connect() as c:
        if status:
            return _rows(c.execute("SELECT * FROM tickets WHERE status=? ORDER BY id", (status,)))
        return _rows(c.execute("SELECT * FROM tickets ORDER BY id"))


def get_ticket(ticket_id: int) -> dict:
    with connect() as c:
        t = _one(c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)))
        if not t:
            raise ShopError(f"Ticket {ticket_id} not found")
        t["updates"] = _rows(c.execute(
            "SELECT author,status,note,created_at FROM ticket_updates WHERE ticket_id=? ORDER BY id", (ticket_id,)))
        t["approvals"] = _rows(c.execute(
            "SELECT id,kind,payee,amount,status,decision_note FROM approvals WHERE ticket_id=? ORDER BY id", (ticket_id,)))
        t["drafts"] = _rows(c.execute(
            "SELECT id,recipient,subject,status FROM drafts WHERE ticket_id=? ORDER BY id", (ticket_id,)))
        t["price_decisions"] = _rows(c.execute(
            "SELECT sku,qty,unit_price,decision FROM price_decisions WHERE ticket_id=? ORDER BY id", (ticket_id,)))
        t["sales"] = _rows(c.execute(
            "SELECT id,qty,unit_price,revenue,recorded_by FROM sales WHERE ticket_id=? ORDER BY id", (ticket_id,)))
    return t


def update_ticket(ticket_id: int, status: str, note: str, author: str = "Boss",
                  assigned_to: str | None = None, resolution: str | None = None) -> dict:
    if status not in TICKET_STATUSES:
        raise ShopError(f"status must be one of {sorted(TICKET_STATUSES)}")
    with connect() as c:
        if not c.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone():
            raise ShopError(f"Ticket {ticket_id} not found")
        c.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
        if assigned_to:
            c.execute("UPDATE tickets SET assigned_to=? WHERE id=?", (assigned_to, ticket_id))
        if resolution:
            c.execute("UPDATE tickets SET resolution=? WHERE id=?", (resolution, ticket_id))
        c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                  (ticket_id, author, status, note, _now()))
    return {"ok": True, "ticket_id": ticket_id, "status": status}


# ---------------------------------------------------------------------------
# Inventory & vendors
# ---------------------------------------------------------------------------
def check_stock(sku: str, size: str | None = None) -> list[dict]:
    with connect() as c:
        if size:
            rows = _rows(c.execute("SELECT * FROM inventory WHERE sku=? AND size=?", (sku, size)))
        else:
            rows = _rows(c.execute("SELECT * FROM inventory WHERE sku=? ORDER BY size", (sku,)))
    if not rows:
        raise ShopError(f"No inventory rows for sku={sku} size={size}")
    return rows


def list_inventory() -> list[dict]:
    with connect() as c:
        return _rows(c.execute(
            "SELECT i.*, p.unit_cost, p.list_price FROM inventory i LEFT JOIN pricing p USING(sku) ORDER BY sku,size"))


def _vendor_open_invoices(c, vendor_id: int) -> list[dict]:
    return _rows(c.execute(
        "SELECT id,amount,due_date,status,description FROM invoices WHERE vendor_id=? AND status='open'",
        (vendor_id,)))


def vendor_status(vendor_id: int) -> dict:
    with connect() as c:
        v = _one(c.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)))
        if not v:
            raise ShopError(f"Vendor {vendor_id} not found")
        today = _today(c)
        open_inv = _vendor_open_invoices(c, vendor_id)
    for inv in open_inv:
        inv["overdue"] = date.fromisoformat(inv["due_date"]) < today
        inv["days_overdue"] = max(0, (today - date.fromisoformat(inv["due_date"])).days)
    v["open_invoices"] = open_inv
    v["will_ship"] = not open_inv
    v["eta_if_ordered_today"] = (today + timedelta(days=v["lead_days"])).isoformat()
    if open_inv:
        v["blocker"] = (f"{v['name']} will not ship until open invoice(s) "
                        f"{[i['id'] for i in open_inv]} are paid.")
    return v


def list_vendors() -> list[dict]:
    with connect() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM vendors ORDER BY id")]
    return [vendor_status(i) for i in ids]


_SPECIALTY_HINTS = {"HOOD": "apparel", "TEE": "apparel", "HAT": "apparel", "MUG": "mug"}


def find_restock_vendor(sku: str) -> dict:
    """Suggest the vendor whose specialty matches the SKU family."""
    family = next((k for k in _SPECIALTY_HINTS if k in sku.upper()), None)
    hint = _SPECIALTY_HINTS.get(family)
    vendors = list_vendors()
    matches = [v for v in vendors if hint and hint in v["specialty"].lower()]
    return {"sku": sku, "specialty_needed": hint, "candidates": matches or vendors}


def check_shortfall(sku: str, size: str, qty_needed: int) -> dict:
    row = check_stock(sku, size)[0]
    with connect() as c:
        reserved = c.execute(
            "SELECT COALESCE(SUM(qty),0) FROM stock_reservations WHERE sku=? AND size=?", (sku, size)).fetchone()[0]
        price = _one(c.execute("SELECT unit_cost,list_price FROM pricing WHERE sku=?", (sku,)))
    on_hand = row["qty"]
    short = max(0, qty_needed - on_hand)
    return {"sku": sku, "size": size, "on_hand": on_hand, "qty_needed": qty_needed,
            "shortfall": short, "already_reserved_from_this_stock": reserved,
            "restock_cost_at_unit_cost": round(short * price["unit_cost"], 2) if price else None}


def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, reserved_by: str = "Inventory") -> dict:
    """Pull units off the shelf for a ticket (decrements inventory.qty)."""
    if qty <= 0:
        raise ShopError("qty must be positive")
    with connect() as c:
        row = _one(c.execute("SELECT qty FROM inventory WHERE sku=? AND size=?", (sku, size)))
        if not row:
            raise ShopError(f"No inventory row for {sku} {size}")
        if row["qty"] < qty:
            raise ShopError(f"Only {row['qty']} of {sku} {size} on hand; cannot reserve {qty}.")
        c.execute("UPDATE inventory SET qty=qty-? WHERE sku=? AND size=?", (qty, sku, size))
        c.execute("INSERT INTO stock_reservations(ticket_id,sku,size,qty,reserved_by,created_at) VALUES(?,?,?,?,?,?)",
                  (ticket_id, sku, size, qty, reserved_by, _now()))
        left = c.execute("SELECT qty FROM inventory WHERE sku=? AND size=?", (sku, size)).fetchone()[0]
    return {"ok": True, "reserved": qty, "sku": sku, "size": size, "remaining_on_hand": left}


# ---------------------------------------------------------------------------
# Money - read side
# ---------------------------------------------------------------------------
def get_cash() -> dict:
    with connect() as c:
        acct = _one(c.execute("SELECT * FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)))
        pending = c.execute("SELECT COALESCE(SUM(amount),0) FROM approvals WHERE status='pending'").fetchone()[0]
    acct["pending_approvals_total"] = round(pending, 2)
    acct["balance_after_pending"] = round(acct["balance"] - pending, 2)
    return acct


def list_invoices(status: str | None = None) -> list[dict]:
    with connect() as c:
        today = _today(c)
        q = "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id=i.vendor_id"
        rows = _rows(c.execute(q + (" WHERE i.status=?" if status else "") + " ORDER BY i.id",
                               (status,) if status else ()))
    for r in rows:
        due = date.fromisoformat(r["due_date"])
        r["overdue"] = r["status"] == "open" and due < today
        r["days_overdue"] = max(0, (today - due).days) if r["status"] == "open" else 0
    return rows


def list_leases() -> list[dict]:
    with connect() as c:
        today = _today(c)
        rows = _rows(c.execute("SELECT * FROM leases ORDER BY id"))
    for r in rows:
        due = date.fromisoformat(r["next_due"])
        r["today"] = today.isoformat()
        r["days_until_due"] = (due - today).days
        r["overdue"] = due < today
    return rows


def get_lease(lease_id: int) -> dict:
    for l in list_leases():
        if l["id"] == lease_id:
            return l
    raise ShopError(f"Lease {lease_id} not found")


def list_payments() -> list[dict]:
    with connect() as c:
        return _rows(c.execute("SELECT * FROM payments ORDER BY id"))


def check_margin(sku: str, unit_price: float, qty: int = 1) -> dict:
    with connect() as c:
        p = _one(c.execute("SELECT * FROM pricing WHERE sku=?", (sku,)))
    if not p:
        raise ShopError(f"No pricing for {sku}")
    margin = unit_price - p["unit_cost"]
    return {"sku": sku, "unit_cost": p["unit_cost"], "list_price": p["list_price"], "unit_price": unit_price,
            "qty": qty, "discount_pct": round(100 * (1 - unit_price / p["list_price"]), 1),
            "unit_margin": round(margin, 2), "margin_pct": round(100 * margin / unit_price, 1) if unit_price else None,
            "order_revenue": round(unit_price * qty, 2), "order_gross_profit": round(margin * qty, 2),
            "list_margin_pct": round(100 * (p["list_price"] - p["unit_cost"]) / p["list_price"], 1),
            "below_cost": unit_price < p["unit_cost"]}


def record_price_decision(ticket_id: int, sku: str, qty: int, unit_price: float, decision: str,
                          rationale: str, decided_by: str = "Boss") -> dict:
    if decision not in {"approved", "countered", "declined"}:
        raise ShopError("decision must be approved | countered | declined")
    m = check_margin(sku, unit_price, qty)
    if unit_price < m["unit_cost"] and decision != "declined":
        raise ShopError(f"Refused: ${unit_price} is below unit cost ${m['unit_cost']} - the shop would lose money.")
    with connect() as c:
        c.execute("INSERT INTO price_decisions(ticket_id,sku,qty,list_price,unit_price,unit_cost,margin_pct,decision,"
                  "rationale,decided_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (ticket_id, sku, qty, m["list_price"], unit_price, m["unit_cost"], m["margin_pct"], decision,
                   rationale, decided_by, _now()))
    return {"ok": True, **m, "decision": decision}


# ---------------------------------------------------------------------------
# Money - requests (agents) and execution (humans only)
# ---------------------------------------------------------------------------
def _dupe(c, kind: str, ref_id, vendor_id=None, details=None) -> dict | None:
    if kind == "purchase_order":
        rows = _rows(c.execute("SELECT * FROM approvals WHERE kind='purchase_order' AND status='pending' AND vendor_id=?",
                               (vendor_id,)))
        return next((r for r in rows if r["details"] == details), None)
    return _one(c.execute("SELECT * FROM approvals WHERE kind=? AND ref_id=? AND status='pending'", (kind, ref_id)))


def _insert_approval(c, **kw) -> dict:
    cols = ",".join(kw) + ",created_at"
    c.execute(f"INSERT INTO approvals({cols}) VALUES({','.join('?' * (len(kw) + 1))})", (*kw.values(), _now()))
    aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _one(c.execute("SELECT * FROM approvals WHERE id=?", (aid,)))


def _cash_note(c, amount: float, discretionary: bool = False) -> dict:
    """Cash check for a new request. Refuses requests that could never be paid:
    any request larger than the whole balance, and discretionary spend (purchase orders)
    that doesn't fit after the requests already waiting for approval."""
    bal = c.execute("SELECT balance FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)).fetchone()[0]
    pending = c.execute("SELECT COALESCE(SUM(amount),0) FROM approvals WHERE status='pending'").fetchone()[0]
    after = bal - pending - amount
    if amount > bal + 1e-9:
        raise ShopError(f"Refused: ${amount:,.2f} is more than the ${bal:,.2f} in {CASH_ACCOUNT}. "
                        "It could never be paid, so no request was created.")
    if discretionary and after < -1e-9:
        raise ShopError(f"Refused: this ${amount:,.2f} purchase order doesn't fit. Checking is ${bal:,.2f} with "
                        f"${pending:,.2f} already waiting for approval (${bal - pending:,.2f} free). "
                        "Obligations come first; no request was created.")
    note = {"cash_balance": bal, "other_pending": round(pending, 2), "balance_if_all_paid": round(after, 2)}
    if after < 0:
        note["warning"] = ("Not enough cash to pay this AND every other pending request. "
                           "The pay step will refuse whichever one would go negative.")
    return note


def request_invoice_payment(ticket_id: int | None, invoice_id: int, reason: str, requested_by: str = "Accounting") -> dict:
    with connect() as c:
        inv = _one(c.execute("SELECT i.*, v.name vendor_name FROM invoices i JOIN vendors v ON v.id=i.vendor_id "
                             "WHERE i.id=?", (invoice_id,)))
        if not inv:
            raise ShopError(f"Invoice {invoice_id} not found")
        if inv["status"] != "open":
            raise ShopError(f"Invoice {invoice_id} is already {inv['status']}")
        if (d := _dupe(c, "invoice", invoice_id)):
            return {"ok": True, "already_pending": True, "approval": d}
        note = _cash_note(c, inv["amount"])
        a = _insert_approval(c, ticket_id=ticket_id, kind="invoice", ref_id=invoice_id, vendor_id=inv["vendor_id"],
                             payee=inv["vendor_name"], amount=inv["amount"],
                             details=json.dumps({"description": inv["description"], "due_date": inv["due_date"]}),
                             reason=reason, requested_by=requested_by)
    return {"ok": True, "approval": a, "cash_check": note,
            "next": "Waiting for a HUMAN to approve on the dashboard. No money has moved."}


def request_rent_payment(ticket_id: int | None, lease_id: int, reason: str, requested_by: str = "Facilities") -> dict:
    with connect() as c:
        lease = _one(c.execute("SELECT * FROM leases WHERE id=?", (lease_id,)))
        if not lease:
            raise ShopError(f"Lease {lease_id} not found")
        if (d := _dupe(c, "rent", lease_id)):
            return {"ok": True, "already_pending": True, "approval": d}
        note = _cash_note(c, lease["monthly_rent"])
        a = _insert_approval(c, ticket_id=ticket_id, kind="rent", ref_id=lease_id, payee=lease["landlord"],
                             amount=lease["monthly_rent"],
                             details=json.dumps({"space": lease["space_name"], "due": lease["next_due"]}),
                             reason=reason, requested_by=requested_by)
    return {"ok": True, "approval": a, "cash_check": note,
            "next": "Waiting for a HUMAN to approve on the dashboard. No money has moved."}


def request_purchase_order(ticket_id: int | None, vendor_id: int, sku: str, size: str, qty: int, reason: str,
                           requested_by: str = "Accounting") -> dict:
    """Prepare a prepaid restock order. Cash goes out only when a human approves."""
    if qty <= 0:
        raise ShopError("qty must be positive")
    with connect() as c:
        v = _one(c.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)))
        if not v:
            raise ShopError(f"Vendor {vendor_id} not found")
        open_inv = _vendor_open_invoices(c, vendor_id)
        if open_inv:
            raise ShopError(f"Refused: {v['name']} has open unpaid invoice(s) {[i['id'] for i in open_inv]} "
                            f"and will not ship new product. Get the invoice paid (human approval) first.")
        p = _one(c.execute("SELECT unit_cost FROM pricing WHERE sku=?", (sku,)))
        if not p or not c.execute("SELECT 1 FROM inventory WHERE sku=? AND size=?", (sku, size)).fetchone():
            raise ShopError(f"Unknown sku/size {sku} {size}")
        total = round(p["unit_cost"] * qty, 2)
        details = json.dumps({"sku": sku, "size": size, "qty": qty, "unit_cost": p["unit_cost"],
                              "lead_days": v["lead_days"]}, sort_keys=True)
        if (d := _dupe(c, "purchase_order", None, vendor_id, details)):
            return {"ok": True, "already_pending": True, "approval": d}
        note = _cash_note(c, total, discretionary=True)
        eta = (_today(c) + timedelta(days=v["lead_days"])).isoformat()
        a = _insert_approval(c, ticket_id=ticket_id, kind="purchase_order", vendor_id=vendor_id, payee=v["name"],
                             amount=total, details=details, reason=reason, requested_by=requested_by)
    return {"ok": True, "approval": a, "cash_check": note, "eta_if_approved_today": eta,
            "next": "Waiting for a HUMAN to approve on the dashboard. No money has moved."}


def list_approvals(status: str | None = None) -> list[dict]:
    with connect() as c:
        if status:
            rows = _rows(c.execute("SELECT * FROM approvals WHERE status=? ORDER BY id", (status,)))
        else:
            rows = _rows(c.execute("SELECT * FROM approvals ORDER BY id"))
    for r in rows:
        r["details"] = json.loads(r["details"]) if r["details"] else {}
    return rows


def approve_and_pay(approval_id: int, approver: str) -> dict:
    """HUMAN-ONLY. Executes an approved request in one transaction.

    Refuses (and records the refusal) if cash would go negative or a store rule
    is no longer satisfied. Updates payments, cash_accounts and the related
    invoice / lease / purchase_orders row.
    """
    approver = (approver or "").strip()
    if not approver:
        raise ShopError("A human approver name is required.")
    with connect() as c:
        a = _one(c.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)))
        if not a:
            raise ShopError(f"Approval {approval_id} not found")
        if a["status"] != "pending":
            raise ShopError(f"Approval {approval_id} is already {a['status']}")
        today = _today(c)
        amount = float(a["amount"])
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)).fetchone()[0]

        def refuse(msg):
            c.execute("UPDATE approvals SET status='refused', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
                      (approver, _now(), msg, approval_id))
            if a["ticket_id"]:
                c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                          (a["ticket_id"], "pay tool", None, f"Payment #{approval_id} REFUSED: {msg}", _now()))
            return {"ok": False, "refused": True, "approval_id": approval_id, "reason": msg, "cash_balance": bal}

        if amount > bal + 1e-9:
            return refuse(f"Insufficient cash: ${amount:,.2f} requested, ${bal:,.2f} in {CASH_ACCOUNT}. "
                          f"Paying would make the balance negative.")
        details = json.loads(a["details"] or "{}")
        result: dict = {}
        if a["kind"] == "invoice":
            inv = _one(c.execute("SELECT status FROM invoices WHERE id=?", (a["ref_id"],)))
            if not inv or inv["status"] != "open":
                return refuse(f"Invoice {a['ref_id']} is no longer open.")
            c.execute("UPDATE invoices SET status='paid' WHERE id=?", (a["ref_id"],))
            result["invoice"] = {"id": a["ref_id"], "status": "paid"}
        elif a["kind"] == "rent":
            lease = _one(c.execute("SELECT * FROM leases WHERE id=?", (a["ref_id"],)))
            new_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            note = f"Paid {lease['next_due']} rent ${amount:,.2f} on {today.isoformat()} (approved by {approver})"
            c.execute("UPDATE leases SET next_due=?, notes=? WHERE id=?", (new_due, note, a["ref_id"]))
            result["lease"] = {"id": a["ref_id"], "paid_period_due": lease["next_due"], "next_due": new_due}
        elif a["kind"] == "purchase_order":
            open_inv = _vendor_open_invoices(c, a["vendor_id"])
            if open_inv:
                return refuse(f"Vendor still has open invoice(s) {[i['id'] for i in open_inv]}; it will not ship.")
        else:
            return refuse(f"Unknown approval kind {a['kind']}")

        c.execute("UPDATE cash_accounts SET balance=balance-?, date=? WHERE name=?",
                  (amount, today.isoformat(), CASH_ACCOUNT))
        c.execute("INSERT INTO payments(kind,ref_id,amount,account,paid_at,approved_by) VALUES(?,?,?,?,?,?)",
                  (a["kind"], a["ref_id"], amount, CASH_ACCOUNT, today.isoformat(), approver))
        pay_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if a["kind"] == "purchase_order":
            v = _one(c.execute("SELECT lead_days FROM vendors WHERE id=?", (a["vendor_id"],)))
            eta = (today + timedelta(days=v["lead_days"])).isoformat()
            c.execute("INSERT INTO purchase_orders(vendor_id,sku,size,qty,unit_cost,total,status,ordered_on,eta,"
                      "ticket_id,approval_id,payment_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (a["vendor_id"], details["sku"], details["size"], details["qty"], details["unit_cost"], amount,
                       "ordered", today.isoformat(), eta, a["ticket_id"], approval_id, pay_id))
            c.execute("UPDATE payments SET ref_id=last_insert_rowid() WHERE id=?", (pay_id,))
            result["purchase_order"] = {"id": c.execute("SELECT last_insert_rowid()").fetchone()[0], "eta": eta, **details}
        c.execute("UPDATE approvals SET status='paid', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
                  (approver, _now(), f"Paid as payment #{pay_id}", approval_id))
        new_bal = c.execute("SELECT balance FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)).fetchone()[0]
        if a["ticket_id"]:
            c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                      (a["ticket_id"], approver, None,
                       f"HUMAN APPROVED #{approval_id}: paid ${amount:,.2f} to {a['payee']} (payment #{pay_id})", _now()))
    return {"ok": True, "approval_id": approval_id, "payment_id": pay_id, "amount": amount, "payee": a["payee"],
            "cash_balance_after": new_bal, **result}


def reject_request(approval_id: int, approver: str, reason: str) -> dict:
    """HUMAN-ONLY. Reject a pending request; no money moves."""
    with connect() as c:
        a = _one(c.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)))
        if not a or a["status"] != "pending":
            raise ShopError(f"Approval {approval_id} is not pending")
        c.execute("UPDATE approvals SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
                  (approver, _now(), reason, approval_id))
        if a["ticket_id"]:
            c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                      (a["ticket_id"], approver, None, f"HUMAN REJECTED #{approval_id}: {reason}", _now()))
    return {"ok": True, "approval_id": approval_id, "status": "rejected"}


# ---------------------------------------------------------------------------
# Customer service drafts (never sent)
# ---------------------------------------------------------------------------
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, author: str = "Customer Service") -> dict:
    with connect() as c:
        c.execute("INSERT INTO drafts(ticket_id,recipient,subject,body,author,status,created_at) VALUES(?,?,?,?,?,?,?)",
                  (ticket_id, recipient, subject, body, author, "draft", _now()))
        did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "draft_id": did, "status": "draft",
            "note": "Saved to the board only. Nothing was emailed or sent."}


def list_drafts() -> list[dict]:
    with connect() as c:
        return _rows(c.execute("SELECT * FROM drafts ORDER BY id"))


# ---------------------------------------------------------------------------
# Analysis tools (Inventory health, Accounting tie-out)
# ---------------------------------------------------------------------------
def inventory_health_check(low_stock_threshold: int = 3) -> dict:
    """Every SKU/size with on-hand qty, open-ticket demand, coverage and restock options.

    The database has no sales history, so the reorder signal uses only what is stored:
    on-hand qty, demand from tickets that are not resolved, and the safety-stock
    threshold passed in. Restock ETAs come from vendors.lead_days.
    """
    with connect() as c:
        today = _today(c)
        stock = _rows(c.execute(
            "SELECT i.sku, i.name, i.size, i.qty, i.location, p.unit_cost, p.list_price "
            "FROM inventory i LEFT JOIN pricing p USING(sku) ORDER BY i.sku, i.size"))
        demand = {(r["sku"], r["size"]): (r["qty"], r["tickets"]) for r in _rows(c.execute(
            "SELECT sku, size, SUM(qty) AS qty, GROUP_CONCAT(id) AS tickets FROM tickets "
            "WHERE status != 'resolved' AND sku IS NOT NULL GROUP BY sku, size"))}
        on_order = {(r["sku"], r["size"]): r["qty"] for r in _rows(c.execute(
            "SELECT sku, size, SUM(qty) AS qty FROM purchase_orders GROUP BY sku, size"))}
    vendors_by_sku: dict[str, list] = {}
    items, reorder = [], []
    for s in stock:
        if s["sku"] not in vendors_by_sku:
            vendors_by_sku[s["sku"]] = [
                {k: v[k] for k in ("id", "name", "lead_days", "will_ship", "eta_if_ordered_today")}
                for v in find_restock_vendor(s["sku"])["candidates"]]
        need, tickets = demand.get((s["sku"], s["size"]), (0, None))
        incoming = on_order.get((s["sku"], s["size"]), 0)
        coverage = s["qty"] + incoming - need
        status = "out_of_stock" if s["qty"] == 0 else "low" if s["qty"] <= low_stock_threshold else "ok"
        needs_reorder = coverage < low_stock_threshold
        row = {**s, "status": status, "open_ticket_demand": need, "demand_tickets": tickets,
               "on_order": incoming, "coverage_after_demand": coverage, "needs_reorder": needs_reorder}
        if needs_reorder:
            row["suggested_reorder_qty"] = low_stock_threshold - coverage
            if s["unit_cost"] is not None:
                row["suggested_reorder_cost"] = round(row["suggested_reorder_qty"] * s["unit_cost"], 2)
            row["restock_vendors"] = vendors_by_sku[s["sku"]]
            reorder.append(f"{s['sku']} {s['size']}")
        items.append(row)
    return {"today": today.isoformat(), "low_stock_threshold": low_stock_threshold,
            "needs_reorder": reorder, "items": items,
            "note": "No sales history is stored; demand = quantities on unresolved tickets."}


# ---------------------------------------------------------------------------
# Sales (cash in) and receiving purchase orders - HUMAN-ONLY actions
# ---------------------------------------------------------------------------
def record_sale(ticket_id: int | None, customer: str, sku: str, size: str, qty: int, unit_price: float,
                recorded_by: str) -> dict:
    """HUMAN-ONLY (the cashier). A customer paid: add cash, take the units out of stock.

    Units come first from this ticket's reserved stock (already off the shelf), then from the
    shelf. Refuses below-cost prices, more units than are available, and missing cashier names.
    """
    recorded_by = (recorded_by or "").strip()
    customer = (customer or "").strip()
    if not recorded_by:
        raise ShopError("A human cashier name is required to record a sale.")
    if not customer:
        raise ShopError("Customer name is required.")
    if qty <= 0:
        raise ShopError("qty must be positive")
    with connect() as c:
        price = _one(c.execute("SELECT unit_cost, list_price FROM pricing WHERE sku=?", (sku,)))
        row = _one(c.execute("SELECT qty FROM inventory WHERE sku=? AND size=?", (sku, size)))
        if not price or not row:
            raise ShopError(f"Unknown sku/size {sku} {size}")
        if unit_price < price["unit_cost"]:
            raise ShopError(f"Refused: ${unit_price:,.2f} is below unit cost ${price['unit_cost']:,.2f}.")
        reserved = 0
        if ticket_id:
            if not c.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone():
                raise ShopError(f"Ticket {ticket_id} not found")
            held = c.execute("SELECT COALESCE(SUM(qty),0) FROM stock_reservations WHERE ticket_id=? AND sku=? "
                             "AND size=?", (ticket_id, sku, size)).fetchone()[0]
            used = c.execute("SELECT COALESCE(SUM(from_reserved),0) FROM sales WHERE ticket_id=? AND sku=? "
                             "AND size=?", (ticket_id, sku, size)).fetchone()[0]
            reserved = min(qty, max(0, held - used))
        from_shelf = qty - reserved
        if from_shelf > row["qty"]:
            raise ShopError(f"Only {row['qty'] + reserved} of {sku} {size} available "
                            f"({reserved} reserved for this ticket, {row['qty']} on the shelf); cannot sell {qty}.")
        today = _today(c).isoformat()
        revenue, cogs = round(qty * unit_price, 2), round(qty * price["unit_cost"], 2)
        if from_shelf:
            c.execute("UPDATE inventory SET qty=qty-? WHERE sku=? AND size=?", (from_shelf, sku, size))
        c.execute("UPDATE cash_accounts SET balance=balance+?, date=? WHERE name=?", (revenue, today, CASH_ACCOUNT))
        c.execute("INSERT INTO sales(ticket_id,customer,sku,size,qty,unit_price,unit_cost,revenue,cogs,from_reserved,"
                  "account,sold_on,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (ticket_id, customer, sku, size, qty, unit_price, price["unit_cost"], revenue, cogs, reserved,
                   CASH_ACCOUNT, today, recorded_by, _now()))
        sale_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if ticket_id:
            c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                      (ticket_id, recorded_by, None, f"SALE #{sale_id}: {qty} x {sku} {size} at ${unit_price:,.2f} "
                       f"= ${revenue:,.2f} received from {customer}", _now()))
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)).fetchone()[0]
        left = c.execute("SELECT qty FROM inventory WHERE sku=? AND size=?", (sku, size)).fetchone()[0]
    return {"ok": True, "sale_id": sale_id, "revenue": revenue, "cogs": cogs, "gross_profit": round(revenue - cogs, 2),
            "from_reserved": reserved, "from_shelf": from_shelf, "on_shelf_after": left, "cash_balance_after": bal}


def list_sales(ticket_id: int | None = None) -> list[dict]:
    with connect() as c:
        if ticket_id:
            return _rows(c.execute("SELECT * FROM sales WHERE ticket_id=? ORDER BY id", (ticket_id,)))
        return _rows(c.execute("SELECT * FROM sales ORDER BY id"))


def list_purchase_orders(status: str | None = None) -> list[dict]:
    """Purchase orders with vendor, ETA and whether they have been received."""
    with connect() as c:
        q = "SELECT po.*, v.name AS vendor_name FROM purchase_orders po JOIN vendors v ON v.id=po.vendor_id"
        return _rows(c.execute(q + (" WHERE po.status=?" if status else "") + " ORDER BY po.id",
                               (status,) if status else ()))


def receive_purchase_order(po_id: int, received_by: str) -> dict:
    """HUMAN-ONLY. The boxes arrived: add the ordered units to inventory."""
    received_by = (received_by or "").strip()
    if not received_by:
        raise ShopError("A human name is required to receive an order.")
    with connect() as c:
        po = _one(c.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))
        if not po:
            raise ShopError(f"Purchase order {po_id} not found")
        if po["status"] != "ordered":
            raise ShopError(f"Purchase order {po_id} is already {po['status']}")
        today = _today(c).isoformat()
        c.execute("UPDATE inventory SET qty=qty+? WHERE sku=? AND size=?", (po["qty"], po["sku"], po["size"]))
        c.execute("UPDATE purchase_orders SET status='received', received_on=?, received_by=? WHERE id=?",
                  (today, received_by, po_id))
        if po["ticket_id"]:
            c.execute("INSERT INTO ticket_updates(ticket_id,author,status,note,created_at) VALUES(?,?,?,?,?)",
                      (po["ticket_id"], received_by, None, f"RECEIVED PO #{po_id}: {po['qty']} x {po['sku']} "
                       f"{po['size']} added to stock (ETA was {po['eta']})", _now()))
        on_hand = c.execute("SELECT qty FROM inventory WHERE sku=? AND size=?", (po["sku"], po["size"])).fetchone()[0]
    return {"ok": True, "po_id": po_id, "added": po["qty"], "sku": po["sku"], "size": po["size"],
            "on_hand_after": on_hand, "received_before_eta": today < po["eta"]}


def books_tie_out(month: str = "") -> dict:
    """Month-end tie-out of the cash books, plus a cash-basis P&L for the month.

    Checks: opening cash + sales - payments = current balance; every paid approval has a
    payment; every paid invoice has an invoice payment; every PO payment has a PO row;
    no negative balance. Categories the database does not record are listed as
    not_in_database rather than given made-up numbers.
    """
    with connect() as c:
        today = _today(c)
        month = month or today.strftime("%Y-%m")
        opening = _one(c.execute("SELECT * FROM cash_opening WHERE name=?", (CASH_ACCOUNT,)))
        acct = _one(c.execute("SELECT * FROM cash_accounts WHERE name=?", (CASH_ACCOUNT,)))
        payments = _rows(c.execute("SELECT * FROM payments ORDER BY id"))
        paid_approvals = _rows(c.execute("SELECT id, kind, ref_id, amount FROM approvals WHERE status='paid'"))
        paid_invoices = _rows(c.execute("SELECT id, amount FROM invoices WHERE status='paid'"))
        po_ids = {r[0] for r in c.execute("SELECT id FROM purchase_orders")}
        pending = c.execute("SELECT COALESCE(SUM(amount),0) FROM approvals WHERE status='pending'").fetchone()[0]
        sales = _rows(c.execute("SELECT * FROM sales ORDER BY id"))
    total_paid = round(sum(p["amount"] for p in payments), 2)
    total_sales = round(sum(x["revenue"] for x in sales), 2)
    expected = round(opening["opening_balance"] + total_sales - total_paid, 2)
    issues = []
    if abs(expected - acct["balance"]) > 0.005:
        issues.append(f"Cash does not tie: opening {opening['opening_balance']} + sales {total_sales} - payments "
                      f"{total_paid} = {expected}, but cash_accounts shows {acct['balance']}.")
    for x in sales:
        if not x["recorded_by"]:
            issues.append(f"Sale {x['id']} has no human cashier recorded.")
        if abs(x["revenue"] - round(x["qty"] * x["unit_price"], 2)) > 0.005:
            issues.append(f"Sale {x['id']} revenue does not equal qty x price.")
    if acct["balance"] < 0:
        issues.append(f"Negative cash balance {acct['balance']}.")
    if len(paid_approvals) != len(payments):
        issues.append(f"{len(paid_approvals)} paid approvals but {len(payments)} payment rows.")
    inv_paid_ids = {p["ref_id"] for p in payments if p["kind"] == "invoice"}
    for inv in paid_invoices:
        if inv["id"] not in inv_paid_ids:
            issues.append(f"Invoice {inv['id']} is marked paid but has no invoice payment.")
    for p in payments:
        if p["kind"] == "purchase_order" and p["ref_id"] not in po_ids:
            issues.append(f"Payment {p['id']} is a PO payment with no purchase_orders row.")
        if not p["approved_by"]:
            issues.append(f"Payment {p['id']} has no human approver recorded.")

    month_pay = [p for p in payments if (p["paid_at"] or "").startswith(month)]
    by_kind = {k: round(sum(p["amount"] for p in month_pay if p["kind"] == k), 2)
               for k in ("invoice", "purchase_order", "rent")}
    month_sales = [x for x in sales if x["sold_on"].startswith(month)]
    revenue = round(sum(x["revenue"] for x in month_sales), 2)
    cogs = round(sum(x["cogs"] for x in month_sales), 2)
    return {
        "month": month, "today": today.isoformat(), "ties_out": not issues, "issues": issues,
        "cash": {"opening_balance": opening["opening_balance"], "opening_date": opening["opening_date"],
                 "total_sales": total_sales, "total_payments": total_paid,
                 "expected_balance": expected, "actual_balance": acct["balance"],
                 "pending_approvals": round(pending, 2),
                 "balance_if_all_pending_paid": round(acct["balance"] - pending, 2)},
        "cash_basis_pnl": {
            "revenue (sales)": revenue,
            "cogs (unit cost of units sold)": cogs,
            "gross_profit": round(revenue - cogs, 2),
            "vendor_invoices_paid (inventory)": by_kind["invoice"],
            "purchase_orders_paid (inventory)": by_kind["purchase_order"],
            "rent (occupancy overhead / SG&A)": by_kind["rent"],
            "total_cash_in": revenue,
            "total_cash_out": round(sum(by_kind.values()), 2),
            "net_cash_change": round(revenue - sum(by_kind.values()), 2),
        },
        "units_sold": sum(x["qty"] for x in month_sales),
        "not_in_database": ["labor/payroll", "other SG&A", "interest", "taxes", "depreciation", "amortization"],
        "note": "Cash in = recorded sales; cash out = human-approved payments. Inventory purchases are cash out "
                "when paid; COGS is recognised per unit when sold. EBITDA lines and items below it are not "
                "stored, so they are flagged, not estimated.",
    }
