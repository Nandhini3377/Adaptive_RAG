"use client";

import { useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { MODE_LABELS, STRATEGY_LABELS, label, ms } from "@/lib/format";
import type { DocumentOut, Mode, QueryOut } from "@/lib/types";

import { WhyPanel } from "./WhyPanel";
import { Badge, Button, Card, ErrorBox, PageHeader } from "./ui";

interface Turn {
  question: string;
  result?: QueryOut;
  error?: string;
}

const MODES: (Mode | "auto")[] = ["auto", "vector", "hybrid", "graph", "graph_hybrid"];

export function ChatView() {
  const preselected = useSearchParams().get("doc");
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selected, setSelected] = useState<string[]>(preselected ? [preselected] : []);
  const [mode, setMode] = useState<Mode | "auto">("auto");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => d.status === "ready")))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load documents"));
  }, []);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text) return;
    setAsking(true);
    setQuestion("");
    setTurns((current) => [...current, { question: text }]);
    let turn: Turn;
    try {
      const result = await api.query(
        text,
        selected.length ? selected : undefined,
        mode === "auto" ? undefined : mode,
      );
      turn = { question: text, result };
    } catch (err) {
      turn = { question: text, error: err instanceof Error ? err.message : "The question failed" };
    }
    setTurns((current) => [...current.slice(0, -1), turn]);
    setAsking(false);
  }

  return (
    <>
      <PageHeader
        title="Ask"
        subtitle="Each question is classified and routed to the best index each document has."
      />
      <ErrorBox message={error} />
      <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
        <aside className="space-y-4">
          <Card title="Search in">
            {documents.length === 0 ? (
              <p className="text-sm text-ink-soft">No ready documents yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {documents.map((doc) => (
                  <li key={doc.id}>
                    <label className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={selected.includes(doc.id)}
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? [...selected, doc.id]
                              : selected.filter((id) => id !== doc.id),
                          )
                        }
                      />
                      <span>
                        <span className="block text-ink">{doc.filename}</span>
                        <span className="text-xs text-ink-soft">{label(STRATEGY_LABELS, doc.strategy)}</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-ink-soft">None selected = all ready documents.</p>
          </Card>
          <Card title="Mode">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as Mode | "auto")}
              className="w-full rounded-lg border border-line bg-page px-2 py-1.5 text-sm text-ink"
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m === "auto" ? "Automatic (router)" : label(MODE_LABELS, m)}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-ink-soft">Manual modes are for comparing and debugging.</p>
          </Card>
        </aside>

        <div className="space-y-4">
          {turns.length === 0 && (
            <Card>
              <p className="text-sm text-ink-soft">
                Try a fact (&ldquo;How many leave days do we get?&rdquo;), an exact code
                (&ldquo;What is AUTH-403?&rdquo;), or a relationship (&ldquo;What depends on the
                Auth Service?&rdquo;) and open the explanation under the answer.
              </p>
            </Card>
          )}
          {turns.map((turn, index) => (
            <TurnView key={index} turn={turn} />
          ))}
          <form onSubmit={ask} className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your documents…"
              maxLength={2000}
              className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
            <Button type="submit" disabled={asking || !question.trim()}>
              {asking ? "Thinking…" : "Ask"}
            </Button>
          </form>
        </div>
      </div>
    </>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const [showWhy, setShowWhy] = useState(false);
  const [openCitation, setOpenCitation] = useState<number | null>(null);
  const { result } = turn;

  return (
    <div className="space-y-2">
      <p className="ml-auto w-fit max-w-[85%] rounded-xl bg-accent px-3.5 py-2 text-sm text-white">
        {turn.question}
      </p>
      {!result && !turn.error && <p className="text-sm text-ink-soft">Searching and writing an answer…</p>}
      {turn.error && <ErrorBox message={turn.error} />}
      {result && (
        <Card>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone={result.mode === result.ideal_mode ? "good" : "warn"}>{label(MODE_LABELS, result.mode)}</Badge>
            {result.insufficient_evidence && <Badge tone="warn">Not enough evidence</Badge>}
            {result.rewrites.length > 0 && <Badge>Rewritten {result.rewrites.length}×</Badge>}
            <span className="ml-auto text-xs text-ink-soft">{ms(result.latency_ms)}</span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{result.answer}</p>

          {result.citations.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {result.citations.map((citation) => (
                <li key={citation.number} className="text-sm">
                  <button
                    type="button"
                    className="text-left text-ink-soft hover:text-ink"
                    onClick={() => setOpenCitation(openCitation === citation.number ? null : citation.number)}
                  >
                    <span className="font-medium text-accent">[{citation.number}]</span>{" "}
                    {result.documents[citation.document_id] ?? "Document"}
                    {citation.section && ` › ${citation.section}`}
                    {citation.page && `, page ${citation.page}`}
                  </button>
                  {openCitation === citation.number && (
                    <pre className="mt-1.5 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 font-sans text-xs text-ink">
                      {citation.text}
                    </pre>
                  )}
                </li>
              ))}
            </ul>
          )}

          {result.recommendation && !showWhy && (
            <p className="mt-3 text-sm text-warn">{result.recommendation.message}</p>
          )}

          <button
            type="button"
            className="mt-4 text-sm font-medium text-accent hover:underline"
            onClick={() => setShowWhy(!showWhy)}
          >
            {showWhy ? "Hide explanation" : "Why did I get this answer?"}
          </button>
          {showWhy && (
            <div className="mt-4 border-t border-line pt-4">
              <WhyPanel result={result} />
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
