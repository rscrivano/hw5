"""Problem 4 smoke test: call each MCP tool over a real MCP stdio connection and save evidence.

The server is launched exactly as .mcp.json describes (same command, args and env), so this
exercises the same connection the vibe coder (Claude Code) uses. Each tool result is then
cross-checked against a direct read-only query of data/campus_customs_new.db.

Run:  .venv\\Scripts\\python.exe tests\\mcp_smoke.py
Writes: output/mcp_smoke.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "mcp_smoke.json"

CASES = [
    {
        "prompt": "Using the campus-customs MCP server, call check_stock for SKU CC-TEE-WHITE in size S "
                  "(ticket 101: Tauhid Zaman wants 1 Bulldog tee in size S). How many are on hand?",
        "tool": "check_stock",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S"},
        "ticket": 101,
    },
    {
        "prompt": "Using the campus-customs MCP server, call get_lease for lease 1 "
                  "(ticket 102: Elm City Properties says rent is due in 2 days). What is the rent and when is it due?",
        "tool": "get_lease",
        "arguments": {"lease_id": 1},
        "ticket": 102,
    },
    {
        "prompt": "Using the campus-customs MCP server, call check_margin for 20 x CC-HOOD-NAVY at $45 each "
                  "(ticket 103: Yale AI Club wants a bulk discount). What is the discount and margin?",
        "tool": "check_margin",
        "arguments": {"sku": "CC-HOOD-NAVY", "unit_price": 45, "qty": 20},
        "ticket": 103,
    },
]


def db_rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def check_against_db(tool: str, args: dict, out) -> dict:
    """Compare the tool output with the same facts read straight from the database."""
    if tool == "check_stock":
        expected = db_rows("SELECT sku, name, size, qty, location FROM inventory WHERE sku=? AND size=?",
                           (args["sku"], args["size"]))
        return {"db_query": "SELECT sku, name, size, qty, location FROM inventory WHERE sku='CC-TEE-WHITE' AND size='S'",
                "db_rows": expected, "matches": out == expected}
    if tool == "get_lease":
        lease = db_rows("SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id=?",
                        (args["lease_id"],))[0]
        today = db_rows("SELECT date_today FROM desk")[0]["date_today"]
        fields = ["id", "space_name", "landlord", "monthly_rent", "next_due", "notes"]
        days = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
        ok = all(out.get(f) == lease[f] for f in fields) and out.get("today") == today and out.get("days_until_due") == days
        return {"db_query": "SELECT * FROM leases WHERE id=1; SELECT date_today FROM desk",
                "db_rows": {"lease": lease, "desk.date_today": today, "days_until_due (computed)": days},
                "matches": ok}
    if tool == "check_margin":
        p = db_rows("SELECT sku, unit_cost, list_price FROM pricing WHERE sku=?", (args["sku"],))[0]
        ok = out.get("unit_cost") == p["unit_cost"] and out.get("list_price") == p["list_price"] \
            and out.get("order_gross_profit") == round((args["unit_price"] - p["unit_cost"]) * args["qty"], 2)
        return {"db_query": "SELECT sku, unit_cost, list_price FROM pricing WHERE sku='CC-HOOD-NAVY'",
                "db_rows": p, "matches": ok}
    raise ValueError(tool)


async def main() -> None:
    cfg = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["campus-customs"]
    # .mcp.json uses paths relative to the project root (portable for anyone who clones the repo)
    command = cfg["command"] if Path(cfg["command"]).is_absolute() else str(ROOT / cfg["command"])
    args = [a if Path(a).is_absolute() or not (ROOT / a).exists() else str(ROOT / a) for a in cfg["args"]]
    params = StdioServerParameters(command=command, args=args,
                                   env={**os.environ, **cfg.get("env", {})}, cwd=str(ROOT))
    results = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            for case in CASES:
                res = await session.call_tool(case["tool"], case["arguments"])
                sc = res.structuredContent
                out = sc["result"] if isinstance(sc, dict) and set(sc) == {"result"} else sc
                if out is None:
                    out = json.loads("".join(getattr(c, "text", "") for c in res.content))
                results.append({
                    "ticket": case["ticket"],
                    "prompt_to_vibe_coder": case["prompt"],
                    "tool_name": case["tool"],
                    "arguments": case["arguments"],
                    "is_error": res.isError,
                    "tool_output": out,
                    "db_cross_check": check_against_db(case["tool"], case["arguments"], out),
                })
    evidence = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mcp_server": {"name": init.serverInfo.name, "config_file": ".mcp.json",
                       "command": cfg["command"], "args": cfg["args"], "tools_listed": tools},
        "database": "data/campus_customs_new.db",
        "all_match_database": all(r["db_cross_check"]["matches"] and not r["is_error"] for r in results),
        "tests": results,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({"tools_listed": tools, "all_match_database": evidence["all_match_database"]}))


if __name__ == "__main__":
    asyncio.run(main())
