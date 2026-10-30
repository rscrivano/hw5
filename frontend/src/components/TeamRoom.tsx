import type { CSSProperties } from "react";
import { AGENTS, prettyTool } from "../agents";
import type { AgentEvent, AgentName } from "../types";

export interface AgentLive {
  state: "idle" | "working" | "done" | "error";
  line: string;
  tool: string | null;
}

/** Each agent's latest status, replayed from the run's events. */
export function liveStatus(events: AgentEvent[]): Record<AgentName, AgentLive> {
  const out = Object.fromEntries(
    AGENTS.map((a) => [a.name, { state: "idle", line: "Standing by", tool: null } as AgentLive]),
  ) as Record<AgentName, AgentLive>;
  for (const e of events) {
    const s = out[e.agent];
    if (!s) continue;
    if (e.kind === "run_start") {
      Object.assign(s, { state: "working", line: e.agent === "Boss" ? "Reading the ticket" : "Got a task", tool: null });
    } else if (e.kind === "tool_call") {
      Object.assign(s, { state: "working", line: `Using ${prettyTool(e.tool ?? "")}`, tool: e.tool });
    } else if (e.kind === "delegate") {
      Object.assign(s, { state: "working", line: `Handed off to ${String(e.detail)}`, tool: null });
    } else if (e.kind === "model_response") {
      Object.assign(s, { line: e.text });
    } else if (e.kind === "final_output") {
      Object.assign(s, { state: "done", line: e.text, tool: null });
    } else if (e.kind === "error") {
      Object.assign(s, { state: "error", line: e.text, tool: null });
    }
  }
  return out;
}

interface Props {
  live: Record<AgentName, AgentLive>;
  handoff: { from: AgentName; to: AgentName } | null;
  ticketId: number | null;
  running: boolean;
}

export function TeamRoom({ live, handoff, ticketId, running }: Props) {
  return (
    <section className="panel team" aria-labelledby="team-title">
      <div className="panel-head">
        <h2 id="team-title">Team room</h2>
        <span className="muted small">
          {ticketId ? `Ticket #${ticketId}` : "Pick a ticket"}
          {running && <span className="live-tag"> ● live</span>}
        </span>
      </div>
      <div className="agents">
        {AGENTS.map((a) => {
          const s = live[a.name];
          return (
            <article
              key={a.name}
              className={`agent-card agent-${s.state} ${a.name === "Boss" ? "agent-boss" : ""} ${
                handoff?.to === a.name && running ? "agent-baton" : ""}`}
              style={{ "--agent": a.color, "--agent-soft": a.soft, "--agent-ink": a.ink } as CSSProperties}
            >
              <div className="avatar" aria-hidden>{a.emoji}</div>
              <div className="agent-body">
                <div className="agent-name">
                  {a.name}
                  <span className={`agent-state state-${s.state}`}>
                    {s.state === "idle" ? "idle" : s.state === "working" ? "working" : s.state === "done" ? "done" : "error"}
                  </span>
                </div>
                <div className="agent-role">{a.role}</div>
                <div className="agent-line" title={s.line}>
                  {s.state === "working" && <span className="typing" aria-hidden><i /><i /><i /></span>}
                  {s.line}
                </div>
                {s.tool && <span className="tool-chip">🔧 {prettyTool(s.tool)}</span>}
              </div>
            </article>
          );
        })}
      </div>
      {handoff && (
        <p className="baton" aria-live="polite">
          Last hand-off: <b>{handoff.from}</b> <span className="baton-arrow">➜</span> <b>{handoff.to}</b>
        </p>
      )}
    </section>
  );
}
