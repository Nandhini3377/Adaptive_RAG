"use client";

import { useParams, useRouter } from "next/navigation";
import { type ReactNode, useCallback, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { ApiError, api } from "@/lib/api";
import { STRATEGY_LABELS, inr, label, num, pct } from "@/lib/format";
import type { AnalysisOut, DocumentOut, Intent } from "@/lib/types";

import { StatusBadge } from "./StatusBadge";
import { Badge, Button, Card, ErrorBox, PageHeader, ProgressBar, Stat } from "./ui";

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

  if (!document) return <p className="text-sm text-ink-soft">{error ?? "Loading…"}</p>;
  const profile = analysis?.profile;

  return (
    <>
      <PageHeader
        title={document.filename}
        subtitle={`${document.file_type.toUpperCase()} · uploaded ${new Date(document.created_at).toLocaleString()}`}
        action={
          <div className="flex gap-2">
            {document.status === "ready" && (
              <Button variant="secondary" onClick={() => router.push(`/chat?doc=${document.id}`)}>
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
              Delete
            </Button>
          </div>
        }
      />
      <ErrorBox message={error} />

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Status" action={<StatusBadge status={document.status} />}>
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
          </Card>

          {document.status === "awaiting_intent" && analysis && chosen && (
            <Card title="What will you mostly ask about this document?">
              <p className="mb-3 text-sm text-ink-soft">
                Pre-selected from the scan. This decides how the document is indexed.
              </p>
              <div className="space-y-2">
                {analysis.intent_options.map((option) => (
                  <label key={option.id} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2.5 text-sm">
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
              <div className="mt-4 flex gap-2">
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
              <p className="text-sm leading-relaxed text-ink">{analysis.reason}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Stat label="Confidence" value={pct(analysis.confidence)} />
                <Stat
                  label="Your intents"
                  value={analysis.user_intents?.length ? analysis.user_intents.length : "Skipped"}
                />
              </div>
            </Card>
          )}

          {profile && (
            <Card title="Quick scan (no LLM, whole document)">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
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
            <Card title={`LLM sample (${profile.sampled_section_ids.length} sections, not the whole document)`}>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Relationships per entity" value={num(profile.relationship_density)} />
                <Stat label="Entities in 3+ sections" value={pct(profile.entity_repetition)} />
                <Stat label="Tokens used" value={profile.analysis_tokens.toLocaleString()} />
                <Stat label="Cost" value={inr(profile.analysis_cost_inr)} />
              </div>
              {profile.sample_entities.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {profile.sample_entities.slice(0, 30).map((entity) => (
                    <Badge key={entity}>{entity}</Badge>
                  ))}
                </div>
              )}
              {profile.sample_relationships.length > 0 && (
                <ul className="mt-3 space-y-1 font-mono text-xs text-ink-soft">
                  {profile.sample_relationships.slice(0, 12).map((relation) => (
                    <li key={relation}>{relation}</li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Indexes">
            <ul className="space-y-3 text-sm">
              <IndexRow name="Vector search" built={document.status === "ready"} />
              <IndexRow
                name="Keyword search (BM25)"
                built={document.has_bm25}
                action={
                  document.status === "ready" && !document.has_bm25 ? (
                    <Button variant="secondary" disabled={busy} onClick={() => act(() => api.buildIndex(id, "bm25"))}>
                      Build
                    </Button>
                  ) : null
                }
              />
              <IndexRow
                name="Knowledge graph"
                built={document.graph_status === "ready"}
                note={document.graph_status === "candidate" ? "Recommended for this document" : undefined}
                action={
                  document.status === "ready" && document.graph_status !== "ready" ? (
                    <Button variant="secondary" disabled={busy} onClick={() => act(() => api.buildIndex(id, "graph"))}>
                      Build
                    </Button>
                  ) : null
                }
              />
            </ul>
            <p className="mt-4 text-xs text-ink-soft">
              Questions only use indexes that exist. When a missing index would help, the answer
              recommends building it.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}

function IndexRow({
  name,
  built,
  note,
  action,
}: {
  name: string;
  built: boolean;
  note?: string;
  action?: ReactNode;
}) {
  return (
    <li className="flex items-center gap-3">
      <span className={`h-2 w-2 shrink-0 rounded-full ${built ? "bg-good" : "bg-line"}`} />
      <div className="flex-1">
        <div className="text-ink">{name}</div>
        <div className="text-xs text-ink-soft">{built ? "Built" : (note ?? "Not built")}</div>
      </div>
      {action}
    </li>
  );
}
