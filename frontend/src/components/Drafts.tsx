import { useState } from "react";
import type { Draft } from "../types";

export function Drafts({ drafts, ticketId }: { drafts: Draft[]; ticketId: number | null }) {
  const [open, setOpen] = useState<number | null>(null);
  const shown = ticketId ? drafts.filter((d) => d.ticket_id === ticketId) : drafts;
  return (
    <section className="panel drafts" aria-labelledby="drafts-title">
      <div className="panel-head">
        <h2 id="drafts-title">Message drafts</h2>
        <span className="muted small">never sent</span>
      </div>
      {shown.length === 0 ? (
        <p className="empty small">Customer Service drafts show up here.</p>
      ) : (
        <ul className="envelopes">
          {shown.map((d) => (
            <li key={d.id} className="envelope">
              <button onClick={() => setOpen(open === d.id ? null : d.id)} aria-expanded={open === d.id}>
                <span aria-hidden>✉️</span>
                <span><b>{d.subject}</b><br /><span className="small muted">to {d.recipient} · ticket #{d.ticket_id}</span></span>
              </button>
              {open === d.id && <p className="letter">{d.body}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
