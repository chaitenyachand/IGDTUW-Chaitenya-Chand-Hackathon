import { useEffect, useState } from "react";
import { animate, useReducedMotion } from "framer-motion";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis, XAxis } from "recharts";

import { useRiskIndex } from "@/api/client";
import { CountUp, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { CHART, ChartTooltip } from "@/components/terminal/chart";
import { formatNumber, formatTime } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import { rampColor, regimeColor, riskValueColor } from "@/lib/severity";

const SEGMENTS = 5;
const CX = 100;
const CY = 100;
const R = 80;

function pt(t: number, r: number) {
  const a = Math.PI * (1 - t);
  return { x: CX + r * Math.cos(a), y: CY - r * Math.sin(a) };
}
function arc(t0: number, t1: number) {
  const a = pt(t0, R);
  const b = pt(t1, R);
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${R} ${R} 0 0 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

/** Semicircle gauge 0-100: ramp arcs (reached segments full colour, the rest faint) plus an animated needle. */
export function RiskGauge({ value }: { value: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    const c = animate(shown, value, {
      duration: 0.9,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: setShown,
    });
    return () => c.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduce]);
  const t = Math.max(0, Math.min(1, shown / 100));
  const tip = pt(t, R - 12);
  return (
    <svg
      viewBox="0 0 200 112"
      className="mx-auto w-full max-w-[260px]"
      role="img"
      aria-label={`Global risk index gauge, value ${formatNumber(value, { maximumFractionDigits: 1 })} of 100`}
    >
      {Array.from({ length: SEGMENTS }, (_, i) => {
        const t0 = i / SEGMENTS;
        const t1 = (i + 1) / SEGMENTS;
        const reached = t >= t0;
        return (
          <path
            key={i}
            d={arc(t0 + 0.004, t1 - 0.004)}
            fill="none"
            stroke={rampColor((t0 + t1) / 2)}
            strokeWidth={12}
            opacity={reached ? 1 : 0.22}
          />
        );
      })}
      <line
        x1={CX}
        y1={CY}
        x2={tip.x}
        y2={tip.y}
        stroke="var(--ink)"
        strokeWidth={2}
        strokeLinecap="round"
      />
      <circle cx={CX} cy={CY} r={4} fill="var(--ink)" />
      <text
        x={CX - R}
        y={CY + 11}
        textAnchor="middle"
        className="num"
        fontSize={9}
        fill={CHART.axis}
      >
        0
      </text>
      <text
        x={CX + R}
        y={CY + 11}
        textAnchor="middle"
        className="num"
        fontSize={9}
        fill={CHART.axis}
      >
        100
      </text>
    </svg>
  );
}

export function RiskCard() {
  const q = useRiskIndex();
  const { tz } = useSettings();
  return (
    <Panel
      title="Global Risk Index"
      info="Composite 0-100 score of current market-moving signal pressure. Higher means more severe. Regime: Calm, Elevated or Stressed."
      source={q.data?.meta.source}
      className="h-full"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/risk-index"
        skeleton={<SkeletonBlock className="h-52" />}
      >
        {({ data }) => {
          const series = data.series;
          const first = series[0]?.value;
          const prevBase = first ?? null;
          const delta = prevBase == null ? null : data.value - prevBase;
          return (
            <div className="flex flex-col gap-2">
              <div className="relative">
                <RiskGauge value={data.value} />
                <div className="absolute inset-x-0 bottom-0 flex flex-col items-center leading-none">
                  <CountUp
                    value={data.value}
                    format={(n) =>
                      formatNumber(n, { maximumFractionDigits: 1, minimumFractionDigits: 1 })
                    }
                    className="text-[30px] font-medium"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span
                  className="inline-flex items-center gap-1.5 text-[13px] font-medium"
                  style={{ color: regimeColor(data.regime) }}
                >
                  <span
                    className="inline-block size-2 rounded-full"
                    style={{ background: riskValueColor(data.value) }}
                  />
                  {data.regime}
                </span>
                <span
                  className="num text-[12px] text-muted-foreground"
                  title="Change versus the first point of the 24h series"
                >
                  {delta == null
                    ? "—"
                    : `${delta > 0 ? "+" : ""}${formatNumber(delta, { maximumFractionDigits: 1 })} 24h`}
                </span>
              </div>
              {series.length > 1 ? (
                <div className="h-14" aria-label="24 hour risk index sparkline">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={series} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
                      <XAxis dataKey="ts" hide />
                      <YAxis hide domain={["dataMin", "dataMax"]} />
                      <Tooltip
                        content={
                          <ChartTooltip
                            labelFormatter={(l) => formatTime(String(l), tz, false)}
                            valueFormatter={(v) => formatNumber(v, { maximumFractionDigits: 1 })}
                          />
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        name="Risk"
                        stroke={CHART.primary}
                        strokeWidth={1.5}
                        dot={false}
                        isAnimationActive
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Not enough history for a sparkline yet.
                </p>
              )}
            </div>
          );
        }}
      </QueryBoundary>
    </Panel>
  );
}
