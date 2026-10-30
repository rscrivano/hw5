import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, API_URL } from "./api";
import { money } from "./agents";
import { Approvals } from "./components/Approvals";
import { CashVault } from "./components/CashVault";
import { Drafts } from "./components/Drafts";
import { LiveFeed } from "./components/LiveFeed";
import { Register } from "./components/Register";
import { RunRecap } from "./components/RunRecap";
import { liveStatus, TeamRoom } from "./components/TeamRoom";
import { TicketBoard } from "./components/TicketBoard";
import type {
  AgentEvent, AgentName, Approval, Cash, Draft, PurchaseOrder, Sale, Ticket, TicketSummary,
} from "./types";

interface Toast { id: number; tone: "ok" | "bad" | "info"; text: string }

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmReset, setConfirmReset] = useState(false);
  const [approver, setApproverState] = useState(() => {
    try { return localStorage.getItem("cc-approver") ?? ""; } catch { return ""; }
  });
  const lastId = useRef(-1);
  const prevStates = useRef<Record<number, Ticket["state"]>>({});

  const setApprover = (name: string) => {
    setApproverState(name);
    try { localStorage.setItem("cc-approver", name); } catch { /* storage blocked: keep in memory */ }
  };
  const toast = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const running = tickets.some((t) => t.running);

  const refresh = useCallback(async () => {
    try {
      const [t, c, a, d, ev, s, po] = await Promise.all([
        api.tickets(), api.cash(), api.approvals(), api.drafts(), api.events(lastId.current),
        api.sales(), api.purchaseOrders(),
      ]);
      setOnline(true);
      for (const tk of t) {
        const before = prevStates.current[tk.id];
        if (before === "running" && tk.state === "resolved") toast("ok", `Ticket #${tk.id} resolved: ${tk.status.replace(/_/g, " ")}.`);
        if (before === "running" && tk.last_run?.status === "error") toast("bad", `Ticket #${tk.id} run failed: ${tk.last_run.error}`);
        prevStates.current[tk.id] = tk.state;
      }
      setTickets(t);
      setCash(c);
      setApprovals(a);
      setDrafts(d);
      setSales(s);
      setOrders(po);
      if (ev.last_id < lastId.current) { // audit trail was replaced: start over
        lastId.current = -1;
        setEvents([]);
      } else if (ev.events.length) {
        setEvents((old) => { // overlapping polls can return the same events: keep one per id
          const seen = new Set(old.map((e) => e.id));
          return [...old, ...ev.events.filter((e) => !seen.has(e.id))].slice(-4000);
        });
      }
      lastId.current = Math.max(lastId.current, ev.last_id);
      setSelected((s) => s ?? t[0]?.id ?? null);
    } catch {
      setOnline(false);
    }
  }, [toast]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, running ? 1200 : 4000);
    return () => clearInterval(iv);
  }, [refresh, running]);

  // Events of the selected ticket's latest run drive the team room and feed.
  const runEvents = useMemo(() => {
    const mine = events.filter((e) => e.ticket_id === selected);
    const runId = mine.at(-1)?.run_id;
    return runId ? mine.filter((e) => e.run_id === runId) : [];
  }, [events, selected]);
  const selTicket = tickets.find((t) => t.id === selected) ?? null;
  const selRunning = !!selTicket?.running;
  const live = useMemo(() => liveStatus(runEvents), [runEvents]);
  const handoff = useMemo(() => {
    const d = [...runEvents].reverse().find((e) => e.kind === "delegate");
    return d ? { from: d.agent, to: String(d.detail) as AgentName } : null;
  }, [runEvents]);

  useEffect(() => {
    if (selected == null) return;
    api.summary(selected).then(setSummary).catch(() => setSummary(null));
  }, [selected, runEvents.length]);

  const startRun = async (id: number) => {
    try {
      await api.run(id);
      toast("info", `The team is on ticket #${id}. Boss is reading it now.`);
      await refresh();
    } catch (e) {
      toast("bad", (e as Error).message);
    }
  };
  const approve = async (a: Approval) => {
    try {
      const r = await api.approve(a.id, approver.trim());
      if (r.refused) toast("bad", `Refused: ${String(r.reason)}`);
      else toast("ok", `Paid ${money(a.amount)} to ${a.payee}. Checking is now ${money(Number(r.cash_balance_after))}.`);
    } catch (e) { toast("bad", (e as Error).message); }
    await refresh();
  };
  const reject = async (a: Approval) => {
    try {
      await api.reject(a.id, approver.trim(), "Rejected on the desk");
      toast("info", `Rejected #${a.id}. No money moved.`);
    } catch (e) { toast("bad", (e as Error).message); }
    await refresh();
  };
  const reset = async () => {
    setConfirmReset(false);
    try {
      await api.reset();
      toast("ok", "Working database reset to the original. Fresh start!");
    } catch (e) { toast("bad", (e as Error).message); }
    await refresh();
  };

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden>🐶</span>
            <span>Campus Customs<small>Ops Desk · agent team</small></span>
          </div>
          <div className="topbar-chips">
            <span className="chip">📅 Shop day {cash?.date ?? "…"}</span>
            <span className="chip">🤖 gpt-6-luna</span>
            <span className={`chip conn ${online ? "on" : online === false ? "off" : ""}`}>
              {online ? "● Backend connected" : online === false ? `● Can't reach ${API_URL}` : "● Connecting…"}
            </span>
          </div>
          <button className="btn btn-ghost btn-small" onClick={() => setConfirmReset(true)} disabled={running}>
            ↺ Reset DB
          </button>
        </div>
      </header>

      {online === false && (
        <div className="banner">
          The desk can't reach the backend at <code>{API_URL}</code>. Start it from <code>backend/</code> with
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="layout">
        <TicketBoard tickets={tickets} selected={selected} busy={running} onSelect={setSelected} onRun={startRun} />
        <div className="center">
          <TeamRoom live={live} handoff={handoff} ticketId={selected} running={selRunning} />
          <RunRecap summary={summary} />
          <LiveFeed events={runEvents} running={selRunning} />
        </div>
        <aside className="side">
          <CashVault cash={cash} opening={cash?.opening_balance ?? null} />
          <Approvals approvals={approvals} approver={approver} setApprover={setApprover} onApprove={approve} onReject={reject} />
          <Register ticketId={selected} person={approver} sales={sales} orders={orders}
            onSale={async (text, ok) => { toast(ok ? "ok" : "bad", text); await refresh(); }} />
          <Drafts drafts={drafts} ticketId={selected} />
        </aside>
      </main>

      {confirmReset && (
        <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="reset-title">
          <div className="modal">
            <h2 id="reset-title">Reset to the original data?</h2>
            <p>This copies <code>campus_customs.db</code> over the working copy. Payments, sales, approvals, drafts and ticket
              updates are cleared and cash goes back to the start. The audit trail is kept.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setConfirmReset(false)}>Cancel</button>
              <button className="btn" onClick={reset}>Yes, reset</button>
            </div>
          </div>
        </div>
      )}

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>)}
      </div>
    </>
  );
}
