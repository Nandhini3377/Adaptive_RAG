// Display helpers: human labels for internal names, and number formatting.

import type { DocumentStatus, Intent, Mode } from "./types";

export const MODE_LABELS: Record<Mode | "router", string> = {
  vector: "Vector",
  hybrid: "Hybrid",
  graph: "Graph",
  graph_hybrid: "Graph + Hybrid",
  router: "Router",
};

export const STRATEGY_LABELS: Record<string, string> = {
  vector: "Vector",
  hybrid: "Hybrid",
  graph_hybrid: "Graph + Hybrid",
  "": "Not decided",
};

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  scanning: "Scanning",
  awaiting_intent: "Needs your input",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

export const INTENT_LABELS: Record<Intent, string> = {
  facts: "Look up facts or policies",
  exact_terms: "Find exact terms, IDs, or codes",
  connections: "Understand how things connect",
  compare: "Compare or summarize across sections",
};

export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key.replaceAll("_", " ");
}

export function ms(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

export function inr(value: number): string {
  return `₹${value < 0.01 && value > 0 ? value.toFixed(4) : value.toFixed(2)}`;
}

export function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}
