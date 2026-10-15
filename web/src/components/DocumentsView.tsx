"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ChangeEvent, type DragEvent, useCallback, useRef, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { STRATEGY_LABELS, dateTime, label } from "@/lib/format";
import type { DocumentOut } from "@/lib/types";

import { AlertIcon, CheckIcon, FileIcon, GraphIcon, SearchIcon, SparkIcon, UploadIcon } from "./icons";
import { StatusBadge } from "./StatusBadge";
import { Button, ErrorBox, Loading, MetricTile, PageHeader, ProgressBar } from "./ui";

const ACCEPT = ".pdf,.docx,.html,.htm,.md,.markdown,.txt";
const BUSY = new Set(["scanning", "indexing"]);

const FILTERS: { id: string; name: string; match: (doc: DocumentOut) => boolean }[] = [
  { id: "all", name: "All", match: () => true },
  { id: "ready", name: "Ready", match: (doc) => doc.status === "ready" },
  { id: "busy", name: "In progress", match: (doc) => BUSY.has(doc.status) },
  { id: "input", name: "Needs input", match: (doc) => doc.status === "awaiting_intent" },
  { id: "failed", name: "Failed", match: (doc) => doc.status === "failed" },
];

export function DocumentsView() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setDocuments(await api.listDocuments());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents");
    }
  }, []);

  useOnMount(load);
  usePolling(load, 2000, !!documents?.some((d) => BUSY.has(d.status)));

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const { document_id } = await api.upload(file);
      router.push(`/documents/${document_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void upload(file);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file && !uploading) void upload(file);
  }

  const count = (id: string) => documents?.filter(FILTERS.find((f) => f.id === id)!.match).length ?? 0;
  const empty = documents?.length === 0;
  const term = search.trim().toLowerCase();
  const shown = documents?.filter(
    (doc) => FILTERS.find((f) => f.id === filter)!.match(doc) && doc.filename.toLowerCase().includes(term),
  );

  return (
    <>
      <input ref={input} type="file" accept={ACCEPT} onChange={onFile} className="hidden" />
      <PageHeader
        title="Documents"
        subtitle="Each upload is scanned cheaply, then indexed with the strategy that fits it."
      />
      <ErrorBox message={error} className="mb-5" />

      {documents === null ? (
        !error && <Loading />
      ) : (
        <div className="space-y-6">
          {!empty && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <MetricTile icon={<FileIcon width={20} height={20} />} label="Documents" value={documents.length} />
              <MetricTile
                icon={<CheckIcon width={20} height={20} />}
                label="Ready to ask"
                value={count("ready")}
                tone="good"
              />
              <MetricTile
                icon={<GraphIcon width={20} height={20} />}
                label="Knowledge graphs built"
                value={documents.filter((d) => d.graph_status === "ready").length}
              />
              <MetricTile
                icon={<AlertIcon width={20} height={20} />}
                label="Need your input"
                value={count("input")}
                tone={count("input") ? "warn" : "neutral"}
              />
            </div>
          )}

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`flex items-center gap-x-5 gap-y-4 rounded-2xl border-2 border-dashed px-6 transition-colors ${
              empty ? "flex-col py-16 text-center" : "flex-col py-6 text-center sm:flex-row sm:text-left"
            } ${dragging ? "border-accent bg-accent/8" : "border-line bg-surface/60"}`}
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
              <UploadIcon width={22} height={22} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold tracking-tight text-ink">
                {dragging ? "Drop to upload" : empty ? "Upload your first document" : "Drop a document here"}
              </p>
              <p className="mt-1 text-sm text-ink-soft">PDF, Word, HTML, Markdown or text · up to 50 MB</p>
            </div>
            <Button onClick={() => input.current?.click()} disabled={uploading}>
              {uploading ? "Uploading…" : "Browse files"}
            </Button>
          </div>

          {!empty && (
            <section>
              <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-3">
                <div className="flex flex-1 flex-wrap gap-1.5">
                  {FILTERS.filter((f) => f.id === "all" || count(f.id) > 0).map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      aria-pressed={filter === f.id}
                      onClick={() => setFilter(f.id)}
                      className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                        filter === f.id
                          ? "bg-ink font-medium text-surface"
                          : "bg-surface text-ink-soft ring-1 ring-inset ring-line hover:text-ink"
                      }`}
                    >
                      {f.name}
                      <span className="ml-1.5 tabular-nums opacity-70">{count(f.id)}</span>
                    </button>
                  ))}
                </div>
                <label className="relative w-full sm:w-64">
                  <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft" />
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by name"
                    aria-label="Search documents by name"
                    className="field pl-10"
                  />
                </label>
              </div>

              {shown?.length === 0 ? (
                <p className="rounded-2xl border border-line/70 bg-surface px-6 py-10 text-center text-sm text-ink-soft">
                  No documents match.
                </p>
              ) : (
                <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {shown?.map((doc) => (
                    <li key={doc.id}>
                      <DocumentCard doc={doc} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      )}
    </>
  );
}

function DocumentCard({ doc }: { doc: DocumentOut }) {
  return (
    <Link
      href={`/documents/${doc.id}`}
      className="group flex h-full flex-col rounded-2xl border border-line/70 bg-surface p-5 shadow-card transition-all hover:-translate-y-0.5 hover:border-accent/40"
    >
      <div className="flex items-start gap-3.5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-[10px] font-semibold uppercase tracking-wide text-accent">
          {doc.file_type.slice(0, 4)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink group-hover:text-accent">{doc.filename}</p>
          <p className="mt-0.5 text-xs text-ink-soft">{dateTime(doc.created_at)}</p>
        </div>
        <StatusBadge status={doc.status} />
      </div>

      <div className="mt-4 flex-1">
        {BUSY.has(doc.status) ? (
          <div className="space-y-1.5">
            <ProgressBar value={doc.progress} />
            <p className="text-xs text-ink-soft">{doc.stage}</p>
          </div>
        ) : doc.status === "awaiting_intent" ? (
          <p className="text-sm text-warn">Tell us what you&apos;ll ask about it to finish indexing.</p>
        ) : doc.status === "failed" ? (
          <p className="line-clamp-2 text-sm text-danger">{doc.error}</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            <IndexChip name="Vector" state={doc.has_vector ? "built" : "none"} />
            <IndexChip name="Keyword" state={doc.has_bm25 ? "built" : "none"} />
            <IndexChip
              name="Graph"
              state={
                doc.graph_status === "ready" ? "built" : doc.graph_status === "none" ? "none" : doc.graph_status
              }
            />
          </div>
        )}
      </div>

      {doc.strategy && (
        <p className="mt-4 flex items-center gap-1.5 border-t border-line/70 pt-3.5 text-xs text-ink-soft">
          <SparkIcon width={14} height={14} className="text-accent" />
          Strategy
          <span className="font-medium text-ink">{label(STRATEGY_LABELS, doc.strategy)}</span>
        </p>
      )}
    </Link>
  );
}

/** Whether one index exists for a document. */
function IndexChip({ name, state }: { name: string; state: "built" | "none" | "candidate" | "building" }) {
  const styles = {
    built: "bg-good/12 text-good",
    none: "bg-muted text-ink-soft",
    candidate: "bg-warn/15 text-warn",
    building: "bg-accent/10 text-accent",
  }[state];
  const suffix = { built: "", none: "", candidate: " recommended", building: " building" }[state];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${styles}`}>
      {state === "built" && <CheckIcon width={12} height={12} strokeWidth={3} />}
      <span className={state === "none" ? "line-through decoration-ink-soft/50" : ""}>{name}</span>
      {suffix}
    </span>
  );
}
