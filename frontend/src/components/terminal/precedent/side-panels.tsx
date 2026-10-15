import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowDown, ArrowUp } from "lucide-react";

import type { PrecedentAnalog, PrecedentResult, ProvenanceSource } from "@/api/types";
import { DASH, formatDate, formatNumber, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CHART } from "@/components/terminal/chart";
import { EmptyState, Panel } from "@/components/terminal/kit";

export function AnalogTable({
  analogs,
  hoverId,
  onHover,
  source,
}: {
  analogs: PrecedentAnalog[];
  hoverId: string | null;
  onHover: (id: string | null) => void;
  source: ProvenanceSource;
}) {
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const rows = [...analogs].sort((a, b) =>
    dir === "desc" ? b.similarity - a.similarity : a.similarity - b.similarity,
  );
  return (
    <Panel
      title="Historical analogs"
      info="Past events judged similar to the selected signal. Similarity is 0 to 100%. Max drawdown is the worst peak-to-trough fall after the event; recovery is trading days to regain the pre-event level."
      source={source}
      bodyClassName="p-0"
    >
      {rows.length === 0 ? (
        <EmptyState
          title="No analogs above this similarity"
          hint="Lower the minimum similarity slider."
          className="py-8"
        />
      ) : (
        <div data-lenis-prevent className="max-h-[360px] overflow-auto">
          <table className="w-full min-w-[420px] text-[12px]">
            <thead className="sticky top-0 bg-paper text-[10px] uppercase tracking-label text-muted-foreground">
              <tr className="border-b border-hairline">
                <th className="px-3 py-1.5 text-left font-medium">Event</th>
                <th className="px-2 py-1.5 text-left font-medium">Date</th>
                <th
                  className="px-2 py-1.5 text-left font-medium"
                  aria-sort={dir === "desc" ? "descending" : "ascending"}
                >
                  <button
                    type="button"
                    onClick={() => setDir(dir === "desc" ? "asc" : "desc")}
                    className="inline-flex items-center gap-1 uppercase hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    Similarity{" "}
                    {dir === "desc" ? (
                      <ArrowDown className="size-3" />
                    ) : (
                      <ArrowUp className="size-3" />
                    )}
                  </button>
                </th>
                <th className="px-2 py-1.5 text-right font-medium">Max DD</th>
                <th className="px-3 py-1.5 text-right font-medium">Recovery</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr
                  key={a.eventId}
                  tabIndex={0}
                  onMouseEnter={() => onHover(a.eventId)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(a.eventId)}
                  onBlur={() => onHover(null)}
                  className={cn(
                    "border-b border-hairline/60 outline-none transition-colors",
                    hoverId === a.eventId ? "bg-accent" : "hover:bg-surface/70",
                  )}
                >
                  <td className="max-w-[160px] truncate px-3 py-1.5" title={a.title}>
                    {a.title}
                  </td>
                  <td className="num whitespace-nowrap px-2 py-1.5 text-muted-foreground">
                    {formatDate(a.date)}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex items-center gap-1.5">
                      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-surface">
                        <span
                          className="block h-full bg-primary"
                          style={{ width: `${Math.max(0, Math.min(1, a.similarity)) * 100}%` }}
                        />
                      </span>
                      <span className="num text-[11px]">{formatPct(a.similarity, 0)}</span>
                    </span>
                  </td>
                  <td className="num px-2 py-1.5 text-right">{formatPct(a.maxDrawdown, 1)}</td>
                  <td className="num px-3 py-1.5 text-right">
                    {a.recoveryDays == null
                      ? DASH
                      : `${formatNumber(a.recoveryDays, { maximumFractionDigits: 0 })}d`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

const HW = 360;
const HH = 170;
const HM = { l: 36, r: 14, t: 12, b: 26 };

export function HalfLifeCurve({
  precedent,
  source,
}: {
  precedent: PrecedentResult;
  source: ProvenanceSource;
}) {
  const reduce = useReducedMotion();
  const hl = precedent.halfLifeDays;
  const T = precedent.horizonDays > 0 ? precedent.horizonDays : 30;
  const sx = (t: number) => HM.l + (t / T) * (HW - HM.l - HM.r);
  const sy = (v: number) => HM.t + (1 - v) * (HH - HM.t - HM.b);
  return (
    <Panel
      title="Half-life decay"
      info="How quickly the event's market impact fades: remaining impact = exp(-ln2 · t / half-life). At the half-life marker half of the impact is gone."
      source={source}
    >
      {hl == null || !(hl > 0) ? (
        <EmptyState title="Half-life not available (impact model not live)" className="py-6" />
      ) : (
        <>
          <svg
            viewBox={`0 0 ${HW} ${HH}`}
            className="h-auto w-full"
            role="img"
            aria-label={`Decay curve with half-life of ${formatNumber(hl, { maximumFractionDigits: 1 })} days`}
          >
            {[0, 0.5, 1].map((v) => (
              <g key={v}>
                <line
                  x1={HM.l}
                  x2={HW - HM.r}
                  y1={sy(v)}
                  y2={sy(v)}
                  stroke={CHART.grid}
                  strokeWidth={0.75}
                />
                <text
                  x={HM.l - 6}
                  y={sy(v) + 3}
                  textAnchor="end"
                  fontSize={9}
                  fill={CHART.axis}
                  fontFamily="IBM Plex Mono, monospace"
                >
                  {formatPct(v, 0)}
                </text>
              </g>
            ))}
            {[0, T / 2, T].map((t) => (
              <text
                key={t}
                x={sx(t)}
                y={HH - 8}
                textAnchor="middle"
                fontSize={9}
                fill={CHART.axis}
                fontFamily="IBM Plex Mono, monospace"
              >
                {formatNumber(t, { maximumFractionDigits: 0 })}
              </text>
            ))}
            <motion.path
              d={Array.from(
                { length: Math.round(T) + 1 },
                (_, t) =>
                  `${t ? "L" : "M"}${sx(t).toFixed(1)} ${sy(Math.exp((-Math.LN2 * t) / hl)).toFixed(1)}`,
              ).join(" ")}
              fill="none"
              stroke={CHART.primary}
              strokeWidth={2}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: reduce ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
            />
            {hl <= T ? (
              <g>
                <line
                  x1={sx(hl)}
                  x2={sx(hl)}
                  y1={sy(0.5)}
                  y2={sy(0)}
                  stroke={CHART.ink}
                  strokeWidth={0.75}
                  strokeDasharray="3 3"
                />
                <line
                  x1={HM.l}
                  x2={sx(hl)}
                  y1={sy(0.5)}
                  y2={sy(0.5)}
                  stroke={CHART.ink}
                  strokeWidth={0.75}
                  strokeDasharray="3 3"
                />
                <circle
                  cx={sx(hl)}
                  cy={sy(0.5)}
                  r={4}
                  fill="var(--paper, #fff)"
                  stroke={CHART.ink}
                  strokeWidth={1.75}
                />
                <text
                  x={Math.min(sx(hl) + 8, HW - 70)}
                  y={sy(0.5) - 8}
                  fontSize={10}
                  fill={CHART.ink}
                  fontFamily="IBM Plex Mono, monospace"
                >
                  half-life {formatNumber(hl, { maximumFractionDigits: 1 })}d
                </text>
              </g>
            ) : null}
          </svg>
          <p className="num mt-1 text-[11px] text-muted-foreground">
            Half-life {formatNumber(hl, { maximumFractionDigits: 1 })} days
            {hl > T ? ` (beyond the ${T}-day horizon)` : ""}
          </p>
        </>
      )}
    </Panel>
  );
}
