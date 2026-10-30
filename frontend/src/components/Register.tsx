import { useEffect, useState } from "react";
import { api } from "../api";
import { money } from "../agents";
import type { PurchaseOrder, Sale, TicketPrice } from "../types";

interface Props {
  ticketId: number | null;
  person: string;               // the same human name used for approvals
  sales: Sale[];
  orders: PurchaseOrder[];
  onSale: (text: string, ok: boolean) => Promise<void>;
}

/** The human register: ring up a sale (cash in, stock out) and receive deliveries (stock in). */
export function Register({ ticketId, person, sales, orders, onSale }: Props) {
  const [price, setPrice] = useState<TicketPrice | null>(null);
  const [form, setForm] = useState({ customer: "", qty: 1, unit_price: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const soldForTicket = sales.filter((s) => s.ticket_id === ticketId).reduce((n, s) => n + s.qty, 0);
  const received = orders.filter((o) => o.status === "received").length;  // a delivery changes what's on the shelf

  useEffect(() => {
    setError("");
    if (ticketId == null) { setPrice(null); return; }
    api.ticketPrice(ticketId).then((p) => {
      setPrice(p);
      if (p.sku) {
        const left = Math.max(0, (p.qty ?? 1) - (p.already_sold ?? 0));
        setForm({ customer: p.customer ?? "", qty: Math.max(1, Math.min(left || 1, p.on_shelf ?? 1)),
                  unit_price: p.agreed_price ?? p.list_price ?? 0 });
      }
    }).catch(() => setPrice(null));
  }, [ticketId, soldForTicket, received]);

  const ring = async () => {
    if (!price?.sku) return;
    if (!person.trim()) { setError("Type your name under \"Approving as\" first; it's recorded as the cashier."); return; }
    setBusy(true);
    setError("");
    try {
      const r = await api.recordSale({ cashier: person.trim(), customer: form.customer, sku: price.sku,
        size: price.size ?? "", qty: form.qty, unit_price: form.unit_price, ticket_id: ticketId });
      await onSale(`Sale recorded: ${form.qty} × ${price.sku} ${price.size} = ${money(Number(r.revenue))}. `
        + `Checking is now ${money(Number(r.cash_balance_after))}.`, true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const receive = async (po: PurchaseOrder) => {
    if (!person.trim()) { setError("Type your name under \"Approving as\" first."); return; }
    try {
      const r = await api.receive(po.id, person.trim());
      await onSale(`Received PO #${po.id}: ${po.qty} × ${po.sku} ${po.size} added to stock (${String(r.on_hand_after)} on hand).`, true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const open = orders.filter((o) => o.status === "ordered");
  const revenue = sales.reduce((n, s) => n + s.revenue, 0);
  const gross = sales.reduce((n, s) => n + s.revenue - s.cogs, 0);

  return (
    <section className="panel register" aria-labelledby="reg-title">
      <div className="panel-head">
        <h2 id="reg-title">Register</h2>
        <span className="muted small">cash in · stock out</span>
      </div>

      {price?.sku ? (
        <div className="sale-form">
          <p className="small muted">
            Ticket #{price.ticket_id}: <code>{price.sku}</code> size <b>{price.size}</b> · {price.on_shelf} on the shelf
            {price.already_sold ? ` · ${price.already_sold} already sold` : ""}
            {price.agreed_price != null && <> · agreed price <b>{money(price.agreed_price)}</b></>}
          </p>
          <label>Customer<input value={form.customer} onChange={(e) => setForm({ ...form, customer: e.target.value })} /></label>
          <div className="sale-row">
            <label>Qty<input type="number" min={1} value={form.qty}
              onChange={(e) => setForm({ ...form, qty: Math.max(1, Number(e.target.value)) })} /></label>
            <label>Unit price<input type="number" min={0} step="0.01" value={form.unit_price}
              onChange={(e) => setForm({ ...form, unit_price: Number(e.target.value) })} /></label>
          </div>
          <div className="sale-total">
            Total <b>{money(form.qty * form.unit_price)}</b>
            {price.unit_cost != null && form.unit_price < price.unit_cost &&
              <span className="warn-text"> · below cost ({money(price.unit_cost)})</span>}
          </div>
          <button className="btn btn-sun" onClick={ring} disabled={busy || !form.customer.trim()}>
            {busy ? "Recording…" : "💵 Record sale"}
          </button>
        </div>
      ) : (
        <p className="empty small">Pick a ticket with a product (101 or 103) to ring up its sale.</p>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}

      {open.length > 0 && (
        <>
          <h3 className="mini-head">Deliveries on the way</h3>
          <ul className="deliveries">
            {open.map((o) => (
              <li key={o.id}>
                <span>📦 PO #{o.id}: {o.qty} × {o.sku} {o.size} from {o.vendor_name} · ETA {o.eta}</span>
                <button className="btn btn-ghost btn-small" onClick={() => receive(o)}>Mark received</button>
              </li>
            ))}
          </ul>
        </>
      )}

      {sales.length > 0 && (
        <>
          <h3 className="mini-head">Sales · {money(revenue)} in · {money(gross)} gross profit</h3>
          <ul className="sales-list">
            {sales.slice(-5).reverse().map((s) => (
              <li key={s.id}>
                <span>#{s.id} {s.customer}: {s.qty} × {s.sku} {s.size} @ {money(s.unit_price)}</span>
                <b>+{money(s.revenue)}</b>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
