"""The Campus Customs agent team (PydanticAI).

Five agents - Boss, Inventory, Accounting, Facilities, Customer Service - all on gpt-6-luna
through Portkey. The team is fully connected: every agent has a `delegate` tool that can hand
a task to ANY other agent. Each agent sees only its role's slice of the MCP server.

Agent loop: every run goes through `Agent.iter`, and each step (prompt, model request, model
response, tool call/result, delegation, final output) is appended to output/audit_trail.json.

Guard rails (core/config.py):
  * no self-delegation, and no delegating to an agent already in the current chain (no loops)
  * delegation depth <= MAX_DELEGATION_DEPTH
  * each agent takes at most MAX_TASKS_PER_AGENT_PER_TICKET tasks per ticket (no overloading)
  * one usage budget per ticket shared by every agent: request and total-token limits
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from pydantic_ai import Agent, NativeOutput, RunContext, Tool, UsageLimitExceeded, UsageLimits
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.usage import RunUsage

from backend import audit
from backend.agents import ROLES
from backend.llm import build_model
from backend.mcp_tools import shop_toolset, toolset_for
from backend.models import AGENT_NAMES, AgentName, AgentReport, TeamDeps, TicketWork
from core.config import (MAX_DELEGATION_DEPTH, MAX_REQUESTS_PER_TICKET, MAX_TASKS_PER_AGENT_PER_TICKET,
                         MAX_TOKENS_PER_TICKET)

PROMPTS = Path(__file__).resolve().parent / "prompts"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _usage_dict(usage) -> dict[str, int]:
    return {"requests": usage.requests, "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens, "total_tokens": usage.total_tokens}


class Team:
    def __init__(self) -> None:
        self.model = build_model()
        self.mcp: MCPToolset = shop_toolset()
        self.limits = UsageLimits(request_limit=MAX_REQUESTS_PER_TICKET, total_tokens_limit=MAX_TOKENS_PER_TICKET)
        rules = (PROMPTS / "store_rules.md").read_text(encoding="utf-8")
        self.agents: dict[str, Agent[TeamDeps, AgentReport]] = {}
        for name in AGENT_NAMES:
            role = ROLES[name]
            roster = "\n".join(f"- {r.name}: {r.description}" for r in ROLES.values() if r.name != name)
            instructions = (f"{(PROMPTS / role.prompt_file).read_text(encoding='utf-8')}\n\n"
                            f"Your teammates (use `delegate` to hand them work):\n{roster}\n\n{rules}")
            self.agents[name] = Agent(
                self.model,
                name=name,
                deps_type=TeamDeps,
                output_type=NativeOutput(AgentReport),  # final answer must match the schema (no free-text runaway)
                instructions=instructions,
                toolsets=[toolset_for(role, self.mcp)],
                tools=[Tool(self._delegate, name="delegate",
                            description="Hand a task to a teammate and wait for their report. "
                                        "Teammates: " + "; ".join(f"{r.name} ({r.description})"
                                                                   for r in ROLES.values() if r.name != name))],
                retries=1,
            )

    # ------------------------------------------------------------------ delegation
    async def _delegate(self, ctx: RunContext[TeamDeps], teammate: AgentName, task: str) -> str:
        """Ask a teammate to do a task and return their report.

        Args:
            teammate: Who should do it: Boss, Inventory, Accounting, Facilities or Customer Service.
            task: The outcome you need, with the ids (ticket, sku, size, qty, invoice, lease) they need.
        """
        deps, work = ctx.deps, ctx.deps.work
        refusal = None
        if teammate == deps.agent:
            refusal = "You can't delegate to yourself - do it with your own tools."
        elif teammate in deps.chain:
            refusal = (f"{teammate} is already working on this request ({' -> '.join(deps.chain)}). "
                       "Answer with what you have instead.")
        elif deps.depth >= MAX_DELEGATION_DEPTH:
            refusal = "Delegation depth limit reached - finish with your own tools and report."
        elif work.tasks_per_agent.get(teammate, 0) >= MAX_TASKS_PER_AGENT_PER_TICKET:
            refusal = (f"{teammate} already has {MAX_TASKS_PER_AGENT_PER_TICKET} tasks on this ticket - "
                       "use the reports you have.")
        if refusal:
            audit.log(deps, "delegate_refused", {"to": teammate, "task": task, "reason": refusal})
            return json.dumps({"ok": False, "error": refusal})
        work.tasks_per_agent[teammate] = work.tasks_per_agent.get(teammate, 0) + 1
        audit.log(deps, "delegate", {"to": teammate, "task": task})
        child = TeamDeps(agent=teammate, work=work, chain=(*deps.chain, teammate))
        report = await self.run_agent(child, f"{task}\n\n{work.brief}", usage=ctx.usage)
        return report.model_dump_json()

    # ------------------------------------------------------------------ agent loop
    async def run_agent(self, deps: TeamDeps, task: str, usage: RunUsage | None = None) -> AgentReport:
        agent = self.agents[deps.agent]
        audit.log(deps, "run_start", {"task": task})
        try:
            async with agent.iter(task, deps=deps, usage=usage, usage_limits=self.limits) as run:
                async for node in run:
                    if Agent.is_user_prompt_node(node):
                        audit.log(deps, "user_prompt", {"prompt": node.user_prompt})
                    elif Agent.is_model_request_node(node):
                        parts = [{"kind": p.part_kind, **({"tool": p.tool_name} if hasattr(p, "tool_name") else {})}
                                 for p in node.request.parts]
                        audit.log(deps, "model_request", {"parts": parts}, _usage_dict(run.usage))
                    elif Agent.is_call_tools_node(node):
                        resp = node.model_response
                        audit.log(deps, "model_response", {
                            "text": [p.content for p in resp.parts if p.part_kind == "text"],
                            "tool_calls": [{"tool": p.tool_name, "args": p.args} for p in resp.parts
                                           if p.part_kind == "tool-call"],
                            "model_name": resp.model_name,
                        }, _usage_dict(run.usage))
                    elif Agent.is_end_node(node):
                        audit.log(deps, "final_output", node.data.output.model_dump(), _usage_dict(run.usage))
            return run.result.output
        except UsageLimitExceeded as e:
            audit.log(deps, "error", {"error": f"Usage limit: {e}"})
            return AgentReport(summary=f"{deps.agent} stopped: token/request budget for this ticket is used up.",
                               blockers=[str(e)])
        except Exception as e:  # noqa: BLE001 - record and report instead of crashing the whole run
            audit.log(deps, "error", {"error": f"{type(e).__name__}: {e}"})
            return AgentReport(summary=f"{deps.agent} hit an error: {type(e).__name__}: {e}", blockers=[str(e)])

    async def run_ticket(self, ticket_id: int, run_id: str | None = None) -> AgentReport:
        """Boss works one ticket, delegating as needed. Needs the MCP connection open (see `session`)."""
        work = TicketWork(run_id=run_id or new_run_id(), ticket_id=ticket_id)
        deps = TeamDeps(agent="Boss", work=work, chain=("Boss",))
        work.brief = await self._ticket_brief(ticket_id)
        task = (f"Work ticket {ticket_id}. Get it handled by the right teammates, make the final call, "
                f"and set the ticket status with update_ticket.\n\n{work.brief}")
        usage = RunUsage()
        report = await self.run_agent(deps, task, usage=usage)
        audit.log(deps, "run_end", {"ticket_id": ticket_id, "report": report.model_dump(),
                                    "tasks_per_agent": work.tasks_per_agent}, _usage_dict(usage))
        return report

    async def _ticket_brief(self, ticket_id: int) -> str:
        """Ticket facts read once over MCP and handed to every agent, so no one re-reads the ticket."""
        t = await self.mcp.direct_call_tool("get_ticket", {"ticket_id": ticket_id})
        if not isinstance(t, dict) or t.get("ok") is False:
            return ""
        keep = {k: t.get(k) for k in ("id", "type", "requester", "subject", "sku", "size", "qty", "lease_id",
                                       "invoice_id", "status", "notes", "resolution") if t.get(k) is not None}
        keep["history"] = [f"{u['author']}: {u['note']}" for u in (t.get("updates") or [])][-6:]
        keep["approvals"] = [f"#{a['id']} {a['kind']} ${a['amount']:,.2f} to {a['payee']}: {a['status']}"
                             for a in (t.get("approvals") or [])]
        keep["drafts"] = [f"#{d['id']} to {d['recipient']}: {d['subject']}" for d in (t.get("drafts") or [])]
        return ("TICKET FACTS (already loaded from the board; don't call get_ticket again):\n"
                + json.dumps(keep, indent=1, default=str))

    def session(self):
        """`async with team.session():` keeps one MCP server process open for the whole team."""
        return self.mcp
