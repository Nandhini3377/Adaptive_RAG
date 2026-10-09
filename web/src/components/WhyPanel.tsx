"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { MODE_LABELS, inr, label, ms, num } from "@/lib/format";
import type { QueryOut } from "@/lib/types";

import { Badge, Button, Stat } from "./ui";

const STAGE_ORDER = ["classify", "route", "retrieve", "rerank", "evaluate", "rewrite", "generate", "ground", "regenerate", "refuse"];

/** "Why did I get this answer?" (FR36): every decision the pipeline made, with numbers. */
export function WhyPanel({ result }: { result: QueryOut }) {
  const [building, setBuilding] = useState<"idle" | "busy" | "started" | "error">("idle");
  const stages = STAGE_ORDER.filter((stage) => stage in result.timings);
  const slowest = Math.max(...stages.map((stage) => result.timings[stage]), 1);

  async function buildRecommended() {
    if (!result.recommendation) return;
    setBuilding("busy");
    try {
      await Promise.all(
        result.recommendation_document_ids.map((id) => api.buildIndex(id, result.recommendation!.index_to_build)),
      );
      setBuilding("started");
    } catch {
      setBuilding("error");
    }
  }

  return (
    <div className="space-y-5 text-sm">
      <section>
        <h3 className="mb-2 font-medium text-ink">Routing</h3>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{label({}, result.query_type)} question</Badge>
          <span className="text-ink-soft">classified by {result.classified_by === "rules" ? "rules (free)" : "the LLM"}</span>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-ink-soft">Ideal mode</span>
          <Badge tone="accent">{label(MODE_LABELS, result.ideal_mode)}</Badge>
          <span className="text-ink-soft">→ used</span>
          <Badge tone={result.mode === result.ideal_mode ? "good" : "warn"}>{label(MODE_LABELS, result.mode)}</Badge>
        </div>
        <p className="mt-2 text-ink-soft">{result.routing_reason}</p>
      </section>

      {result.recommendation && (
        <section className="rounded-lg border border-warn/40 bg-warn/8 p-3">
          <p className="text-ink">{result.recommendation.message}</p>
          <div className="mt-2 flex items-center gap-3">
            <Button variant="secondary" disabled={building !== "idle"} onClick={buildRecommended}>
              Build {result.recommendation.index_to_build === "bm25" ? "keyword index" : result.recommendation.index_to_build === "graph" ? "graph" : "keyword index + graph"}
            </Button>
            {building === "started" && <span className="text-good">Building in the background. Ask again when it&apos;s ready.</span>}
            {building === "error" && <span className="text-danger">Could not start the build.</span>}
          </div>
        </section>
      )}

      {result.rewrites.length > 0 && (
        <section>
          <h3 className="mb-2 font-medium text-ink">Self-correction</h3>
          <p className="text-ink-soft">
            The first search found weak evidence, so the question was rewritten and searched again.
          </p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-ink">
            {result.rewrites.map((rewrite) => (
              <li key={rewrite}>{rewrite}</li>
            ))}
          </ol>
        </section>
      )}

      <section>
        <h3 className="mb-2 font-medium text-ink">Scores</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Relevance" value={num(result.scores.relevance)} hint="From reranker scores (0-1). Below the threshold triggers a rewrite." />
          <Stat label="Grounding" value={num(result.scores.grounding)} hint="Share of claims supported by their cited chunk." />
          <Stat label="Regenerated" value={result.regenerated ? "Yes" : "No"} />
          <Stat label="Attempts" value={result.scores.relevance_history.length} />
        </div>
        {result.refused_reason && <p className="mt-2 text-warn">Refused: {result.refused_reason}.</p>}
      </section>

      {result.graph_paths.length > 0 && (
        <section>
          <h3 className="mb-2 font-medium text-ink">Graph paths</h3>
          <ul className="space-y-1.5 font-mono text-xs">
            {result.graph_paths.slice(0, 8).map((path, index) => (
              <li key={index} className="flex flex-wrap items-center gap-1 text-ink">
                {path.nodes.map((node, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="rounded bg-muted px-1.5 py-0.5">{node}</span>
                    {i < path.relations.length && <span className="text-ink-soft">{arrow(path.relations[i])}</span>}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="mb-2 font-medium text-ink">Time per stage</h3>
        <ul className="space-y-1">
          {stages.map((stage) => (
            <li key={stage} className="grid grid-cols-[6rem_1fr_4.5rem] items-center gap-2 text-xs">
              <span className="text-ink-soft">{stage}</span>
              <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                <span className="block h-full rounded-full bg-accent" style={{ width: `${(result.timings[stage] / slowest) * 100}%` }} />
              </span>
              <span className="text-right tabular-nums text-ink">{ms(result.timings[stage])}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-ink-soft">
          Total {ms(result.latency_ms)} · {result.llm_calls} LLM calls · {result.tokens.toLocaleString()} tokens
          ({result.reasoning_tokens.toLocaleString()} reasoning) · {inr(result.cost_inr)}
        </p>
      </section>
    </div>
  );
}

function arrow(relation: string): string {
  // "<-DEPENDS_ON" means the edge points back toward the previous node
  return relation.startsWith("<-") ? `←${relation.slice(2)}—` : `—${relation}→`;
}
