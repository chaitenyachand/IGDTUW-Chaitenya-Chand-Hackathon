import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { StressResult } from "@/api/types";
import { formatCurrency } from "@/lib/format";
import { CHART, ChartTooltip, axisProps } from "@/components/terminal/chart";

export function AssetClassChart({ r }: { r: StressResult }) {
  return (
    <div
      className="h-56 w-full"
      role="img"
      aria-label="Value by asset class before versus after the shock"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={r.byAssetClass} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="assetClass" {...axisProps} />
          <YAxis {...axisProps} width={52} tickFormatter={(v: number) => formatCurrency(v)} />
          <Tooltip
            cursor={{ fill: "transparent" }}
            content={<ChartTooltip valueFormatter={(v) => formatCurrency(v)} />}
          />
          <Legend iconType="circle" iconSize={6} wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="before" name="Before" fill={CHART.secondary} animationDuration={700} />
          <Bar dataKey="after" name="After" fill={CHART.primary} animationDuration={700} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Top 8 by absolute delta; crimson negative, positive colour for gains. */
export function DeltaBars({
  rows,
  label,
}: {
  rows: { name: string; delta: number }[];
  label: string;
}) {
  const top = [...rows].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 8);
  return (
    <div
      className="w-full"
      style={{ height: Math.max(80, top.length * 26 + 24) }}
      role="img"
      aria-label={label}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={top} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={(v: number) => formatCurrency(v)} />
          <YAxis type="category" dataKey="name" {...axisProps} width={84} interval={0} />
          <Tooltip
            cursor={{ fill: "transparent" }}
            content={<ChartTooltip valueFormatter={(v) => formatCurrency(v)} />}
          />
          <Bar dataKey="delta" name="Delta" animationDuration={700}>
            {top.map((x) => (
              <Cell key={x.name} fill={x.delta < 0 ? CHART.primary : CHART.positive} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
