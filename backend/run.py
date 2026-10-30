"""Run the agent team on tickets from the command line.

    python -m backend.run --ticket 102        # Boss works one ticket (no reset)
    python -m backend.run --all               # FULL RUN: reset the working DB, then every open ticket

A full run always resets data/campus_customs_new.db from the original first.
Payments the agents request wait for a human:  python -m backend.approve list
"""
from __future__ import annotations

import argparse
import asyncio

from backend.team import Team
from mcp_server.shop_db import reset_database  # file copy only; agents never import shop_db


async def main(ticket_ids: list[int] | None, full_run: bool) -> None:
    if full_run:
        print("Resetting working database:", reset_database()["today"])
    team = Team()
    async with team.session() as mcp:
        if ticket_ids is None:
            tickets = await mcp.direct_call_tool("list_tickets", {"status": "open"})
            ticket_ids = [t["id"] for t in tickets]
        for tid in ticket_ids:
            print(f"\n=== Ticket {tid} ===")
            report = await team.run_ticket(tid)
            print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    g.add_argument("--all", action="store_true", help="reset the DB, then run every open ticket")
    a = ap.parse_args()
    asyncio.run(main(None if a.all else a.ticket, full_run=a.all))
