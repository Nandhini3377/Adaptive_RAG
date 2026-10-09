"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useCallback, useRef, useState } from "react";

import { useOnMount, usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { STRATEGY_LABELS, label } from "@/lib/format";
import type { DocumentOut } from "@/lib/types";

import { StatusBadge } from "./StatusBadge";
import { Badge, Button, Card, ErrorBox, PageHeader, ProgressBar } from "./ui";

const ACCEPT = ".pdf,.docx,.html,.htm,.md,.markdown,.txt";
const BUSY = new Set(["scanning", "indexing"]);

export function DocumentsView() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
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

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
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

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Each upload is scanned cheaply, then indexed with the strategy that fits it."
        action={
          <>
            <input ref={input} type="file" accept={ACCEPT} onChange={onFile} className="hidden" />
            <Button onClick={() => input.current?.click()} disabled={uploading}>
              {uploading ? "Uploading…" : "Upload document"}
            </Button>
          </>
        }
      />
      <ErrorBox message={error} />
      {documents === null ? (
        <p className="text-sm text-ink-soft">Loading…</p>
      ) : documents.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-soft">
            No documents yet. Upload a PDF, Word, HTML, Markdown, or text file (up to 50 MB).
          </p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {documents.map((doc) => (
            <li key={doc.id}>
              <Link
                href={`/documents/${doc.id}`}
                className="block rounded-xl border border-line bg-surface p-4 transition hover:border-accent/50"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-medium text-ink">{doc.filename}</span>
                  <StatusBadge status={doc.status} />
                  {doc.strategy && <Badge tone="accent">{label(STRATEGY_LABELS, doc.strategy)}</Badge>}
                  {doc.graph_status === "candidate" && <Badge tone="warn">Graph recommended</Badge>}
                  <span className="ml-auto text-xs text-ink-soft">
                    {new Date(doc.created_at).toLocaleString()}
                  </span>
                </div>
                {BUSY.has(doc.status) && (
                  <div className="mt-3 space-y-1">
                    <ProgressBar value={doc.progress} />
                    <p className="text-xs text-ink-soft">{doc.stage}</p>
                  </div>
                )}
                {doc.status === "awaiting_intent" && (
                  <p className="mt-2 text-sm text-warn">Tell us what you&apos;ll ask about it →</p>
                )}
                {doc.status === "failed" && <p className="mt-2 text-sm text-danger">{doc.error}</p>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
