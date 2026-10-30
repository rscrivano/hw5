import { useRef, useState, type CSSProperties } from "react";
import { AGENT, money } from "../agents";
import type { Approval } from "../types";

const KIND: Record<Approval["kind"], { label: string; icon: string }> = {
  invoice: { label: "Vendor invoice", icon: "🧾" },
  rent: { label: "Rent", icon: "🏠" },
  purchase_order: { label: "Purchase order", icon: "📦" },
};

interface Props {
  approvals: Approval[];
  approver: string;
  setApprover: (name: string) => void;
  onApprove: (a: Approval) => Promise<void>;
  onReject: (a: Approval) => Promise<void>;
}

export function Approvals({ approvals, approver, setApprover, onApprove, onReject }: Props) {
  const [working, setWorking] = useState<number | null>(null);
  const [needName, setNeedName] = useState(false);
  const nameBox = useRef<HTMLInputElement>(null);
  const pending = approvals.filter((a) => a.status === "pending");
  const decided = approvals.filter((a) => a.status !== "pending").slice(-4).reverse();
  const act = async (a: Approval, fn: (a: Approval) => Promise<void>) => {
    if (!approver.trim()) { // no silent dead button: point at the missing name instead
      setNeedName(true);
      nameBox.current?.scrollIntoView({ block: "center", behavior: "smooth" });
      nameBox.current?.focus();
      return;
    }
    setWorking(a.id);
    try { await fn(a); } finally { setWorking(null); }
  };
  return (
    <section className="panel approvals" aria-labelledby="appr-title">
      <div className="panel-head">
        <h2 id="appr-title">Needs your OK</h2>
        {pending.length > 0 && <span className="count-chip hot">{pending.length}</span>}
      </div>
      <label className={`approver ${needName && !approver.trim() ? "approver-missing" : ""}`}>
        <span>Approving as</span>
        <input ref={nameBox} value={approver} onChange={(e) => { setApprover(e.target.value); setNeedName(false); }}
          placeholder="Type your name to approve" />
        {needName && !approver.trim() && <span className="approver-hint" role="alert">Type your name first, then click Approve again.</span>}
      </label>
      {pending.length === 0 && <p className="empty small">Nothing to approve. When an agent prepares a payment it lands here.</p>}
      <ul className="receipts">
        {pending.map((a) => {
          const who = AGENT[a.requested_by];
          return (
            <li key={a.id} className="receipt" style={{ "--agent": who?.color, "--agent-soft": who?.soft } as CSSProperties}>
              <div className="receipt-top">
                <span className="receipt-kind">{KIND[a.kind].icon} {KIND[a.kind].label} · #{a.id}</span>
                {a.ticket_id && <span className="muted small">ticket #{a.ticket_id}</span>}
              </div>
              <div className="receipt-amount">{money(a.amount)}</div>
              <div className="receipt-payee">to <b>{a.payee}</b></div>
              <p className="receipt-reason">{a.reason}</p>
              <div className="receipt-by small">Prepared by {who?.emoji} {a.requested_by}</div>
              <div className="receipt-actions">
                <button className="btn" disabled={working != null}
                  onClick={() => act(a, onApprove)}>
                  {working === a.id ? "Paying…" : `Approve & pay`}
                </button>
                <button className="btn btn-ghost" disabled={working != null}
                  onClick={() => act(a, onReject)}>Reject</button>
              </div>
            </li>
          );
        })}
      </ul>
      {decided.length > 0 && (
        <ul className="decided">
          {decided.map((a) => (
            <li key={a.id} className={`decided-${a.status}`}>
              <span className="decided-stamp">{a.status}</span> #{a.id} {money(a.amount)} to {a.payee}
              {a.decided_by && <span className="muted"> · {a.decided_by}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
