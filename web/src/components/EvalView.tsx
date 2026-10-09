"use client";

import { useCallback, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { MODE_LABELS, STRATEGY_LABELS, inr, label, ms, num, pct } from "@/lib/format";
import type { EvalReport, EvalRunOut, ModeSummary } from "@/lib/types";

import { type GroupRow, MODE_COLORS, ModeBarChart } from "./ModeBarChart";
import { Badge, Button, Card, ErrorBox, PageHeader, Stat } from "./ui";

const QUALITY: { key: keyof ModeSummary; name: string }[] = [
  { key: "hit_at_5", name: "Hit@5" },
  { key: "recall_at_5", name: "Recall@5" },
  { key: "mrr", name: "MRR" },
];

export function EvalView() {
  const [runs, setRuns] = useState<EvalRunOut[]>([]);
  const [current, setCurrent] = useState<EvalRunOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const loadRuns = useCallback(async () => {
    try {
      const list = await api.listEvalRuns();
      setRuns(list);
      const latest = list.find((r) => r.status !== "failed") ?? list[0];
      if (latest) setCurrent((existing) => existing ?? latest);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load runs");
    }
  }, []);

  useOnMount(loadRuns);

  const refreshCurrent = useCallback(async () => {
    if (!current) return;
    const updated = await api.getEvalRun(current.id);
    setCurrent(updated);
    if (updated.status !== "running") void loadRuns();
  }, [current, loadRuns]);
  usePolling(refreshCurrent, 3000, current?.status === "running");

  async function start(full: boolean) {
    if (full && !confirm("A full run generates answers for every question and mode. It spends Sarvam credits (cached re-runs are free). Continue?")) return;
    setStarting(true);
    setError(null);
    try {
      const run = await api.startEval(full);
      setCurrent(run);
      void loadRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run");
    } finally {
      setStarting(false);
    }
  }

  const running = current?.status === "running";
  const report = current?.status === "done" ? (current.metrics as EvalReport) : null;

  return (
    <>
      <PageHeader
        title="Evaluation Lab"
        subtitle="60 questions with known answers, run through every retrieval mode and the router."
        action={
          <div className="flex gap-2">
            <Button variant="secondary" disabled={starting || running} onClick={() => start(false)}>
              Run retrieval eval
            </Button>
            <Button disabled={starting || running} onClick={() => start(true)}>
              Run full eval
            </Button>
          </div>
        }
      />
      <ErrorBox message={error} />

      {runs.length > 1 && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-ink-soft">Runs:</span>
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => setCurrent(run)}
              className={`rounded-md px-2 py-1 ${run.id === current?.id ? "bg-muted text-ink" : "text-ink-soft hover:text-ink"}`}
            >
              {run.metrics.run?.created_at?.slice(0, 16).replace("T", " ") ?? run.status}
              {run.metrics.run && (run.metrics.run.full ? " · full" : " · retrieval")}
            </button>
          ))}
        </div>
      )}

      {!current && (
        <Card>
          <p className="text-sm text-ink-soft">
            No runs yet. A retrieval eval needs no answer-generation calls; the first run also
            indexes the demo corpus (one sampled LLM call per document, plus the graph when Neo4j
            is running).
          </p>
        </Card>
      )}
      {running && (
        <Card title="Running…">
          <p className="text-sm text-ink-soft">{current.progress || "Starting"}</p>
        </Card>
      )}
      {current?.status === "failed" && <ErrorBox message={`Run failed: ${current.metrics.error ?? "unknown error"}`} />}
      {report && <Report report={report} />}
    </>
  );
}

function Report({ report }: { report: EvalReport }) {
  const columns = Object.keys(report.modes);
  const overall = (mode: string) => report.modes[mode].overall;
  const types = Object.keys(report.modes[columns[0]].by_type).filter((t) => t !== "unanswerable");

  const qualityRows: GroupRow[] = QUALITY.map(({ key, name }) => ({
    group: name,
    ...Object.fromEntries(columns.map((m) => [m, Number(overall(m)[key] ?? 0)])),
  }));
  const typeRows: GroupRow[] = types.map((type) => ({
    group: type.replaceAll("_", " "),
    ...Object.fromEntries(columns.map((m) => [m, report.modes[m].by_type[type].recall_at_5])),
  }));
  const latencyKey = report.run.full ? "latency_ms" : "retrieval_ms";
  const latencyRows: GroupRow[] = (["p50", "p95"] as const).map((p) => ({
    group: p,
    ...Object.fromEntries(
      columns.map((m) => [m, Number(overall(m)[`${latencyKey}_${p}` as keyof ModeSummary] ?? 0)]),
    ),
  }));

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-soft">
        {report.run.questions} questions · {report.run.full ? "full answers" : "retrieval only"} ·
        graph {report.run.graph_available ? "available" : "not available (start Neo4j to compare graph modes)"} ·{" "}
        {report.run.seconds}s
      </p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Stat label="Router accuracy" value={pct(report.router.accuracy)} hint="Router's pick was among the best-scoring modes" />
        <Stat label="Strategy accuracy" value={pct(report.strategy.accuracy)} hint="Upload decision matched the best measured strategy" />
        <Stat label="Rule coverage" value={pct(report.rule_coverage)} hint="Questions classified without the LLM" />
        <Stat label="Analysis cost ratio" value={num(report.analysis_cost_ratio, 3)} hint="Sample tokens / full graph extraction tokens" />
        <Stat label="Rewrite gain" value={num(report.rewrite_gain, 3)} hint="Relevance after minus before, when rewritten" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Retrieval quality by mode">
          <ModeBarChart rows={qualityRows} modes={columns} format={(v) => v.toFixed(2)} domain={[0, 1]} />
        </Card>
        <Card title={report.run.full ? "End-to-end latency" : "Retrieval latency"}>
          <ModeBarChart rows={latencyRows} modes={columns} format={ms} />
        </Card>
      </div>
      <Card title="Recall@5 by question type">
        <ModeBarChart rows={typeRows} modes={columns} format={(v) => v.toFixed(2)} domain={[0, 1]} />
      </Card>

      <Card title="All metrics (table view)">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink-soft">
                <th className="py-2 pr-4 font-medium">Metric</th>
                {columns.map((m) => (
                  <th key={m} className="py-2 pr-4 text-right font-medium">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-sm" style={{ background: MODE_COLORS[m] }} />
                    {label(MODE_LABELS, m)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricRows(report.run.full).map(([key, name, fmt]) => (
                <tr key={key} className="border-b border-line/60">
                  <td className="py-1.5 pr-4 text-ink-soft">{name}</td>
                  {columns.map((m) => {
                    const value = overall(m)[key as keyof ModeSummary];
                    return (
                      <td key={m} className="py-1.5 pr-4 text-right tabular-nums text-ink">
                        {value == null ? "—" : fmt(Number(value))}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Upload decisions vs measured best strategy">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink-soft">
                <th className="py-2 pr-4 font-medium">Document</th>
                <th className="py-2 pr-4 font-medium">Decided</th>
                <th className="py-2 pr-4 font-medium">Best measured</th>
                <th className="py-2 pr-4 font-medium">Expected by design</th>
                <th className="py-2 pr-4 text-right font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {report.strategy.documents.map((row) => (
                <tr key={row.document} className="border-b border-line/60">
                  <td className="py-1.5 pr-4 text-ink">{row.document}</td>
                  <td className="py-1.5 pr-4">
                    <Badge tone={row.correct ? "good" : "warn"}>
                      {row.correct ? "✓ " : "✗ "}
                      {label(STRATEGY_LABELS, row.decided)}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-4 text-ink">{label(STRATEGY_LABELS, row.best_measured)}</td>
                  <td className="py-1.5 pr-4 text-ink-soft">{label(STRATEGY_LABELS, row.expected_by_design)}</td>
                  <td className="py-1.5 pr-4 text-right tabular-nums text-ink">{pct(row.confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function metricRows(full: boolean): [string, string, (v: number) => string][] {
  const two = (v: number) => v.toFixed(3);
  const rows: [string, string, (v: number) => string][] = [
    ["hit_at_5", "Hit@5", two],
    ["recall_at_5", "Recall@5", two],
    ["mrr", "MRR", two],
    ["retrieval_ms_p50", "Retrieval p50", ms],
    ["retrieval_ms_p95", "Retrieval p95", ms],
  ];
  if (full) {
    rows.push(
      ["answer_correctness", "Answer correctness", two],
      ["faithfulness", "Faithfulness", two],
      ["refusal_accuracy", "Refusal accuracy", two],
      ["false_refusals", "False refusals", two],
      ["latency_ms_p50", "Latency p50", ms],
      ["latency_ms_p95", "Latency p95", ms],
      ["tokens_per_query", "Tokens / query", (v) => Math.round(v).toLocaleString()],
      ["cost_inr_per_query", "Cost / query", inr],
    );
  }
  return rows;
}
