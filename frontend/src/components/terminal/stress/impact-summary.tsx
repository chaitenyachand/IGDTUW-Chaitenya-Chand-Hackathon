import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { StressResult } from "@/api/types";
import { formatCurrency, formatPct } from "@/lib/format";
import { CHART, ChartTooltip, axisProps } from "@/components/terminal/chart";
import { CountUp, Stat } from "@/components/terminal/kit";

const cur = (n: number | null) => formatCurrency(n);

export function BigNumbers({ r }: { r: StressResult }) {
  const delta = r.valueAfter - r.valueBefore;
  const pct = r.valueBefore !== 0 ? delta / r.valueBefore : null;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat
          label="Value before"
          info="Mark-to-market value of the book before the shock."
          value={<CountUp value={r.valueBefore} format={cur} className="text-[28px]" />}
        />
        <Stat
          label="Value after"
          info="Value of the book after applying the shock vector."
          value={<CountUp value={r.valueAfter} format={cur} className="text-[28px]" />}
        />
        <Stat
          label="Delta"
          info="Value after minus value before."
          value={<CountUp value={delta} format={cur} className="text-[28px] text-primary" />}
          sub={<CountUp value={pct} format={(n) => formatPct(n, 2, true)} />}
        />
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-hairline pt-3 sm:grid-cols-4">
        <Stat
          label="VaR before"
          info="Value at Risk: the loss the book is not expected to exceed over the horizon at a given confidence level (for example 95%)."
          value={<CountUp value={r.varBefore} format={cur} />}
        />
        <Stat
          label="VaR after"
          info="Value at Risk after the shock."
          value={<CountUp value={r.varAfter} format={cur} />}
        />
        <Stat
          label="ES before"
          info="Expected Shortfall: the average loss in the tail beyond the VaR threshold. Always at least as large as VaR."
          value={<CountUp value={r.esBefore} format={cur} />}
        />
        <Stat
          label="ES after"
          info="Expected Shortfall after the shock."
          value={<CountUp value={r.esAfter} format={cur} />}
        />
      </div>
    </div>
  );
}

interface Row {
  name: string;
  base: number;
  bar: number;
  label: string;
  fill: string;
  tip: string;
}

export function buildWaterfall(r: StressResult): Row[] {
  const rows: Row[] = [
    {
      name: "Before",
      base: 0,
      bar: r.valueBefore,
      label: formatCurrency(r.valueBefore),
      fill: CHART.secondary,
      tip: formatCurrency(r.valueBefore),
    },
  ];
  let run = r.valueBefore;
  for (const f of r.byFactor) {
    const end = run + f.delta;
    rows.push({
      name: f.factor,
      base: Math.min(run, end),
      bar: Math.abs(f.delta),
      label: formatCurrency(f.delta),
      fill: f.delta < 0 ? CHART.primary : CHART.positive,
      tip: formatCurrency(f.delta),
    });
    run = end;
  }
  rows.push({
    name: "After",
    base: 0,
    bar: r.valueAfter,
    label: formatCurrency(r.valueAfter),
    fill: CHART.ink,
    tip: formatCurrency(r.valueAfter),
  });
  return rows;
}

export function Waterfall({ r }: { r: StressResult }) {
  const rows = buildWaterfall(r);
  const levels = rows.flatMap((x) => [x.base, x.base + x.bar]);
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  const span = hi - lo;
  // Truncated axis so small factor steps stay visible against the large totals.
  const domain: [number, number] =
    span > 0 ? [Math.max(0, lo - span * 0.6), hi + span * 0.12] : [0, hi || 1];
  return (
    <div>
      <div
        className="h-72 w-full"
        role="img"
        aria-label="Waterfall chart of portfolio value before, per risk factor, and after the shock"
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 18, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={CHART.grid} vertical={false} />
            <XAxis dataKey="name" {...axisProps} interval={0} />
            <YAxis
              {...axisProps}
              width={56}
              domain={domain}
              allowDataOverflow
              tickFormatter={(v: number) => formatCurrency(v)}
            />
            <Tooltip
              cursor={{ fill: "transparent" }}
              content={<ChartTooltip valueFormatter={(v) => formatCurrency(v)} />}
            />
            <Bar
              dataKey="base"
              stackId="w"
              fill="transparent"
              isAnimationActive
              animationDuration={700}
              tooltipType="none"
            />
            <Bar dataKey="bar" name="Amount" stackId="w" isAnimationActive animationDuration={700}>
              {rows.map((x) => (
                <Cell key={x.name} fill={x.fill} />
              ))}
              <LabelList
                dataKey="label"
                position="top"
                style={{
                  fontSize: 10,
                  fontFamily: "IBM Plex Mono, monospace",
                  fill: "oklch(0.51 0.008 285)",
                }}
              />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="num mt-1 text-[11px] text-muted-foreground">
        Value axis is truncated to make factor steps legible.
      </p>
    </div>
  );
}
