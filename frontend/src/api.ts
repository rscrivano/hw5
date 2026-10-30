import type {
  AgentEvent, Approval, Cash, Draft, PurchaseOrder, RunInfo, Sale, Ticket, TicketPrice, TicketSummary,
} from "./types";

// 127.0.0.1, not "localhost": browsers may resolve localhost to IPv6 (::1) first, but
// `uvicorn main:app --port 8000` listens on IPv4 only, which shows up as ERR_CONNECTION_REFUSED.
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://127.0.0.1:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  return body as T;
}

export const api = {
  tickets: () => call<Ticket[]>("/api/tickets"),
  run: (id: number) => call<RunInfo>(`/api/tickets/${id}/run`, { method: "POST" }),
  events: (after: number) => call<{ events: AgentEvent[]; last_id: number }>(`/api/events?after=${after}&limit=2000`),
  summary: (id: number) => call<TicketSummary>(`/api/tickets/${id}/summary`),
  cash: () => call<Cash>("/api/cash"),
  approvals: () => call<Approval[]>("/api/approvals"),
  approve: (id: number, approver: string) =>
    call<Record<string, unknown>>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ approver }) }),
  reject: (id: number, approver: string, reason: string) =>
    call<Record<string, unknown>>(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ approver, reason }) }),
  drafts: () => call<Draft[]>("/api/drafts"),
  sales: () => call<Sale[]>("/api/sales"),
  recordSale: (sale: { cashier: string; customer: string; sku: string; size: string; qty: number;
                       unit_price: number; ticket_id: number | null }) =>
    call<Record<string, unknown>>("/api/sales", { method: "POST", body: JSON.stringify(sale) }),
  purchaseOrders: () => call<PurchaseOrder[]>("/api/purchase_orders"),
  receive: (id: number, received_by: string) =>
    call<Record<string, unknown>>(`/api/purchase_orders/${id}/receive`, { method: "POST", body: JSON.stringify({ received_by }) }),
  ticketPrice: (id: number) => call<TicketPrice>(`/api/pricing/${id}`),
  reset: () => call<Record<string, unknown>>("/api/reset", { method: "POST" }),
  health: () => call<{ ok: boolean; model: string; running: number | null }>("/api/health"),
};
