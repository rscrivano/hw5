import type { CSSProperties } from "react";
import { AGENT, AGENTS, prettyTool } from "../agents";
import type { TicketSummary } from "../types";

export function RunRecap({ summary }: { summary: TicketSummary | null }) {
  if (!summary?.run_id) return null;
  const byAgent = Object.fromEntries(summary.agents.map((a) => [a.agent, a]));
  const used = AGENTS.filter((a) => byAgent[a.name]);
  const benched = AGENTS.filter((a) => !byAgent[a.name]);
  return (
    <section className="panel recap" aria-labelledby="recap-title">
      <div className="panel-head">
        <h2 id="recap-title">Run recap · ticket #{summary.ticket_id}</h2>
        <span className="muted small">
          {summary.finished ? "finished" : "in progress"}
          {summary.usage && <> · {summary.usage.total_tokens.toLocaleString()} tokens · {summary.usage.requests} model calls</>}
        </span>
      </div>
      {summary.delegations.length > 0 && (
        <div className="path" aria-label="Delegation path">
          {summary.delegations.map((d, i) => (
            <span key={i} className="path-step">
              <span style={{ color: AGENT[d.from]?.ink }}>{AGENT[d.from]?.emoji} {d.from}</span>
              <span className="baton-arrow">➜</span>
              <span style={{ color: AGENT[d.to]?.ink }}>{AGENT[d.to]?.emoji} {d.to}</span>
            </span>
          ))}
        </div>
      )}
      <div className="recap-grid">
        {used.map((a) => {
          const s = byAgent[a.name];
          return (
            <article key={a.name} className="recap-card"
              style={{ "--agent": a.color, "--agent-soft": a.soft, "--agent-ink": a.ink } as CSSProperties}>
              <header><span aria-hidden>{a.emoji}</span> {a.name}</header>
              <p>{s.summary || <span className="muted">No report yet.</span>}</p>
              {Object.keys(s.tools).length > 0 && (
                <div className="chips">
                  {Object.entries(s.tools).map(([t, n]) => (
                    <span key={t} className="tool-chip">{prettyTool(t)}{n > 1 ? ` ×${n}` : ""}</span>
                  ))}
                </div>
              )}
              {s.approvals.length > 0 && <p className="small">Asked a human to approve #{s.approvals.join(", #")}</p>}
            </article>
          );
        })}
      </div>
      {summary.finished && benched.length > 0 && (
        <p className="small muted bench">
          Not needed this time: {benched.map((a) => `${a.emoji} ${a.name}`).join(" · ")}
        </p>
      )}
    </section>
  );
}
