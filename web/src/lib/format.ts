// Display helpers: human labels for internal names, and number formatting.

import type { DocumentStatus, IndexName, Intent, Mode } from "./types";

export const MODE_LABELS: Record<Mode, string> = {
  vector: "Vector",
  keyword: "Keyword",
  hybrid: "Hybrid",
  graph: "Graph",
  graph_hybrid: "Graph + Hybrid",
};

/** Longer names for comparisons, where vector-only is the traditional-RAG baseline. */
export const MODE_COMPARE_LABELS: Record<Mode, string> = {
  vector: "Vector only (traditional RAG)",
  keyword: "Keyword only",
  hybrid: "Hybrid",
  graph: "Graph",
  graph_hybrid: "Graph + Hybrid",
};

export const STRATEGY_LABELS: Record<string, string> = {
  vector: "Vector",
  keyword: "Keyword only",
  hybrid: "Hybrid",
  graph: "Graph only",
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

/** "11 Oct 2026, 14:05" in the reader's own locale. */
export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
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

export const INDEX_LABELS: Record<IndexName, string> = {
  vector: "vector index",
  bm25: "keyword index",
  graph: "knowledge graph",
};

/** "bm25+graph" (or a list) -> "keyword index + knowledge graph". */
export function indexesLabel(indexes: string | string[]): string {
  const list = typeof indexes === "string" ? indexes.split("+") : indexes;
  return list.map((index) => label(INDEX_LABELS, index)).join(" + ");
}
