import { TICKET_ICON } from "../agents";
import type { Ticket } from "../types";

const STATUS_LABEL: Record<Ticket["status"], string> = {
  open: "Open",
  in_progress: "In progress",
  awaiting_approval: "waiting on your approval",
  blocked: "blocked",
  resolved: "done",
};

interface Props {
  tickets: Ticket[];
  selected: number | null;
  busy: boolean;
  onSelect: (id: number) => void;
  onRun: (id: number) => void;
}

export function TicketBoard({ tickets, selected, busy, onSelect, onRun }: Props) {
  return (
    <section className="panel board" aria-labelledby="board-title">
      <div className="panel-head">
        <h2 id="board-title">Ticket board</h2>
        <span className="count-chip">
          {tickets.filter((t) => t.state === "resolved").length}/{tickets.length} resolved
        </span>
      </div>
      <ul className="ticket-list">
        {tickets.map((t) => {
          const isSel = t.id === selected;
          return (
            <li key={t.id}>
              <article
                className={`ticket ticket-${t.state} ${isSel ? "is-selected" : ""}`}
                onClick={() => onSelect(t.id)}
                aria-current={isSel}
              >
                {t.state === "resolved" && <span className="stamp" aria-hidden>Resolved</span>}
                <div className="ticket-top">
                  <span className="ticket-icon" aria-hidden>{TICKET_ICON[t.type] ?? "🎫"}</span>
                  <div>
                    <div className="ticket-id">#{t.id} · {t.type.replace(/_/g, " ")}</div>
                    <h3>{t.subject}</h3>
                  </div>
                </div>
                <p className="ticket-from">From <strong>{t.requester}</strong></p>
                {t.notes && <p className="ticket-notes">“{t.notes}”</p>}
                {t.sku && (
                  <p className="ticket-meta">
                    <code>{t.sku}</code> {t.size && <>size <b>{t.size}</b></>} {t.qty != null && <>× <b>{t.qty}</b></>}
                  </p>
                )}
                <div className="ticket-foot">
                  <span className={`pill pill-${t.state}`}>
                    {t.state === "running" ? (
                      <><span className="dot-pulse" aria-hidden /> Team working…</>
                    ) : t.state === "resolved" ? (
                      `Resolved · ${STATUS_LABEL[t.status]}`
                    ) : (
                      STATUS_LABEL[t.status]
                    )}
                  </span>
                  <button
                    className="btn btn-small"
                    disabled={busy}
                    onClick={(e) => { e.stopPropagation(); onSelect(t.id); onRun(t.id); }}
                    aria-label={`Start the agent team on ticket ${t.id}`}
                  >
                    {t.state === "resolved" ? "Run again" : "Start team"} ▸
                  </button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
