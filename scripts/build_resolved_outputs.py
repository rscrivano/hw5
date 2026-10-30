"""Problem 9: build output/resolved_tickets.json and output/resolved_board.html from the real run.

Reads the working database (read-only) and the latest run of each ticket in output/audit_trail.json,
so every number comes from the data. Re-run it after approvals change:

    .venv\\Scripts\\python.exe scripts\\build_resolved_outputs.py
"""
from __future__ import annotations

import base64
import html
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
AUDIT = ROOT / "output" / "audit_trail.json"
OUT_JSON = ROOT / "output" / "resolved_tickets.json"
OUT_HTML = ROOT / "output" / "resolved_board.html"
SHOTS = ROOT / "output" / "screenshots"
START_BALANCE = 3400.00  # checking right after the Problem 9 reset (GET /api/cash at reset time)
RESET_AT = "2026-10-29T21:50"  # the Problem 9 reset; every ticket run after it counts
TICKETS = (101, 102, 103)


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


def runs_since_reset(records):
    """All runs of each ticket after the reset, in order (first pass, follow-ups after approvals)."""
    runs: dict[int, dict[str, list]] = {}
    for r in records:
        if r.get("ticket_id") in TICKETS and r["ts"] >= RESET_AT:
            runs.setdefault(r["ticket_id"], {}).setdefault(r["run_id"], []).append(r)
    return {tid: list(by_run.values()) for tid, by_run in runs.items()}


def summarize_run(recs):
    agents: dict[str, dict] = {}
    delegations, refused = [], []
    for r in recs:
        a = agents.setdefault(r["agent"], {"tasks": 0, "tools": [], "contribution": ""})
        d = r.get("data") or {}
        if r["kind"] == "run_start":
            a["tasks"] += 1
        elif r["kind"] == "tool_call" and d.get("tool") not in a["tools"]:
            a["tools"].append(d.get("tool"))
        elif r["kind"] == "delegate":
            delegations.append(f"{r['agent']} -> {d.get('to')}")
        elif r["kind"] == "delegate_refused":
            refused.append({"from": r["agent"], "to": d.get("to"), "reason": d.get("reason")})
        elif r["kind"] == "final_output":
            a["contribution"] = d.get("summary", "")
    end = next((r for r in recs if r["kind"] == "run_end"), None)
    t0, t1 = datetime.fromisoformat(recs[0]["ts"]), datetime.fromisoformat(recs[-1]["ts"])
    return {
        "run_id": recs[0]["run_id"],
        "started": recs[0]["ts"],
        "seconds": round((t1 - t0).total_seconds()),
        "usage": end.get("usage") if end else None,
        "delegations": delegations,
        "refused_handoffs": refused,
        "agents": agents,
        "boss_report": (end or {}).get("data", {}).get("report", {}),
    }


def main() -> None:
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    runs = runs_since_reset(json.loads(AUDIT.read_text(encoding="utf-8")))
    cash = rows(c, "SELECT * FROM cash_accounts WHERE name='checking'")[0]
    payments = rows(c, "SELECT * FROM payments ORDER BY id")

    tickets = []
    for tid in TICKETS:
        t = rows(c, "SELECT * FROM tickets WHERE id=?", (tid,))[0]
        passes = [summarize_run(recs) for recs in runs[tid]]
        agents: dict[str, dict] = {}
        for pa in passes:
            for name, a in pa["agents"].items():
                agg = agents.setdefault(name, {"tasks": 0, "tools": [], "contribution": ""})
                agg["tasks"] += a["tasks"]
                agg["tools"] += [t for t in a["tools"] if t not in agg["tools"]]
                agg["contribution"] = a["contribution"] or agg["contribution"]
        approvals = rows(c, "SELECT id, kind, payee, amount, requested_by, status, decided_by, decided_at, "
                            "decision_note FROM approvals WHERE ticket_id=? ORDER BY id", (tid,))
        totals = {k: sum((pa["usage"] or {}).get(k, 0) for pa in passes) for k in ("total_tokens", "requests")}
        tickets.append({
            "id": tid,
            "type": t["type"],
            "requester": t["requester"],
            "final_status": t["status"],
            "board_state": "resolved" if t["status"] in ("resolved", "awaiting_approval", "blocked") else "open",
            "outcome": passes[-1]["boss_report"].get("summary", ""),
            "passes": [{k: pa[k] for k in ("run_id", "started", "seconds", "usage", "delegations", "refused_handoffs")}
                       | {"boss_summary": pa["boss_report"].get("summary", "")} for pa in passes],
            "totals": totals | {"seconds": sum(pa["seconds"] for pa in passes), "passes": len(passes)},
            "agents": agents,
            "human_approvals": approvals,
            "cash_change": -round(sum(a["amount"] for a in approvals if a["status"] == "paid"), 2),
            "drafts": rows(c, "SELECT id, recipient, subject, status FROM drafts WHERE ticket_id=?", (tid,)),
            "price_decisions": rows(c, "SELECT sku, qty, list_price, unit_price, unit_cost, margin_pct, decision, "
                                       "rationale FROM price_decisions WHERE ticket_id=?", (tid,)),
            "purchase_orders": rows(c, "SELECT id, sku, size, qty, total, status, ordered_on, eta FROM purchase_orders "
                                       "WHERE ticket_id=?", (tid,)),
        })

    end_expected = round(START_BALANCE + sum(t["cash_change"] for t in tickets), 2)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "database": "data/campus_customs_new.db",
        "model": "gpt-6-luna (Portkey)",
        "start_checking_balance": START_BALANCE,
        "end_checking_balance": cash["balance"],
        "end_balance_from_itemized_changes": end_expected,
        "matches_cash_accounts": abs(end_expected - cash["balance"]) < 0.005,
        "payments_made": payments,
        "pending_approvals_total": round(sum(a["amount"] for t in tickets for a in t["human_approvals"]
                                             if a["status"] == "pending"), 2),
        "total_tokens": sum(t["totals"]["total_tokens"] for t in tickets),
        "tickets": tickets,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    cards = []
    for t in tickets:
        shot = SHOTS / f"board_{t['id']}.jpg"
        img = base64.b64encode(shot.read_bytes()).decode() if shot.exists() else ""
        u = t["totals"]
        appr = "".join(f"<li>#{a['id']} {a['kind']} · ${a['amount']:,.2f} to {html.escape(a['payee'])} · "
                       f"<b>{a['status']}</b>{' by ' + html.escape(a['decided_by']) if a['decided_by'] else ''}</li>"
                       for a in t["human_approvals"]) or "<li>None requested</li>"
        passes = "".join(f"<li>Pass {i + 1} ({pa['started'][11:16]}): {html.escape(', '.join(pa['delegations']))} · "
                         f"{(pa['usage'] or {}).get('total_tokens', 0):,} tokens · {pa['seconds']} s</li>"
                         for i, pa in enumerate(t["passes"]))
        cards.append(f"""
<section class="card">
  <h2>Ticket {t['id']} <span class="pill">{t['board_state']} · {t['final_status'].replace('_', ' ')}</span></h2>
  <p class="meta">{html.escape(t['type'].replace('_', ' '))} from {html.escape(t['requester'])} ·
     {u['passes']} passes · {u['total_tokens']:,} tokens · {u['requests']} model calls · {u['seconds']} s ·
     cash change ${t['cash_change']:,.2f}</p>
  {'<img alt="React desk board with ticket ' + str(t['id']) + ' selected after its run" src="data:image/jpeg;base64,' + img + '">' if img else '<p>(screenshot missing)</p>'}
  <p><b>Outcome:</b> {html.escape(t['outcome'])}</p>
  <p><b>Runs:</b></p><ul>{passes}</ul>
  <p><b>Human approvals:</b></p><ul>{appr}</ul>
</section>""")
    OUT_HTML.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resolved Board</title>
<style>
 :root {{ --bg:#fff8f1; --card:#fff; --line:#f0e2d6; --text:#13213f; --muted:#5d6880; --yale:#00356b; --pink:#e0176f; --ok:#0f8a5f; }}
 body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 system-ui,"Segoe UI",Roboto,sans-serif; }}
 header {{ max-width:1100px; margin:0 auto; padding:28px 16px 8px; }}
 h1 {{ color:var(--yale); margin:0; }} h1 span {{ color:var(--pink); }}
 header p {{ color:var(--muted); }}
 main {{ max-width:1100px; margin:0 auto; padding:0 16px 40px; display:grid; gap:22px; }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px 20px; box-shadow:0 10px 30px rgba(19,33,63,.08); }}
 .card h2 {{ margin:0 0 4px; color:var(--yale); }}
 .pill {{ font-size:12px; background:#dcf5ea; color:var(--ok); padding:3px 10px; border-radius:999px; vertical-align:middle; }}
 .meta {{ color:var(--muted); font-size:13px; }}
 img {{ width:100%; height:auto; border-radius:12px; border:1px solid var(--line); }}
 .sum {{ display:flex; gap:12px; flex-wrap:wrap; }} .sum div {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:8px 14px; }}
</style></head><body>
<header><h1>Campus Customs <span>Resolved Board</span></h1>
<p>Screenshots of the React desk (frontend/, localhost:5173) for each ticket after its final Problem 9 run on {report['tickets'][0]['passes'][0]['started'][:10]}. Built from the working database and output/audit_trail.json by scripts/build_resolved_outputs.py.</p>
<div class="sum"><div>Start checking <b>${START_BALANCE:,.2f}</b></div><div>End checking <b>${cash['balance']:,.2f}</b> (cash_accounts)</div>
<div>Waiting for approval <b>${report['pending_approvals_total']:,.2f}</b></div><div>Tokens <b>{report['total_tokens']:,}</b></div></div></header>
<main>{''.join(cards)}</main></body></html>""", encoding="utf-8")
    print(json.dumps({"end_balance": cash["balance"], "matches": report["matches_cash_accounts"],
                      "pending": report["pending_approvals_total"], "tokens": report["total_tokens"]}))


if __name__ == "__main__":
    main()
