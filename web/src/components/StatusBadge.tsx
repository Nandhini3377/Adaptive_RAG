import { STATUS_LABELS } from "@/lib/format";
import type { DocumentStatus } from "@/lib/types";

import { Badge } from "./ui";

const TONES = {
  scanning: "accent",
  awaiting_intent: "warn",
  indexing: "accent",
  ready: "good",
  failed: "bad",
} as const;

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <Badge tone={TONES[status]} dot>{STATUS_LABELS[status]}</Badge>;
}
