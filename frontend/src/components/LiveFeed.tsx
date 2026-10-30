import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { AGENT, prettyTool } from "../agents";
import type { AgentEvent, AgentName } from "../types";

function Line({ e }: { e: AgentEvent }) {
  const [open, setOpen] = useState(false);
  const a = AGENT[e.agent];
  const time = new Date(e.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const style = { "--agent": a?.color, "--agent-soft": a?.soft, "--agent-ink": a?.ink } as CSSProperties;
  let body: ReactNode;
  switch (e.kind) {
    case "run_start":
      body = (
        <>
          <span className="feed-verb">{e.chain.length === 1 ? "picked up the ticket" : "got a task"}</span>
          {e.chain.length > 1 && <q>{e.text}</q>}
        </>
      );
      break;
    case "delegate": {
      const to = String(e.detail) as AgentName;
      body = (
        <>
          <span className="feed-verb">handed off to</span>{" "}
          <b className="to-agent" style={{ color: AGENT[to]?.ink }}>{AGENT[to]?.emoji} {to}</b>
          <q>{e.text}</q>
        </>
      );
      break;
    }
    case "delegate_refused":
      body = <span className="feed-verb">hand-off refused: {String(e.detail)}</span>;
      break;
    case "tool_call":
      body = (
        <>
          <span className="tool-chip">🔧 {prettyTool(e.tool ?? "")}</span> <code className="args">{String(e.detail)}</code>
        </>
      );
      break;
    case "tool_result":
      body = (
        <button className="result-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
          ↳ {prettyTool(e.tool ?? "")} result {open ? "▾" : "▸"}
          {open && <code className="result">{String(e.detail)}</code>}
        </button>
      );
      break;
    case "final_output":
      body = (
        <div className="report">
          <span className="feed-verb">reported back</span>
          <p>{e.text}</p>
        </div>
      );
      break;
    case "run_end":
      body = (
        <div className="report report-end">
          <b>🏁 Run finished.</b>
          <p>{e.text}</p>
        </div>
      );
      break;
    case "error":
      body = <span className="feed-error">⚠ {e.text}</span>;
      break;
    default:
      body = <span className="said">“{e.text}”</span>;
  }
  return (
    <li className={`feed-line feed-${e.kind}`} style={style}>
      <span className="feed-avatar" aria-hidden>{a?.emoji}</span>
      <div className="feed-main">
        <div className="feed-who"><b>{e.agent}</b> <time>{time}</time></div>
        <div className="feed-body">{body}</div>
      </div>
    </li>
  );
}

export function LiveFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const box = useRef<HTMLOListElement>(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [events.length, follow, running]);
  return (
    <section className="panel feed" aria-labelledby="feed-title">
      <div className="panel-head">
        <h2 id="feed-title">Live feed</h2>
        <label className="small muted follow">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Auto-scroll
        </label>
      </div>
      {events.length === 0 && !running ? (
        <p className="empty">No activity yet. Pick a ticket and press <b>Start team</b> to watch the agents work.</p>
      ) : (
        <ol className="feed-list" ref={box} aria-live="polite">
          {events.map((e) => <Line key={e.id} e={e} />)}
          {running && (
            <li className="feed-line feed-waiting">
              <span className="typing" aria-hidden><i /><i /><i /></span> the team is thinking…
            </li>
          )}
        </ol>
      )}
    </section>
  );
}
