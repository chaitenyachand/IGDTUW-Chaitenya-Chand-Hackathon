import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { Holding } from "@/api/types";
import { ChartTooltip } from "@/components/terminal/chart";
import { EmptyState } from "@/components/terminal/kit";
import { formatCurrency, formatPct } from "@/lib/format";

const COLORS: Record<string, string> = {
  Loan: "oklch(0.55 0.217 20)",
  Bond: "oklch(0.42 0.012 285)",
  Derivative: "oklch(0.74 0.008 285)",
};
const FALLBACK = ["oklch(0.65 0.15 20)", "oklch(0.58 0.01 285)", "oklch(0.82 0.006 285)"];

export function AssetDonut({ rows }: { rows: Holding[] }) {
  const { slices, total } = useMemo(() => {
    const m = new Map<string, number>();
    for (const h of rows) m.set(h.assetType, (m.get(h.assetType) ?? 0) + h.marketValue);
    const s = [...m.entries()]
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
    return { slices: s, total: s.reduce((a, b) => a + b.value, 0) };
  }, [rows]);
  if (slices.length === 0 || total <= 0)
    return <EmptyState title="Nothing to chart" hint="No holdings match the current filters." />;
  return (
    <div className="space-y-2">
      <div
        className="relative h-48"
        role="img"
        aria-label="Donut chart of market value by asset class"
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="90%"
              paddingAngle={1}
              stroke="var(--paper)"
              isAnimationActive={false}
            >
              {slices.map((s, i) => (
                <Cell key={s.name} fill={COLORS[s.name] ?? FALLBACK[i % FALLBACK.length]} />
              ))}
            </Pie>
            <Tooltip
              content={
                <ChartTooltip
                  valueFormatter={(v) => `${formatCurrency(v)} (${formatPct(v / total, 1)})`}
                />
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[11px] uppercase tracking-label text-muted-foreground">
            Market value
          </span>
          <span className="num text-[18px] text-foreground">{formatCurrency(total)}</span>
        </div>
      </div>
      <ul className="space-y-1">
        {slices.map((s, i) => (
          <li key={s.name} className="flex items-center justify-between text-[12px]">
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block size-2 rounded-sm"
                style={{ background: COLORS[s.name] ?? FALLBACK[i % FALLBACK.length] }}
              />
              {s.name}
            </span>
            <span className="num text-muted-foreground">
              {formatCurrency(s.value)} · {formatPct(s.value / total, 1)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
