import type { AgentName } from "./types";

export interface AgentStyle {
  name: AgentName;
  emoji: string;
  role: string;
  color: string;   // solid identity color
  soft: string;    // tinted background
  ink: string;     // readable text on the soft background
}

// Each teammate gets one color, one emoji and one voice on the desk.
export const AGENTS: AgentStyle[] = [
  { name: "Boss", emoji: "🧢", role: "Routes work, makes the call", color: "#00356b", soft: "#e1efff", ink: "#00356b" },
  { name: "Inventory", emoji: "📦", role: "Stock, shortfalls, restocks", color: "#10b3a3", soft: "#d8f6f2", ink: "#0b6b62" },
  { name: "Accounting", emoji: "🧾", role: "Cash, invoices, margins", color: "#e6a700", soft: "#fff3cc", ink: "#7a4d00" },
  { name: "Facilities", emoji: "🏬", role: "Leases, rent, the shop", color: "#ff7b54", soft: "#ffe6dc", ink: "#a33a12" },
  { name: "Customer Service", emoji: "💬", role: "Drafts customer messages", color: "#7a5cff", soft: "#ebe6ff", ink: "#4b2fd1" },
];

export const AGENT = Object.fromEntries(AGENTS.map((a) => [a.name, a])) as Record<AgentName, AgentStyle>;

export const TICKET_ICON: Record<string, string> = {
  customer_order: "👕",
  rent_notice: "🏠",
  price_override: "🏷️",
};

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export const prettyTool = (t: string) => t.replace(/_/g, " ");
