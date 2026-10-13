"use client";

import { useParams, useRouter } from "next/navigation";
import { type ReactNode, useCallback, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { ApiError, api } from "@/lib/api";
import { INTENT_LABELS, STRATEGY_LABELS, dateTime, inr, label, num, pct } from "@/lib/format";
import type { AnalysisOut, DocumentOut, DocumentStatus, Intent } from "@/lib/types";

import { ChatIcon, CheckIcon, GraphIcon, HashIcon, LayersIcon, TrashIcon } from "./icons";
import { StatusBadge } from "./StatusBadge";
import { Badge, Button, Card, ErrorBox, Loading, PageHeader, ProgressBar, Ring, SectionLabel, Stat } from "./ui";

const BUSY = new Set(["scanning", "indexing"]);

export function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisOut | null>(null);
  const [chosen, setChosen] = useState<Intent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const doc = await api.getDocument(id);
      setDocument(doc);
      if (doc.status !== "scanning") {
        const result = await api.getAnalysis(id);
        setAnalysis(result);
        setChosen((current) => current ?? result.suggested_intents);
      }
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 409)) {
        setError(err instanceof Error ? err.message : "Could not load the document");
      }
    }
  }, [id]);

  useOnMount(load);
  usePolling(load, 2000, !!document && BUSY.has(document.status));

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (!document) return error ? <ErrorBox message={error} /> : <Loading />;
  const profile = analysis?.profile;

  return (
    <>
      <PageHeader
        back={{ href: "/", label: "Documents" }}
        title={document.filename}
        subtitle={`${document.file_type.toUpperCase()} · uploaded ${dateTime(document.created_at)}`}
        action={
          <div className="flex gap-2">
            {document.status === "ready" && (
              <Button onClick={() => router.push(`/chat?doc=${document.id}`)}>
                <ChatIcon />
                Ask about it
              </Button>
            )}
            <Button
              variant="danger"
              disabled={busy}
              onClick={async () => {
                if (!confirm(`Delete ${document.filename} and all its indexes?`)) return;
                setBusy(true);
                try {
                  await api.deleteDocument(document.id);
                  router.push("/");
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Delete failed");
                  setBusy(false);
                }
              }}
            >
              <TrashIcon />
              Delete
            </Button>
          </div>
        }
      />
      <ErrorBox message={error} className="mb-4" />

      <div className="grid items-start gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card title="Progress" action={<StatusBadge status={document.status} />}>
            <Stepper status={document.status} />
            <div className="mt-5 border-t border-line/70 pt-4">
              {BUSY.has(document.status) ? (
                <div className="space-y-2">
                  <ProgressBar value={document.progress} />
                  <p className="text-sm text-ink-soft">{document.stage}…</p>
                </div>
              ) : document.status === "failed" ? (
                <p className="text-sm text-danger">{document.error}</p>
              ) : (
                <p className="text-sm text-ink-soft">{document.stage}</p>
              )}
            </div>
          </Card>

          {document.status === "awaiting_intent" && analysis && chosen && (
            <Card title="What will you mostly ask about this document?">
              <p className="mb-4 text-sm text-ink-soft">
                Pre-selected from the scan. This decides how the document is indexed.
              </p>
              <div className="space-y-2">
                {analysis.intent_options.map((option) => (
                  <label
                    key={option.id}
                    className="flex cursor-pointer items-center gap-3 rounded-xl border border-line px-4 py-3 text-sm transition-colors hover:bg-muted/60 has-[:checked]:border-accent/60 has-[:checked]:bg-accent/5"
                  >
                    <input
                      type="checkbox"
                      checked={chosen.includes(option.id)}
                      onChange={(e) =>
                        setChosen(
                          e.target.checked ? [...chosen, option.id] : chosen.filter((c) => c !== option.id),
                        )
                      }
                    />
                    <span className="flex-1 text-ink">{option.label}</span>
                    {option.suggested && <Badge tone="accent">suggested</Badge>}
                  </label>
                ))}
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button disabled={busy || chosen.length === 0} onClick={() => act(() => api.setIntent(id, chosen))}>
                  Continue
                </Button>
                <Button variant="secondary" disabled={busy} onClick={() => act(() => api.setIntent(id, [], true))}>
                  Skip: let the scan decide
                </Button>
              </div>
            </Card>
          )}

          {analysis?.strategy && (
            <Card
              title="Decision"
              action={<Badge tone="accent">{label(STRATEGY_LABELS, analysis.strategy)}</Badge>}
            >
              <div className="flex items-center gap-5">
                <div className="flex shrink-0 flex-col items-center gap-1.5">
                  <Ring value={analysis.confidence} size={76} />
                  <span className="text-xs text-ink-soft">Confidence</span>
                </div>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed text-ink">{analysis.reason}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-ink-soft">Your intents</span>
                    {analysis.user_intents?.length ? (
                      analysis.user_intents.map((intent) => <Badge key={intent}>{INTENT_LABELS[intent]}</Badge>)
                    ) : (
                      <Badge>Skipped</Badge>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {profile && (
            <Card title="Quick scan" action={<span className="text-xs text-ink-soft">No LLM · whole document</span>}>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Pages" value={profile.page_count} />
                <Stat label="Sections" value={profile.section_count} />
                <Stat label="Tables" value={profile.table_count} />
                <Stat label="Words" value={profile.word_count.toLocaleString()} />
                <Stat label="Cross-refs / 1k words" value={num(profile.cross_ref_rate, 1)} />
                <Stat label="Relation phrases / 1k" value={num(profile.relationship_phrase_rate, 1)} />
                <Stat label="IDs / 1k words" value={num(profile.identifier_density, 1)} />
                <Stat label="Text in tables" value={pct(profile.table_share)} />
              </div>
            </Card>
          )}

          {profile && profile.sampled_section_ids.length > 0 && (
            <Card
              title="LLM sample"
              action={
                <span className="text-xs text-ink-soft">
                  {profile.sampled_section_ids.length} sections · not the whole document
                </span>
              }
            >
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Relationships per entity" value={num(profile.relationship_density)} />
                <Stat label="Entities in 3+ sections" value={pct(profile.entity_repetition)} />
                <Stat label="Tokens used" value={profile.analysis_tokens.toLocaleString()} />
                <Stat label="Cost" value={inr(profile.analysis_cost_inr)} />
              </div>
              {profile.sample_entities.length > 0 && (
                <div className="mt-5">
                  <SectionLabel>Entities found</SectionLabel>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.sample_entities.slice(0, 30).map((entity) => (
                      <Badge key={entity}>{entity}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {profile.sample_relationships.length > 0 && (
                <div className="mt-5">
                  <SectionLabel>Relationships found</SectionLabel>
                  <ul className="space-y-1 rounded-xl bg-muted px-4 py-3 font-mono text-xs leading-relaxed text-ink-soft">
                    {profile.sample_relationships.slice(0, 12).map((relation) => (
                      <li key={relation}>{relation}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-5">
          <Card title="Indexes">
            <ul className="divide-y divide-line/70 text-sm">
              <IndexRow
                icon={<LayersIcon width={18} height={18} />}
                name="Vector search"
                about="Finds passages by meaning"
                built={document.status === "ready"}
              />
              <IndexRow
                icon={<HashIcon width={18} height={18} />}
                name="Keyword search (BM25)"
                about="Matches exact terms and codes"
                built={document.has_bm25}
                action={
                  document.status === "ready" && !document.has_bm25 ? (
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => act(() => api.buildIndex(id, "bm25"))}>
                      Build
                    </Button>
                  ) : null
                }
              />
              <IndexRow
                icon={<GraphIcon width={18} height={18} />}
                name="Knowledge graph"
                about="Follows how things connect"
                built={document.graph_status === "ready"}
                note={
                  document.graph_status === "candidate"
                    ? "Recommended for this document"
                    : document.graph_status === "building"
                      ? "Building…"
                      : undefined
                }
                action={
                  document.status === "ready" && document.graph_status !== "ready" ? (
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => act(() => api.buildIndex(id, "graph"))}>
                      Build
                    </Button>
                  ) : null
                }
              />
            </ul>
            <p className="mt-5 border-t border-line pt-4 text-xs leading-relaxed text-ink-soft">
              Questions only use indexes that exist. When a missing index would help, the answer
              recommends building it.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}

const STEPS = ["Scan", "Your intent", "Index", "Ready"];
// The step a document is on; "ready" is past the last one, so every step shows as done
const CURRENT_STEP: Record<DocumentStatus, number> = {
  scanning: 0,
  awaiting_intent: 1,
  indexing: 2,
  ready: STEPS.length,
  failed: -1,
};

/** The upload pipeline as numbered steps, with the current one highlighted. */
function Stepper({ status }: { status: DocumentStatus }) {
  const current = CURRENT_STEP[status];
  return (
    <ol className="flex items-center">
      {STEPS.map((step, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={step} className={`flex items-center ${index < STEPS.length - 1 ? "flex-1" : ""}`}>
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                done
                  ? "bg-accent text-on-accent"
                  : active
                    ? "bg-accent/12 text-accent ring-2 ring-accent/40"
                    : "bg-muted text-ink-soft"
              }`}
            >
              {done ? <CheckIcon width={14} height={14} strokeWidth={3} /> : index + 1}
            </span>
            <span
              className={`ml-2.5 hidden text-sm sm:inline ${done || active ? "font-medium text-ink" : "text-ink-soft"}`}
            >
              {step}
            </span>
            {index < STEPS.length - 1 && (
              <span className={`mx-3 h-0.5 flex-1 rounded-full ${done ? "bg-accent" : "bg-line"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function IndexRow({
  icon,
  name,
  about,
  built,
  note,
  action,
}: {
  icon: ReactNode;
  name: string;
  about: string;
  built: boolean;
  note?: string;
  action?: ReactNode;
}) {
  return (
    <li className="flex items-center gap-3.5 py-3.5 first:pt-0 last:pb-0">
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
          built ? "bg-good/12 text-good" : "bg-muted text-ink-soft"
        }`}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-ink">{name}</div>
        <div className="text-xs text-ink-soft">{about}</div>
        <div className={`mt-0.5 text-xs font-medium ${built ? "text-good" : note ? "text-warn" : "text-ink-soft"}`}>
          {built ? "Built" : (note ?? "Not built")}
        </div>
      </div>
      {action}
    </li>
  );
}
