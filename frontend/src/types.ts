export type AgentName = "Boss" | "Inventory" | "Accounting" | "Facilities" | "Customer Service";

export interface RunInfo {
  run_id: string;
  ticket_id: number;
  status: "running" | "finished" | "error";
  started_at: string;
  finished_at?: string;
  error?: string;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: "open" | "in_progress" | "awaiting_approval" | "blocked" | "resolved";
  notes: string | null;
  resolution: string | null;
  state: "open" | "running" | "resolved";
  running: boolean;
  last_run: RunInfo | null;
}

export interface AgentEvent {
  id: number;
  ts: string;
  run_id: string;
  ticket_id: number | null;
  agent: AgentName;
  chain: AgentName[];
  kind: "run_start" | "model_response" | "tool_call" | "tool_result" | "delegate" | "delegate_refused"
    | "final_output" | "error" | "run_end";
  text: string;
  tool: string | null;
  detail: unknown;
}

export interface AgentSummary {
  agent: AgentName;
  tasks: number;
  tools: Record<string, number>;
  summary: string;
  actions: string[];
  approvals: number[];
}

export interface TicketSummary {
  ticket_id: number;
  run_id: string | null;
  finished: boolean;
  usage: { requests: number; input_tokens: number; output_tokens: number; total_tokens: number } | null;
  delegations: { from: AgentName; to: AgentName; task: string }[];
  agents: AgentSummary[];
}

export interface Cash {
  name: string;
  balance: number;
  date: string;
  pending_approvals_total: number;
  balance_after_pending: number;
  opening_balance: number | null;
  total_sales: number;
  total_payments: number;
  ties_out: boolean;
}

export interface Approval {
  id: number;
  ticket_id: number | null;
  kind: "invoice" | "rent" | "purchase_order";
  payee: string;
  amount: number;
  details: Record<string, unknown>;
  reason: string;
  requested_by: AgentName;
  status: "pending" | "paid" | "rejected" | "refused";
  decided_by: string | null;
  decision_note: string | null;
}

export interface Draft {
  id: number;
  ticket_id: number;
  recipient: string;
  subject: string;
  body: string;
  author: string;
  created_at: string;
}

export interface Sale {
  id: number;
  ticket_id: number | null;
  customer: string;
  sku: string;
  size: string;
  qty: number;
  unit_price: number;
  revenue: number;
  cogs: number;
  recorded_by: string;
  created_at: string;
}

export interface PurchaseOrder {
  id: number;
  vendor_name: string;
  sku: string;
  size: string;
  qty: number;
  total: number;
  status: "ordered" | "received";
  ordered_on: string;
  eta: string;
  ticket_id: number | null;
  received_on: string | null;
  received_by: string | null;
}

export interface TicketPrice {
  ticket_id: number;
  sku: string | null;
  customer?: string;
  size?: string;
  qty?: number;
  already_sold?: number;
  on_shelf?: number;
  list_price?: number | null;
  unit_cost?: number | null;
  agreed_price?: number | null;
}
