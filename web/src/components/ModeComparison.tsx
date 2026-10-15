import { MODE_COMPARE_LABELS, label, num } from "@/lib/format";
import type { Mode, ModeQuality } from "@/lib/types";

import { Badge } from "./ui";

/**
 * Precision and recall of each search mode on one question, against the same judged pool.
 * The bar shows recall (or precision when recall is not measured).
 */
export function ModeComparison({
  modes,
  usedLabel = "used",
  best = [],
}: {
  modes: ModeQuality[];
  usedLabel?: string;
  best?: Mode[];
}) {
  return (
    <div role="table" aria-label="Precision and recall per search mode" className="text-sm">
      <div role="row" className="grid grid-cols-[minmax(0,1fr)_4.25rem_4.25rem] gap-x-3 pb-1.5 text-xs text-ink-soft">
        <span role="columnheader">Mode</span>
        <span role="columnheader" className="text-right">
          Precision
        </span>
        <span role="columnheader" className="text-right">
          Recall
        </span>
      </div>
      {modes.map((m) => {
        const bar = m.recall ?? m.precision ?? 0;
        return (
          <div
            role="row"
            key={m.mode}
            className="grid grid-cols-[minmax(0,1fr)_4.25rem_4.25rem] items-center gap-x-3 border-t border-line/60 py-2.5"
          >
            <div role="cell" className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className={`break-words ${m.used ? "font-medium text-ink" : "text-ink-soft"}`}>
                  {label(MODE_COMPARE_LABELS, m.mode)}
                </span>
                {m.used && <Badge tone="accent">{usedLabel}</Badge>}
                {best.includes(m.mode) && <Badge tone="good">best</Badge>}
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full ${m.used ? "bg-accent" : "bg-ink-soft/40"}`}
                  style={{ width: `${Math.min(Math.max(bar, 0), 1) * 100}%` }}
                />
              </div>
              <div className="mt-1 text-xs text-ink-soft">
                {m.found === 0 ? "found nothing" : `${m.relevant} of ${m.found} chunks relevant`}
              </div>
            </div>
            <span role="cell" className="text-right tabular-nums text-ink">
              {num(m.precision)}
            </span>
            <span role="cell" className="text-right tabular-nums text-ink">
              {num(m.recall)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
