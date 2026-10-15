import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useIndexPerformance } from "@/api/client";
import type { PerfStats, PerformanceResponse } from "@/api/types";
import { CHART, ChartTooltip, axisProps } from "@/components/terminal/chart";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { InfoTip } from "@/components/terminal/kit";
import { formatNumber, formatPct } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import { fmtStamp } from "./util";

const ROWS: { label: string; info: string; get: (s: PerfStats) => string }[] = [
  {
    label: "Total return",
    info: "Cumulative return over the series.",
    get: (s) => formatPct(s.totalReturn, 2, true),
  },
  {
    label: "Tracking error",
    info: "Volatility of the return difference versus the benchmark.",
    get: (s) => formatPct(s.trackingError, 2),
  },
  {
    label: "Turnover",
    info: "Share of the index traded. A naive rebalancer churns more on noisy sentiment (whipsaw).",
    get: (s) => formatPct(s.turnover, 1),
  },
  {
    label: "Max drawdown",
    info: "Largest peak-to-trough decline.",
    get: (s) => formatPct(s.maxDrawdown, 2),
  },
  {
    label: "Information ratio",
    info: "Excess return over the benchmark per unit of tracking error. Blank when not defined.",
    get: (s) => formatNumber(s.informationRatio, { minimumFractionDigits: 2 }),
  },
];

function Inner({ data }: { data: PerformanceResponse }) {
  const { tz } = useSettings();
  const cols = [
    { key: "tilted", name: "Sentiment-tilted", stats: data.stats.tilted, color: CHART.primary },
    { key: "naive", name: "Naive rebalancer", stats: data.stats.naive, color: CHART.axis },
    {
      key: "benchmark",
      name: "Static benchmark",
      stats: data.stats.benchmark,
      color: CHART.secondary,
    },
  ] as const;
  return (
    <div className="space-y-3">
      <div
        className="h-56 w-full"
        role="img"
        aria-label="Line chart of tilted index, naive rebalancer and benchmark"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data.series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--hairline)" vertical={false} />
            <XAxis
              dataKey="ts"
              {...axisProps}
              minTickGap={48}
              tickFormatter={(v: string) => fmtStamp(v, tz)}
            />
            <YAxis
              {...axisProps}
              width={44}
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => formatNumber(v, { maximumFractionDigits: 1 })}
            />
            <Tooltip
              isAnimationActive={false}
              content={
                <ChartTooltip
                  labelFormatter={(l) => fmtStamp(String(l), tz)}
                  valueFormatter={(v) => formatNumber(v, { minimumFractionDigits: 2 })}
                />
              }
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              name="Static benchmark"
              stroke={CHART.secondary}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="naive"
              name="Naive rebalancer"
              stroke={CHART.axis}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="tilted"
              name="Sentiment-tilted"
              stroke={CHART.primary}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div data-lenis-prevent className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-[12px]">
          <thead>
            <tr className="border-b border-hairline text-left text-[11px] uppercase tracking-label text-muted-foreground">
              <th className="py-1 pr-2 font-medium">Metric</th>
              {cols.map((c) => (
                <th key={c.key} className="py-1 pl-2 text-right font-medium">
                  <span className="inline-flex items-center gap-1">
                    <span className="inline-block h-0.5 w-3" style={{ background: c.color }} />
                    {c.name}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.label} className="border-b border-hairline last:border-b-0">
                <td className="py-1 pr-2 text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    {r.label}
                    <InfoTip text={r.info} />
                  </span>
                </td>
                {cols.map((c) => (
                  <td key={c.key} className="num py-1 pl-2 text-right text-foreground">
                    {r.get(c.stats)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PerformancePanel() {
  const q = useIndexPerformance();
  return (
    <Panel
      title="Performance: tilted vs naive vs benchmark"
      info="Compares the sentiment-tilted index with a naive rebalancer that reacts to every sentiment move and the static benchmark. Lower turnover and drawdown for the tilted line show whipsaw reduction."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/index/performance"
        skeleton={<SkeletonBlock className="h-72" />}
        isEmpty={(e) => e.data.series.length === 0}
        emptyTitle="No performance data"
      >
        {(env) => <Inner data={env.data} />}
      </QueryBoundary>
    </Panel>
  );
}
