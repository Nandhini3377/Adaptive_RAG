"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { MODE_LABELS, inr, label, ms } from "@/lib/format";
import type { QueryOut } from "@/lib/types";

import { ArrowRightIcon } from "./icons";
import { Button, Meter, SectionLabel, Stat } from "./ui";

const STAGE_ORDER = ["classify", "route", "retrieve", "rerank", "evaluate", "rewrite", "generate", "ground", "regenerate", "refuse", "measure"];

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
    <div className="space-y-6 text-sm">
      <section>
        <SectionLabel>Routing</SectionLabel>
        <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
          <FlowStep
            title="Question type"
            value={label({}, result.query_type)}
            note={result.classified_by === "rules" ? "by rules (free)" : "by the LLM"}
          />
          <ArrowRightIcon className="hidden shrink-0 text-ink-soft sm:block" />
          <FlowStep title="Ideal mode" value={label(MODE_LABELS, result.ideal_mode)} note="best for this type" />
          <ArrowRightIcon className="hidden shrink-0 text-ink-soft sm:block" />
          <FlowStep
            title="Mode used"
            value={label(MODE_LABELS, result.mode)}
            note={result.mode === result.ideal_mode ? "the ideal one" : "best index available"}
            tone={result.mode === result.ideal_mode ? "good" : "warn"}
          />
        </div>
        <p className="mt-2.5 leading-relaxed text-ink-soft">{result.routing_reason}</p>
      </section>

      {result.recommendation && (
        <section className="rounded-lg border border-warn/30 bg-warn/8 p-3.5">
          <p className="text-ink">{result.recommendation.message}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button variant="secondary" size="sm" disabled={building !== "idle"} onClick={buildRecommended}>
              Build {result.recommendation.index_to_build === "bm25" ? "keyword index" : result.recommendation.index_to_build === "graph" ? "graph" : "keyword index + graph"}
            </Button>
            {building === "started" && <span className="text-good">Building in the background. Ask again when it&apos;s ready.</span>}
            {building === "error" && <span className="text-danger">Could not start the build.</span>}
          </div>
        </section>
      )}

      {result.rewrites.length > 0 && (
        <section>
          <SectionLabel>Self-correction</SectionLabel>
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

      {result.quality && (
        <section>
          <SectionLabel>Retrieval quality</SectionLabel>
          <div className="grid gap-3 sm:grid-cols-2">
            <Meter
              label="Precision"
              value={result.quality.precision}
              hint={`${result.quality.relevant_used} of the ${result.quality.used} chunks given to the model were relevant to the question.`}
            />
            <Meter
              label="Relative recall"
              value={result.quality.relative_recall}
              hint={
                result.quality.compared_modes.length === 0
                  ? "Not measured: these documents have only one index, so there is no other search to compare with."
                  : result.quality.relevant_in_pool === 0
                    ? "Not measured: no search mode found a relevant chunk."
                    : `Found ${result.quality.relevant_used} of the ${result.quality.relevant_in_pool} relevant chunks that any mode found (also searched: ${result.quality.compared_modes.map((m) => label(MODE_LABELS, m)).join(", ")}).`
              }
            />
          </div>
          <p className="mt-2.5 text-xs leading-relaxed text-ink-soft">
            Relevance is judged by the LLM. Recall is relative: a relevant chunk that no mode found
            cannot be counted.
          </p>
        </section>
      )}

      <section>
        <SectionLabel>Scores</SectionLabel>
        <div className="grid gap-3 sm:grid-cols-2">
          <Meter label="Relevance" value={result.scores.relevance} hint="Reranker score of the evidence, from 0 to 1." />
          <Meter
            label="Grounding"
            value={result.scores.grounding}
            hint="Share of claims supported by their cited chunk."
          />
          <Stat label="Regenerated" value={result.regenerated ? "Yes" : "No"} />
          <Stat label="Attempts" value={result.scores.relevance_history.length} />
        </div>
        {result.refused_reason && <p className="mt-2 text-warn">Refused: {result.refused_reason}.</p>}
      </section>

      {result.graph_paths.length > 0 && (
        <section>
          <SectionLabel>Graph paths</SectionLabel>
          <ul className="space-y-1.5 font-mono text-xs">
            {result.graph_paths.slice(0, 8).map((path, index) => (
              <li key={index} className="flex flex-wrap items-center gap-1 text-ink">
                {path.nodes.map((node, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="rounded-md bg-accent/10 px-2 py-1 text-accent">{node}</span>
                    {i < path.relations.length && <span className="text-ink-soft">{arrow(path.relations[i])}</span>}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <SectionLabel>Time per stage</SectionLabel>
        <ul className="space-y-1.5">
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
        <p className="mt-3 text-xs text-ink-soft">
          Total {ms(result.latency_ms)} · {result.llm_calls} LLM calls · {result.tokens.toLocaleString()} tokens
          ({result.reasoning_tokens.toLocaleString()} reasoning) · {inr(result.cost_inr)}
        </p>
      </section>
    </div>
  );
}

/** One box in the routing flow: question type, ideal mode, mode used. */
function FlowStep({
  title,
  value,
  note,
  tone = "neutral",
}: {
  title: string;
  value: string;
  note: string;
  tone?: "neutral" | "good" | "warn";
}) {
  const styles = {
    neutral: "border-line/70 bg-page/60",
    good: "border-good/40 bg-good/8",
    warn: "border-warn/40 bg-warn/8",
  }[tone];
  return (
    <div className={`min-w-0 flex-1 rounded-xl border px-4 py-3 ${styles}`}>
      <div className="text-xs text-ink-soft">{title}</div>
      <div className="mt-0.5 font-semibold capitalize text-ink">{value}</div>
      <div className="text-xs text-ink-soft">{note}</div>
    </div>
  );
}

function arrow(relation: string): string {
  // "<-DEPENDS_ON" means the edge points back toward the previous node
  return relation.startsWith("<-") ? `←${relation.slice(2)}—` : `—${relation}→`;
}
