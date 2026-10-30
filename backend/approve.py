"""Human approval desk (command line). Works without the browser.

    approve.bat                                   (double-click: asks your name, walks each pending request)
    python -m backend.approve interactive
    python -m backend.approve list
    python -m backend.approve approve 3 --approver "Ryan S"
    python -m backend.approve reject 3 --approver "Ryan S" --reason "Pay rent first"

Talks to the MCP server's human-only tools with a one-time approval secret generated here.
The agent team's MCP connection never has this secret, so agents can't pay.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # runnable from any folder

from pydantic_ai.mcp import MCPToolset  # noqa: E402

from backend.mcp_tools import mcp_client  # noqa: E402


def _as_list(value) -> list:
    return value if isinstance(value, list) else [] if value in (None, "") else [value]


async def interactive(mcp: MCPToolset, secret: str) -> None:
    cash = await mcp.direct_call_tool("get_cash", {})
    pending = _as_list(await mcp.direct_call_tool("list_approvals", {"status": "pending"}))
    print(f"\nChecking balance: ${cash['balance']:,.2f}   Pending requests: {len(pending)}")
    if not pending:
        print("Nothing to approve.")
        return
    name = ""
    while not name:
        name = input("Your name (recorded as the approver): ").strip()
    for a in pending:
        print(f"\n#{a['id']}  {a['kind']}  ${a['amount']:,.2f}  to {a['payee']}  (ticket {a['ticket_id']}, "
              f"prepared by {a['requested_by']})\n    {a['reason']}")
        choice = ""
        while choice not in ("a", "r", "s"):
            choice = input("    [a]pprove & pay / [r]eject / [s]kip? ").strip().lower()[:1]
        if choice == "a":
            out = await mcp.direct_call_tool("approve_and_pay", {"approval_id": a["id"], "approver": name,
                                                                 "secret": secret})
            if out.get("ok"):
                print(f"    PAID payment #{out['payment_id']}. Checking is now ${out['cash_balance_after']:,.2f}")
            else:
                print(f"    NOT PAID: {out.get('reason') or out.get('error')}")
        elif choice == "r":
            reason = input("    Reason: ").strip() or "Rejected at the approval desk"
            out = await mcp.direct_call_tool("reject_request", {"approval_id": a["id"], "approver": name,
                                                                "reason": reason, "secret": secret})
            print("    Rejected. No money moved." if out.get("ok") else f"    Error: {out.get('error')}")
    cash = await mcp.direct_call_tool("get_cash", {})
    print(f"\nDone. Checking balance: ${cash['balance']:,.2f}")


async def main(a: argparse.Namespace) -> None:
    secret = secrets.token_urlsafe(32)
    async with MCPToolset(mcp_client(approval_secret=secret)) as mcp:
        if a.cmd == "interactive":
            await interactive(mcp, secret)
            return
        if a.cmd == "list":
            out = {"cash": await mcp.direct_call_tool("get_cash", {}),
                   "pending": _as_list(await mcp.direct_call_tool("list_approvals", {"status": "pending"}))}
        elif a.cmd == "approve":
            out = await mcp.direct_call_tool("approve_and_pay", {"approval_id": a.id, "approver": a.approver,
                                                                 "secret": secret})
        else:
            out = await mcp.direct_call_tool("reject_request", {"approval_id": a.id, "approver": a.approver,
                                                                "reason": a.reason, "secret": secret})
        print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("interactive")
    sub.add_parser("list")
    p = sub.add_parser("approve"); p.add_argument("id", type=int); p.add_argument("--approver", required=True)
    r = sub.add_parser("reject"); r.add_argument("id", type=int); r.add_argument("--approver", required=True)
    r.add_argument("--reason", required=True)
    asyncio.run(main(ap.parse_args()))
