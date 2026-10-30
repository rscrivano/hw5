"""Data types shared by the Campus Customs agent team."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
AGENT_NAMES: tuple[AgentName, ...] = ("Boss", "Inventory", "Accounting", "Facilities", "Customer Service")

TicketStatus = Literal["open", "in_progress", "awaiting_approval", "blocked", "resolved"]


@dataclass(frozen=True)
class AgentRole:
    """Static definition of one team member: who they are and which MCP tools they may use."""
    name: AgentName
    prompt_file: str              # file in backend/prompts/
    description: str              # one line other agents see in the delegate tool
    mcp_tools: frozenset[str]     # MCP tools this agent may call (never the human-only ones)


@dataclass
class TicketWork:
    """State shared by every agent working on one ticket (one run)."""
    run_id: str
    ticket_id: int | None
    tasks_per_agent: dict[str, int] = field(default_factory=dict)   # workload guard
    step: int = 0                                                   # audit step counter
    brief: str = ""                                                 # ticket facts handed to every agent

    def next_step(self) -> int:
        self.step += 1
        return self.step


@dataclass
class TeamDeps:
    """PydanticAI deps for one agent run. `chain` is the delegation path that led here."""
    agent: AgentName
    work: TicketWork
    chain: tuple[AgentName, ...]

    @property
    def depth(self) -> int:
        return len(self.chain)


class AgentReport(BaseModel):
    """Structured answer every agent returns to whoever asked it."""
    summary: str = Field(description="2-4 sentences: what you found and did, with the key numbers from tools.")
    actions_taken: list[str] = Field(default_factory=list,
                                     description="Tool actions that changed the board, e.g. 'requested rent payment approval #2'.")
    approvals_requested: list[int] = Field(default_factory=list,
                                           description="Approval ids created for a human to approve or reject.")
    blockers: list[str] = Field(default_factory=list, description="Anything stopping the work.")
    recommended_status: TicketStatus | None = Field(
        default=None, description="Ticket status you recommend (Boss sets it).")


class AuditRecord(BaseModel):
    """One line in output/audit_trail.json - one agent-loop step."""
    ts: str
    run_id: str
    ticket_id: int | None
    step: int
    agent: str
    chain: list[str]
    depth: int
    kind: Literal["run_start", "user_prompt", "model_request", "model_response", "tool_call",
                  "tool_result", "delegate", "delegate_refused", "final_output", "error", "run_end"]
    model: str | None = None
    data: Any = None
    usage: dict[str, int] | None = None
