"use client";

import { type FormEvent, useCallback, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { MODE_LABELS, STRATEGY_LABELS, inr, label, ms, pct } from "@/lib/format";
import type { LabOut, LabQueryOut } from "@/lib/types";

import { CheckIcon } from "./icons";
import { ModeComparison } from "./ModeComparison";
import { Badge, Button, Card, ErrorBox, Loading, PageHeader, ProgressBar, SectionLabel } from "./ui";

// Same limit as the backend (settings.lab_max_chars)
const MAX_CHARS = 8000;
const BUSY = new Set(["scanning", "indexing"]);

/**
 * Evaluation Lab: a short text is indexed in every mode (normal uploads build only the one
 * the analysis picks), so each question shows whether that pick was the best one.
 */
export function LabView() {
  // undefined = still loading; null = no snippet yet
  const [lab, setLab] = useState<LabOut | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<LabQueryOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLab(await api.getLab());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the Lab");
    }
  }, []);

  useOnMount(load);
  const busy = !!lab && BUSY.has(lab.document.status);
  usePolling(load, 2000, busy);

  async function saveSnippet(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      setLab(await api.setLabSnippet(draft));
      setEditing(false);
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not index the snippet");
    } finally {
      setSaving(false);
    }
  }

  async function removeSnippet() {
    setError(null);
    try {
      await api.deleteLab();
      setLab(null);
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the snippet");
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    setAsking(true);
    setError(null);
    try {
      setResult(await api.labQuery(question.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The question failed");
    } finally {
      setAsking(false);
    }
  }

  function startEditing() {
    setDraft(lab?.text ?? "");
    setEditing(true);
  }

  const showForm = lab === null || editing;
  const ready = lab?.document.status === "ready";

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Evaluation Lab"
        subtitle="Index a short text in every search mode, ask a question, and see whether the mode Adaptive RAG would pick is the best one."
      />

      <ErrorBox message={error} className="mb-4" />

      {lab === undefined ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <Card
            title="Your text"
            action={
              lab && !editing && !busy ? (
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" onClick={startEditing}>
                    Replace
                  </Button>
                  <Button variant="danger" size="sm" onClick={removeSnippet}>
                    Delete
                  </Button>
                </div>
              ) : undefined
            }
          >
            {showForm ? (
              <SnippetForm
                draft={draft}
                setDraft={setDraft}
                saving={saving}
                onSubmit={saveSnippet}
                onCancel={lab ? () => setEditing(false) : undefined}
              />
            ) : (
              lab && <SnippetStatus lab={lab} />
            )}
          </Card>

          {ready && !editing && (
            <Card title="Ask a question">
              <form onSubmit={ask} className="flex flex-col gap-2 sm:flex-row">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  maxLength={2000}
                  placeholder="e.g. How many leave days do employees get?"
                  aria-label="Question"
                  className="field min-w-0 flex-1"
                />
                <Button type="submit" disabled={asking || !question.trim()}>
                  {asking ? "Comparing…" : "Compare modes"}
                </Button>
              </form>
              <p className="mt-2 text-xs text-ink-soft">
                Every mode searches and reranks the same way; one LLM call judges which chunks help. No answers are
                written, so each question costs a single short call.
              </p>
              {result && <LabResult result={result} />}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function SnippetForm({
  draft,
  setDraft,
  saving,
  onSubmit,
  onCancel,
}: {
  draft: string;
  setDraft: (text: string) => void;
  saving: boolean;
  onSubmit: (event: FormEvent) => void;
  onCancel?: () => void;
}) {
  return (
    <form onSubmit={onSubmit}>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        maxLength={MAX_CHARS}
        rows={10}
        placeholder={"# Leave Policy\n\nEmployees receive 20 days of annual leave per year.\n\n# Security\n\nAUTH-403 means the token has expired."}
        aria-label="Text to index"
        className="field h-auto resize-y py-3 font-mono text-[13px] leading-relaxed"
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs tabular-nums text-ink-soft">
          {draft.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} characters · Markdown headings become sections
        </span>
        <div className="flex gap-2">
          {onCancel && (
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" disabled={saving || !draft.trim()}>
            {saving ? "Starting…" : "Index in every mode"}
          </Button>
        </div>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        Indexing runs the normal analysis (one LLM call) and builds the knowledge graph (a few short calls), and
        counts as one question toward your daily limit. It replaces your previous Lab text.
      </p>
    </form>
  );
}

function SnippetStatus({ lab }: { lab: LabOut }) {
  const { document } = lab;
  if (document.status === "failed") {
    return <ErrorBox message={document.error || "Indexing failed. Replace the text to try again."} />;
  }
  if (BUSY.has(document.status)) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-ink">{document.stage || "Starting"}</span>
          <span className="tabular-nums text-ink-soft">{document.progress}%</span>
        </div>
        <ProgressBar value={document.progress} />
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line/70 bg-page/60 px-4 py-3.5">
        <div className="text-xs text-ink-soft">For a normal upload, the analysis would build</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-2">
          <span className="font-semibold text-ink">{label(STRATEGY_LABELS, lab.strategy ?? "")}</span>
          {lab.confidence != null && <Badge>confidence {pct(lab.confidence)}</Badge>}
        </div>
        {lab.reason && <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">{lab.reason}</p>}
      </div>
      <div>
        <SectionLabel>Indexed here for comparison</SectionLabel>
        <div className="flex flex-wrap gap-1.5">
          {lab.modes.map((mode) => (
            <Badge key={mode} tone="accent">
              {label(MODE_LABELS, mode)}
            </Badge>
          ))}
        </div>
        {!lab.modes.includes("graph") && (
          <p className="mt-2 text-xs text-ink-soft">The graph modes need the graph database running.</p>
        )}
      </div>
      <details>
        <summary className="cursor-pointer select-none text-xs text-ink-soft transition-colors hover:text-ink">
          Show the text
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-muted px-4 py-3 font-mono text-xs leading-relaxed text-ink">
          {lab.text}
        </pre>
      </details>
    </div>
  );
}

function LabResult({ result }: { result: LabQueryOut }) {
  const picked = label(MODE_LABELS, result.adaptive_mode);
  const nothing = result.best_modes.length === 0;
  const right = result.best_modes.includes(result.adaptive_mode);
  return (
    <div className="mt-6 space-y-5 border-t border-line/70 pt-5">
      <div
        className={`rounded-xl border px-4 py-3.5 text-sm ${
          nothing ? "border-line/70 bg-page/60" : right ? "border-good/40 bg-good/8" : "border-warn/40 bg-warn/8"
        }`}
      >
        <p className="text-ink">
          Adaptive RAG would use <strong>{picked}</strong>{" "}
          <span className="text-ink-soft">
            ({label({}, result.query_type)} question, {result.classified_by === "rules" ? "classified by rules" : "classified by the LLM"};
            the analysis built {label(STRATEGY_LABELS, result.strategy)})
          </span>
        </p>
        <p className="mt-1 flex items-center gap-1.5 font-medium">
          {nothing ? (
            <span className="text-ink-soft">No mode found a relevant chunk: the text may not answer this question.</span>
          ) : right ? (
            <>
              <CheckIcon className="text-good" />
              <span className="text-good">That was the best mode for this question.</span>
            </>
          ) : (
            <span className="text-warn">
              Best measured: {result.best_modes.map((m) => label(MODE_LABELS, m)).join(", ")}
            </span>
          )}
        </p>
      </div>

      <ModeComparison modes={result.modes} usedLabel="Adaptive pick" best={result.best_modes} />

      <p className="text-xs leading-relaxed text-ink-soft">
        {result.relevant_in_pool} of {result.pool_size} pooled chunks judged relevant by the LLM. Recall is relative to
        what any mode found. {ms(result.latency_ms)} · {result.llm_calls} LLM {result.llm_calls === 1 ? "call" : "calls"} ·{" "}
        {inr(result.cost_inr)}
      </p>

      <div>
        <SectionLabel>What each mode found</SectionLabel>
        <div className="space-y-2">
          {result.modes.map((mode) => (
            <details key={mode.mode} className="rounded-xl border border-line/70 px-4 py-2.5">
              <summary className="cursor-pointer select-none text-sm text-ink">
                {label(MODE_LABELS, mode.mode)}{" "}
                <span className="text-ink-soft">
                  · {mode.relevant} of {mode.found} relevant
                </span>
              </summary>
              <ol className="mt-2 space-y-2 pb-1">
                {mode.chunks.map((chunk, index) => (
                  <li key={index} className="flex gap-2.5 text-xs leading-relaxed">
                    <span className="w-4 shrink-0 tabular-nums text-ink-soft">{index + 1}</span>
                    <span className="min-w-0 flex-1">
                      {chunk.section && <span className="block text-ink-soft">{chunk.section}</span>}
                      <span className="line-clamp-3 break-words text-ink">{chunk.text}</span>
                    </span>
                    {chunk.relevant && <Badge tone="good">relevant</Badge>}
                  </li>
                ))}
                {mode.chunks.length === 0 && <li className="text-xs text-ink-soft">Nothing found.</li>}
              </ol>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
