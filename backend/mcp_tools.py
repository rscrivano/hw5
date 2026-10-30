"""Connects the agent team to the Campus Customs MCP server (stdio).

All shop facts come from mcp_server/server.py over MCP. This module never touches the
database; it only:
  * launches the MCP server (without the approval secret, so human-only tools always refuse),
  * gives each agent a filtered view of the tools its role allows,
  * fills identity fields (requested_by, author, ...) with the calling agent's name so an
    agent can't act as someone else, and defaults ticket_id to the ticket being worked,
  * logs every MCP call and result to the audit trail.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext, ToolDefinition
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from backend import audit
from backend.models import AgentRole, TeamDeps
from core.config import ROOT

SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"
HUMAN_ONLY = frozenset({"approve_and_pay", "reject_request", "reset_database", "record_sale",
                        "receive_purchase_order"})

# Tool -> parameter that records who acted. Filled by the backend, hidden from the model.
IDENTITY_PARAM = {
    "update_ticket": "author",
    "draft_customer_message": "author",
    "reserve_stock": "reserved_by",
    "record_price_decision": "decided_by",
    "request_invoice_payment": "requested_by",
    "request_purchase_order": "requested_by",
    "request_rent_payment": "requested_by",
}
TICKET_DEFAULT_TOOLS = {"request_invoice_payment", "request_purchase_order", "request_rent_payment"}


def _server_env(approval_secret: str | None) -> dict[str, str]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    env.pop("PORTKEY_API_KEY", None)          # the MCP server never needs the LLM key
    env.pop("CC_APPROVAL_SECRET", None)
    if approval_secret:
        env["CC_APPROVAL_SECRET"] = approval_secret
    return env


def mcp_client(approval_secret: str | None = None) -> Client:
    """A FastMCP client that launches mcp_server/server.py over stdio."""
    transport = StdioTransport(command=sys.executable, args=[str(SERVER_SCRIPT)],
                               env=_server_env(approval_secret), cwd=str(ROOT))
    return Client(transport)


async def _process_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    deps = ctx.deps
    if name in HUMAN_ONLY:  # belt and braces: these are filtered out anyway
        result = {"ok": False, "error": f"{name} is human-only. Agents cannot approve, pay or reset."}
        audit.log(deps, "tool_result", {"tool": name, "refused": True, "result": result})
        return result
    args = dict(args)
    if name in IDENTITY_PARAM:
        args[IDENTITY_PARAM[name]] = deps.agent
    if name in TICKET_DEFAULT_TOOLS and not args.get("ticket_id") and deps.work.ticket_id:
        args["ticket_id"] = deps.work.ticket_id
    audit.log(deps, "tool_call", {"tool": name, "args": args})
    try:
        result = await call_tool(name, args)
    except Exception as e:  # noqa: BLE001 - give the model the error instead of crashing the run
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    audit.log(deps, "tool_result", {"tool": name, "result": result})
    return result


def shop_toolset() -> MCPToolset:
    """One shared MCP connection for the whole team (no approval secret)."""
    return MCPToolset(mcp_client(), process_tool_call=_process_tool_call, max_retries=1)


def _strip_identity(ctx: RunContext[TeamDeps], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    out = []
    for td in tool_defs:
        param = IDENTITY_PARAM.get(td.name)
        if param:
            schema = json.loads(json.dumps(td.parameters_json_schema))
            schema.get("properties", {}).pop(param, None)
            if param in schema.get("required", []):
                schema["required"].remove(param)
            td = dataclasses.replace(td, parameters_json_schema=schema)
        out.append(td)
    return out


def toolset_for(role: AgentRole, shared: MCPToolset) -> AbstractToolset[TeamDeps]:
    """The slice of the MCP server one role may use."""
    allowed = role.mcp_tools - HUMAN_ONLY
    return shared.filtered(lambda ctx, td: td.name in allowed).prepared(_strip_identity)
