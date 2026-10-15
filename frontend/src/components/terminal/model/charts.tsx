import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART, ChartTooltip, axisProps } from "@/components/terminal/chart";
import { formatDate, formatNumber, formatPct } from "@/lib/format";
import { MetricsPanel } from "./mpanel";

const H = 240;
const margin = { top: 8, right: 12, bottom: 4, left: 0 };

export function ReliabilityCurve() {
  return (
    <MetricsPanel
      title="Reliability curve"
      info="Predicted confidence vs observed frequency per bin. Points on the dashed diagonal are perfectly calibrated."
      className="lg:col-span-5"
      isEmpty={(m) => m.calibration.bins.length === 0}
      emptyTitle="No calibration bins"
    >
      {(m) => (
        <div style={{ height: H }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={m.calibration.bins} margin={margin}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis
                dataKey="predicted"
                type="number"
                domain={[0, 1]}
                tickFormatter={(v: number) => formatPct(v, 0)}
                {...axisProps}
              />
              <YAxis
                type="number"
                domain={[0, 1]}
                tickFormatter={(v: number) => formatPct(v, 0)}
                width={40}
                {...axisProps}
              />
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: 1, y: 1 },
                ]}
                stroke={CHART.secondary}
                strokeDasharray="4 3"
              />
              <Tooltip
                content={
                  <ChartTooltip
                    labelFormatter={(l) => `Predicted ${formatPct(Number(l), 1)}`}
                    valueFormatter={(v) => formatPct(v, 1)}
                  />
                }
              />
              <Line
                name="Observed"
                dataKey="observed"
                stroke={CHART.primary}
                strokeWidth={1.75}
                dot={{ r: 3, fill: CHART.primary }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className="num mt-1 text-[10px] text-muted-foreground">
            bin n: {m.calibration.bins.map((b) => b.n).join(" · ")}
          </p>
        </div>
      )}
    </MetricsPanel>
  );
}

export function BacktestChart() {
  return (
    <MetricsPanel
      title="Backtest: signal quintile vs forward return"
      info="Signals ranked into quintiles by score; bars show the mean realised forward return of each quintile. A monotonic slope means the score is informative."
      className="lg:col-span-6"
      isEmpty={(m) => m.backtest.quintiles.length === 0}
      emptyTitle="No backtest quintiles"
    >
      {(m) => (
        <div style={{ height: H }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={m.backtest.quintiles} margin={margin}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="quintile" tickFormatter={(v: number) => `Q${v}`} {...axisProps} />
              <YAxis tickFormatter={(v: number) => formatPct(v, 1)} width={48} {...axisProps} />
              <ReferenceLine y={0} stroke={CHART.axis} />
              <Tooltip
                content={
                  <ChartTooltip
                    labelFormatter={(l) => {
                      const q = m.backtest.quintiles.find((x) => x.quintile === Number(l));
                      return `Quintile ${l}${q ? ` (n=${formatNumber(q.n, { maximumFractionDigits: 0 })})` : ""}`;
                    }}
                    valueFormatter={(v) => formatPct(v, 2, true)}
                  />
                }
              />
              <Bar name="Mean forward return" dataKey="meanForwardReturn" isAnimationActive={false}>
                {m.backtest.quintiles.map((q) => (
                  <Cell
                    key={q.quintile}
                    fill={q.meanForwardReturn < 0 ? CHART.primary : CHART.positive}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </MetricsPanel>
  );
}

export function DriftMonitor() {
  return (
    <MetricsPanel
      title="Drift monitor (PSI)"
      info="Population Stability Index of the input distribution over time. Values above the threshold indicate material drift and may require retraining."
      className="lg:col-span-6"
      isEmpty={(m) => m.drift.series.length === 0}
      emptyTitle="No drift series"
    >
      {(m) => {
        const th = m.drift.threshold;
        return (
          <div style={{ height: H }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={m.drift.series} margin={margin}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis
                  dataKey="ts"
                  tickFormatter={(v: string) => formatDate(v)}
                  minTickGap={32}
                  {...axisProps}
                />
                <YAxis
                  width={40}
                  domain={[0, (max: number) => Math.max(max, th * 1.2)]}
                  tickFormatter={(v: number) => v.toFixed(2)}
                  {...axisProps}
                />
                <ReferenceLine
                  y={th}
                  stroke={CHART.primary}
                  strokeDasharray="4 3"
                  label={{
                    value: "threshold",
                    fill: "oklch(0.51 0.008 285)",
                    fontSize: 10,
                    position: "insideTopRight",
                  }}
                />
                <Tooltip
                  content={
                    <ChartTooltip
                      labelFormatter={(l) => formatDate(String(l))}
                      valueFormatter={(v) => v.toFixed(3)}
                    />
                  }
                />
                <Line
                  name="PSI"
                  dataKey="psi"
                  stroke={CHART.ink}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  dot={(p: {
                    cx?: number;
                    cy?: number;
                    payload?: { psi: number };
                    index?: number;
                  }) => {
                    const over = (p.payload?.psi ?? 0) > th;
                    return (
                      <circle
                        key={p.index}
                        cx={p.cx}
                        cy={p.cy}
                        r={over ? 3.5 : 2}
                        fill={over ? CHART.primary : CHART.ink}
                      />
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      }}
    </MetricsPanel>
  );
}

export function LatencyHistogram() {
  return (
    <MetricsPanel
      title="Inference latency"
      info="Distribution of end-to-end scoring latency per item. p50 is the median, p95 the slow tail."
      className="lg:col-span-12"
      isEmpty={(m) => m.latency.histogram.length === 0}
      emptyTitle="No latency histogram"
    >
      {(m) => (
        <div style={{ height: H }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={m.latency.histogram} margin={margin}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="bucketMs" tickFormatter={(v: number) => `${v}ms`} {...axisProps} />
              <YAxis width={40} allowDecimals={false} {...axisProps} />
              <Tooltip
                content={
                  <ChartTooltip
                    labelFormatter={(l) => `${l} ms bucket`}
                    valueFormatter={(v) => formatNumber(v, { maximumFractionDigits: 0 })}
                  />
                }
              />
              <Bar name="Count" dataKey="count" fill={CHART.primary} isAnimationActive={false} />
              {m.latency.p50Ms != null && (
                <ReferenceLine
                  x={nearest(
                    m.latency.histogram.map((h) => h.bucketMs),
                    m.latency.p50Ms,
                  )}
                  stroke={CHART.ink}
                  strokeDasharray="4 3"
                  label={{
                    value: `p50 ${Math.round(m.latency.p50Ms)} ms`,
                    fontSize: 10,
                    fill: "oklch(0.51 0.008 285)",
                    position: "top",
                  }}
                />
              )}
              {m.latency.p95Ms != null && (
                <ReferenceLine
                  x={nearest(
                    m.latency.histogram.map((h) => h.bucketMs),
                    m.latency.p95Ms,
                  )}
                  stroke={CHART.ink}
                  strokeDasharray="4 3"
                  label={{
                    value: `p95 ${Math.round(m.latency.p95Ms)} ms`,
                    fontSize: 10,
                    fill: "oklch(0.51 0.008 285)",
                    position: "top",
                  }}
                />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </MetricsPanel>
  );
}

/** Category axis: snap a value to the bucket that contains it (largest bucket start <= value). */
function nearest(buckets: number[], v: number): number {
  let best = buckets[0] ?? v;
  for (const b of buckets) if (b <= v) best = b;
  return best;
}
