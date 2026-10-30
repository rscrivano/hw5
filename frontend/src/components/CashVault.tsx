import { useEffect, useRef, useState } from "react";
import { money } from "../agents";
import type { Cash } from "../types";

/** Counts the number from its old value to the new one so a payment visibly drains the account. */
function useTween(target: number | null, ms = 1200) {
  const [shown, setShown] = useState(target ?? 0);
  const from = useRef<number | null>(target);
  useEffect(() => {
    if (target == null) return;
    if (from.current == null) { // first real value: show it as-is, no count-up from $0
      from.current = target;
      setShown(target);
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const v = a + (target - a) * (1 - Math.pow(1 - t, 3));
      setShown(v);
      if (t < 1) raf = requestAnimationFrame(step);
      else from.current = target as number;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return shown;
}

export function CashVault({ cash, opening }: { cash: Cash | null; opening: number | null }) {
  const balance = useTween(cash?.balance ?? null);
  const [drop, setDrop] = useState<number | null>(null);  // + for sales, - for payments
  const prev = useRef<number | null>(null);
  useEffect(() => {
    if (cash == null) return;
    if (prev.current != null && Math.abs(cash.balance - prev.current) > 0.004) {
      setDrop(cash.balance - prev.current);
      const t = setTimeout(() => setDrop(null), 3500);
      prev.current = cash.balance;
      return () => clearTimeout(t);
    }
    prev.current = cash.balance;
  }, [cash?.balance]);

  const base = opening ?? cash?.balance ?? 1;
  const pct = cash ? Math.max(0, Math.min(100, (cash.balance / base) * 100)) : 0;
  const afterPct = cash ? Math.max(0, Math.min(100, (cash.balance_after_pending / base) * 100)) : 0;
  const tight = cash ? cash.balance_after_pending < 0 : false;

  return (
    <section className="panel vault" aria-labelledby="vault-title">
      <div className="panel-head">
        <h2 id="vault-title">Cash · checking</h2>
        <span className="muted small">as of {cash?.date ?? "…"}</span>
      </div>
      <div className="balance" aria-live="polite">
        {cash ? money(balance) : "—"}
        {drop != null && <span className={`drop ${drop > 0 ? "rise" : ""}`}>{drop > 0 ? "+" : "−"}{money(Math.abs(drop))}</span>}
      </div>
      <div className="gauge" role="img"
        aria-label={`Balance ${pct.toFixed(0)}% of opening; ${afterPct.toFixed(0)}% if all pending approvals are paid`}>
        <div className="gauge-now" style={{ width: `${pct}%` }} />
        <div className="gauge-after" style={{ width: `${afterPct}%` }} />
      </div>
      {cash && (
        <dl className="vault-stats">
          <div className="in"><dt>Sales in</dt><dd>+{money(cash.total_sales ?? 0)}</dd></div>
          <div><dt>Paid out</dt><dd>−{money(cash.total_payments ?? 0)}</dd></div>
          <div><dt>Waiting for approval</dt><dd>{money(cash.pending_approvals_total)}</dd></div>
          <div className={tight ? "bad" : ""}><dt>If all approved</dt><dd>{money(cash.balance_after_pending)}</dd></div>
        </dl>
      )}
      {tight && <p className="warn small">Not enough cash for every pending request. The pay step will refuse whichever would go negative.</p>}
      <p className="small muted">Cash goes out only when a human approves a payment, and comes in only when a human records a sale.
        {cash && <> Books {cash.ties_out ? "tie out ✓" : "do NOT tie out ⚠"}.</>}</p>
    </section>
  );
}
