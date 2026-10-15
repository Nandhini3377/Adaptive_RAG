"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, Fragment, type KeyboardEvent, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { MODE_LABELS, STRATEGY_LABELS, inr, label, ms, pct } from "@/lib/format";
import { type DocumentOut, type IndexName, MODE_INDEXES, type Mode, type QueryOut } from "@/lib/types";

import {
  ArrowRightIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronDownIcon,
  CopyIcon,
  FileIcon,
  GraphIcon,
  HashIcon,
  LayersIcon,
  Logo,
  PlusIcon,
  SparkIcon,
} from "./icons";
import { WhyPanel } from "./WhyPanel";
import { Badge, Button, ErrorBox, SectionLabel } from "./ui";

interface Turn {
  question: string;
  result?: QueryOut;
  error?: string;
}

const MODES: (Mode | "auto")[] = ["auto", "vector", "keyword", "hybrid", "graph", "graph_hybrid"];

// One example per question type: a fact, an exact code, a relationship
const EXAMPLES = [
  { kind: "A fact", question: "How many leave days do we get?", icon: LayersIcon },
  { kind: "An exact code", question: "What is AUTH-403?", icon: HashIcon },
  { kind: "A relationship", question: "What depends on the Auth Service?", icon: GraphIcon },
];

export function ChatView() {
  const preselected = useSearchParams().get("doc");
  // null until the first load finishes
  const [documents, setDocuments] = useState<DocumentOut[] | null>(null);
  const [selected, setSelected] = useState<string[]>(preselected ? [preselected] : []);
  const [mode, setMode] = useState<Mode | "auto">("auto");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [pickingDocuments, setPickingDocuments] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => d.status === "ready")))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load documents"));
  }, []);

  // Bring a newly asked question into view
  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  const ready = documents ?? [];
  // Same rule as the backend (router.available_modes): a mode needs all its indexes on
  // every document being searched.
  const searched = selected.length ? ready.filter((d) => selected.includes(d.id)) : ready;
  const built = (doc: DocumentOut): IndexName[] => [
    ...(doc.has_vector ? (["vector"] as const) : []),
    ...(doc.has_bm25 ? (["bm25"] as const) : []),
    ...(doc.graph_status === "ready" ? (["graph"] as const) : []),
  ];
  const shared = (["vector", "bm25", "graph"] as IndexName[]).filter(
    (index) => searched.length > 0 && searched.every((doc) => built(doc).includes(index)),
  );
  const modes = MODES.filter((m) => m === "auto" || MODE_INDEXES[m].every((index) => shared.includes(index)));
  // A mode that stops existing (after changing the documents) falls back to automatic
  const activeMode = modes.includes(mode) ? mode : "auto";

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || asking) return;
    setAsking(true);
    setQuestion("");
    setTurns((current) => [...current, { question: text }]);
    let turn: Turn;
    try {
      const result = await api.query(
        text,
        selected.length ? selected : undefined,
        activeMode === "auto" ? undefined : activeMode,
      );
      turn = { question: text, result };
    } catch (err) {
      turn = { question: text, error: err instanceof Error ? err.message : "The question failed" };
    }
    setTurns((current) => [...current.slice(0, -1), turn]);
    setAsking(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter adds a line (and Enter while composing text, e.g. Japanese, is left alone)
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const noDocuments = documents !== null && documents.length === 0;
  const scope =
    selected.length === 0
      ? `All documents (${ready.length})`
      : searched.length === 1
        ? searched[0].filename
        : `${searched.length} documents`;

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-8rem)] max-w-3xl flex-col lg:min-h-[calc(100dvh-5rem)]">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Ask</h1>
          <p className="mt-0.5 text-sm text-ink-soft">Routed to the best index each document has.</p>
        </div>
        {turns.length > 0 && (
          <Button variant="secondary" size="sm" disabled={asking} onClick={() => setTurns([])}>
            <PlusIcon width={14} height={14} />
            New chat
          </Button>
        )}
      </div>
      <ErrorBox message={error} className="mb-4" />

      <div className="flex flex-1 flex-col">
        {turns.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center py-6 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-accent-strong text-on-accent shadow-lg shadow-accent/30">
              <SparkIcon width={26} height={26} />
            </span>
            <h2 className="mt-6 text-3xl font-semibold tracking-tight text-ink">What do you want to know?</h2>
            {noDocuments ? (
              <p className="mt-3 max-w-md text-sm leading-relaxed text-ink-soft">
                No documents are ready yet.{" "}
                <Link href="/" className="font-medium text-accent hover:underline">
                  Upload one
                </Link>{" "}
                and come back to ask about it.
              </p>
            ) : (
              <>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-ink-soft">
                  Ask about your documents. Every answer shows its sources, its precision and
                  recall, and how it was routed.
                </p>
                <div className="mt-8 grid w-full gap-3 text-left sm:grid-cols-3">
                  {EXAMPLES.map((example) => (
                    <button
                      key={example.question}
                      type="button"
                      onClick={() => {
                        setQuestion(example.question);
                        box.current?.focus();
                      }}
                      className="flex flex-col items-start rounded-2xl border border-line/70 bg-surface p-4 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-accent/50"
                    >
                      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent">
                        <example.icon width={18} height={18} />
                      </span>
                      <span className="mt-3 text-xs font-semibold uppercase tracking-wider text-ink-soft">
                        {example.kind}
                      </span>
                      <span className="mt-1 text-sm font-medium leading-snug text-ink">{example.question}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 space-y-8">
            {turns.map((turn, index) => (
              <TurnView key={index} turn={turn} />
            ))}
          </div>
        )}
      </div>

      {/* Stays at the bottom of the screen; the fade keeps answers readable as they scroll under it */}
      <div className="sticky bottom-0 bg-gradient-to-t from-page from-70% to-transparent pb-4 pt-10">
        <form
          onSubmit={ask}
          className="rounded-3xl border border-line bg-surface shadow-xl shadow-black/8 transition-colors focus-within:border-accent"
        >
          <textarea
            ref={box}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            rows={Math.min(6, question.split("\n").length)}
            placeholder="Ask a question about your documents…"
            aria-label="Your question"
            maxLength={2000}
            className="block w-full resize-none bg-transparent px-5 pb-2 pt-4 text-[15px] leading-6 text-ink outline-none placeholder:text-ink-soft/70"
          />
          <div className="flex items-center gap-2 px-3 pb-3">
            <div className="relative shrink-0">
              <button
                type="button"
                aria-expanded={pickingDocuments}
                onClick={() => setPickingDocuments(!pickingDocuments)}
                className="inline-flex max-w-40 items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-muted"
              >
                <FileIcon width={14} height={14} className="shrink-0 text-ink-soft" />
                <span className="truncate">{scope}</span>
                <ChevronDownIcon width={12} height={12} className="shrink-0 text-ink-soft" />
              </button>
              {pickingDocuments && (
                <>
                  {/* A click anywhere else closes the list */}
                  <button
                    type="button"
                    aria-label="Close the document list"
                    className="fixed inset-0 z-10 cursor-default"
                    onClick={() => setPickingDocuments(false)}
                  />
                  <div className="absolute bottom-full left-0 z-20 mb-2 w-80 max-w-[calc(100vw-3rem)] rounded-2xl border border-line bg-surface p-2 shadow-xl shadow-black/10">
                    <p className="px-2.5 pb-1.5 pt-2 text-xs font-semibold uppercase tracking-wider text-ink-soft">
                      Search in
                    </p>
                    {ready.length === 0 ? (
                      <p className="px-2.5 pb-2 text-sm text-ink-soft">No ready documents yet.</p>
                    ) : (
                      <ul className="max-h-64 overflow-y-auto text-sm">
                        {ready.map((doc) => (
                          <li key={doc.id}>
                            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl px-2.5 py-2 transition-colors hover:bg-muted/70 has-[:checked]:bg-accent/8">
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
                              <span className="min-w-0">
                                <span className="block break-words text-ink">{doc.filename}</span>
                                <span className="text-xs text-ink-soft">{label(STRATEGY_LABELS, doc.strategy)}</span>
                              </span>
                            </label>
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="border-t border-line/70 px-2.5 pb-1 pt-2.5 text-xs text-ink-soft">
                      None ticked means all ready documents.
                    </p>
                  </div>
                </>
              )}
            </div>

            <div
              role="group"
              aria-label="Retrieval mode"
              className="flex min-w-0 items-center gap-0.5 overflow-x-auto rounded-full bg-muted p-0.5"
            >
              {modes.map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={m === activeMode}
                  onClick={() => setMode(m)}
                  className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs transition-colors ${
                    m === activeMode ? "bg-surface font-medium text-ink shadow-sm" : "text-ink-soft hover:text-ink"
                  }`}
                >
                  {m === "auto" ? "Automatic" : label(MODE_LABELS, m)}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={asking || !question.trim()}
              aria-label={asking ? "Thinking" : "Ask"}
              className="ml-auto flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent transition-all hover:bg-accent-strong active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {asking ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-on-accent/40 border-t-on-accent" />
              ) : (
                <ArrowUpIcon />
              )}
            </button>
          </div>
        </form>
        <p className="mt-2 text-center text-[11px] text-ink-soft">
          {modes.length < MODES.length
            ? "Only modes these documents have an index for are shown. Build the keyword index or graph to unlock more."
            : "Enter to send · Shift + Enter for a new line"}
        </p>
        <div ref={end} />
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const [showWhy, setShowWhy] = useState(false);
  const [openCitation, setOpenCitation] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const { result } = turn;

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked by the browser: nothing to do
    }
  }

  return (
    <div className="space-y-4">
      <p className="ml-auto w-fit max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-br-lg bg-accent px-5 py-3 text-[15px] leading-relaxed text-on-accent">
        {turn.question}
      </p>

      {!result && !turn.error && (
        <div className="flex items-center gap-3 text-sm text-ink-soft" role="status">
          <Logo />
          <span className="flex gap-1" aria-hidden="true">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-soft [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-soft [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-soft" />
          </span>
          Searching, answering, and checking the answer…
        </div>
      )}
      {turn.error && <ErrorBox message={turn.error} />}

      {result && (
        <div className="rounded-3xl border border-line/70 bg-surface p-5 shadow-card sm:p-6">
          {/* How the question was handled, at a glance: its type, then the mode that answered it */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Logo />
            <Badge>{label({}, result.query_type)} question</Badge>
            <ArrowRightIcon width={14} height={14} className="text-ink-soft" />
            <Badge tone={result.mode === result.ideal_mode ? "good" : "warn"} dot>
              {label(MODE_LABELS, result.mode)}
            </Badge>
            {result.insufficient_evidence && <Badge tone="warn">Not enough evidence</Badge>}
            {result.rewrites.length > 0 && <Badge>Rewritten {result.rewrites.length}×</Badge>}
            <button
              type="button"
              onClick={copy}
              className="ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs text-ink-soft transition-colors hover:bg-muted hover:text-ink"
            >
              {copied ? <CheckIcon width={13} height={13} /> : <CopyIcon width={13} height={13} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>

          <AnswerText
            text={result.answer}
            known={new Set(result.citations.map((c) => c.number))}
            onCite={setOpenCitation}
          />

          <dl className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric name="Precision" value={pct(result.quality?.precision)} />
            <Metric name="Relative recall" value={pct(result.quality?.relative_recall)} />
            <Metric name="Grounding" value={pct(result.scores.grounding)} />
            <Metric name="Time" value={ms(result.latency_ms)} />
          </dl>

          {result.citations.length > 0 && (
            <div className="mt-5">
              <SectionLabel>Sources</SectionLabel>
              <ul className="space-y-1">
                {result.citations.map((citation) => (
                  <li key={citation.number} className="text-sm">
                    <button
                      type="button"
                      aria-expanded={openCitation === citation.number}
                      className="-mx-2 flex w-[calc(100%+1rem)] items-start gap-2.5 rounded-lg px-2 py-1.5 text-left text-ink-soft transition-colors hover:bg-muted hover:text-ink"
                      onClick={() => setOpenCitation(openCitation === citation.number ? null : citation.number)}
                    >
                      <span className="mt-px flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md bg-accent/10 px-1 text-[11px] font-semibold tabular-nums text-accent">
                        {citation.number}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="font-medium text-ink">
                          {result.documents[citation.document_id] ?? "Document"}
                        </span>
                        {citation.section && ` › ${citation.section}`}
                        {citation.page && `, page ${citation.page}`}
                      </span>
                      <ChevronDownIcon
                        width={14}
                        height={14}
                        className={`mt-1 shrink-0 transition-transform ${openCitation === citation.number ? "rotate-180" : ""}`}
                      />
                    </button>
                    {openCitation === citation.number && (
                      <pre className="mb-2 mt-1.5 max-h-56 overflow-auto whitespace-pre-wrap rounded-xl border-l-2 border-accent/50 bg-muted p-3.5 font-sans text-xs leading-relaxed text-ink">
                        {citation.text}
                      </pre>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.recommendation && !showWhy && (
            <p className="mt-4 rounded-xl border border-warn/30 bg-warn/8 px-3.5 py-2.5 text-sm text-ink">
              {result.recommendation.message}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line/70 pt-4">
            <button
              type="button"
              aria-expanded={showWhy}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3.5 py-1.5 text-sm font-medium text-accent transition-colors hover:bg-accent/15"
              onClick={() => setShowWhy(!showWhy)}
            >
              <SparkIcon width={14} height={14} />
              {showWhy ? "Hide explanation" : "Why did I get this answer?"}
              <ChevronDownIcon width={14} height={14} className={`transition-transform ${showWhy ? "rotate-180" : ""}`} />
            </button>
            <span className="text-xs tabular-nums text-ink-soft">
              {result.llm_calls} LLM calls · {result.tokens.toLocaleString()} tokens · {inr(result.cost_inr)}
            </span>
          </div>
          {showWhy && (
            <div className="mt-5">
              <WhyPanel result={result} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// "[1]" and lists like "[1, 3]"
const CITATION = /(\[\d+(?:\s*,\s*\d+)*\])/;

/** The answer, with each [n] citation turned into a chip that opens its source. */
function AnswerText({
  text,
  known,
  onCite,
}: {
  text: string;
  known: Set<number>;
  onCite: (number: number) => void;
}) {
  return (
    <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
      {text.split(CITATION).map((part, index) => {
        if (!CITATION.test(part)) return part;
        const numbers = part.slice(1, -1).split(",").map(Number);
        // A number with no matching source is left as plain text
        if (!numbers.every((n) => known.has(n))) return part;
        return (
          <Fragment key={index}>
            {numbers.map((n) => (
              <button
                key={n}
                type="button"
                title={`Show source ${n}`}
                onClick={() => onCite(n)}
                className="mx-px inline-flex h-[18px] min-w-[18px] -translate-y-0.5 items-center justify-center rounded-md bg-accent/10 px-1 text-[11px] font-semibold tabular-nums text-accent transition-colors hover:bg-accent hover:text-on-accent"
              >
                {n}
              </button>
            ))}
          </Fragment>
        );
      })}
    </p>
  );
}

function Metric({ name, value }: { name: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/60 px-3.5 py-2.5">
      <dt className="text-[11px] font-medium uppercase tracking-wider text-ink-soft">{name}</dt>
      <dd className="mt-0.5 text-lg font-semibold leading-tight tabular-nums text-ink">{value}</dd>
    </div>
  );
}
