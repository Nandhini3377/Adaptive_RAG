"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MODE_LABELS, label } from "@/lib/format";

// One fixed colour per mode, so a mode looks the same in every chart (never by rank).
export const MODE_COLORS: Record<string, string> = {
  vector: "var(--series-1)",
  hybrid: "var(--series-2)",
  graph: "var(--series-3)",
  graph_hybrid: "var(--series-4)",
  router: "var(--series-5)",
};

export interface GroupRow {
  group: string;
  [mode: string]: number | string;
}

/** Grouped bars: one group per x value, one bar per mode. Single y axis, hover tooltip. */
export function ModeBarChart({
  rows,
  modes,
  format,
  domain,
}: {
  rows: GroupRow[];
  modes: string[];
  format: (value: number) => string;
  domain?: [number, number];
}) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} barGap={2} barCategoryGap="22%" margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis
            dataKey="group"
            tickLine={false}
            axisLine={{ stroke: "var(--line)" }}
            tick={{ fill: "var(--ink-soft)", fontSize: 12 }}
          />
          <YAxis
            domain={domain}
            tickFormatter={format}
            tickLine={false}
            axisLine={false}
            width={52}
            tick={{ fill: "var(--ink-soft)", fontSize: 12 }}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            content={({ active, payload, label: group }) =>
              active && payload?.length ? (
                <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-sm">
                  <div className="mb-1 font-medium text-ink">{group}</div>
                  {payload.map((item) => (
                    <div key={String(item.dataKey)} className="flex items-center gap-2 text-ink-soft">
                      <span className="h-2 w-2 rounded-sm" style={{ background: item.color }} />
                      <span>{label(MODE_LABELS, String(item.dataKey))}</span>
                      <span className="ml-auto pl-3 tabular-nums text-ink">{format(Number(item.value))}</span>
                    </div>
                  ))}
                </div>
              ) : null
            }
          />
          <Legend
            iconType="square"
            iconSize={10}
            formatter={(value: string) => <span className="text-xs text-ink-soft">{label(MODE_LABELS, value)}</span>}
          />
          {modes.map((mode) => (
            <Bar
              key={mode}
              dataKey={mode}
              fill={MODE_COLORS[mode]}
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
