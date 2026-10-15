import { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import type { AssetClassKey, PrecedentAnalog, PrecedentResult } from "@/api/types";
import { formatDate, formatPct } from "@/lib/format";
import { CHART } from "@/components/terminal/chart";

const W = 900;
const H = 380;
const M = { l: 56, r: 18, t: 30, b: 34 };
const EASE = [0.22, 1, 0.36, 1] as const;

type Pt = { day: number; ret: number };
const line = (pts: { x: number; y: number }[]) =>
  pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

export function HeroChart({
  precedent,
  asset,
  analogs,
  hoverId,
  onHover,
}: {
  precedent: PrecedentResult;
  asset: AssetClassKey;
  analogs: { id: string; analog: PrecedentAnalog }[];
  hoverId: string | null;
  onHover: (id: string | null) => void;
}) {
  const reduce = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const series = precedent.series[asset];

  const geo = useMemo(() => {
    const sorted = (pts: Pt[] | undefined) => [...(pts ?? [])].sort((a, b) => a.day - b.day);
    const median = sorted(series?.median);
    const band = [...(series?.band ?? [])].sort((a, b) => a.day - b.day);
    const paths = analogs.map(({ id, analog }) => ({
      id,
      analog,
      pts: sorted(analog.paths[asset]),
    }));
    const ys: number[] = [
      0,
      ...median.map((m) => m.ret),
      ...band.flatMap((b) => [b.p10, b.p90]),
      ...paths.flatMap((p) => p.pts.map((x) => x.ret)),
    ];
    const days: number[] = [
      0,
      ...median.map((m) => m.day),
      ...band.map((b) => b.day),
      ...paths.flatMap((p) => p.pts.map((x) => x.day)),
    ];
    const maxDay = precedent.horizonDays > 0 ? precedent.horizonDays : Math.max(...days, 1);
    let lo = Math.min(...ys);
    let hi = Math.max(...ys);
    const pad = (hi - lo || 0.02) * 0.08;
    lo -= pad;
    hi += pad;
    const sx = (d: number) => M.l + (d / maxDay) * (W - M.l - M.r);
    const sy = (v: number) => M.t + (1 - (v - lo) / (hi - lo)) * (H - M.t - M.b);
    const yTicks = Array.from({ length: 6 }, (_, i) => lo + ((hi - lo) * i) / 5);
    const xStep = maxDay <= 10 ? 1 : maxDay <= 40 ? 5 : 10;
    const xTicks: number[] = [];
    for (let d = 0; d <= maxDay; d += xStep) xTicks.push(d);
    const bandPoly = band.length
      ? `${line(band.map((b) => ({ x: sx(b.day), y: sy(b.p90) })))} ${band
          .map((b) => `L${sx(b.day).toFixed(1)} ${sy(b.p10).toFixed(1)}`)
          .reverse()
          .join(" ")} Z`
      : "";
    return { median, paths, sx, sy, yTicks, xTicks, bandPoly, maxDay };
  }, [series, analogs, asset, precedent.horizonDays]);

  const ordered = useMemo(
    () => [...geo.paths].sort((a, b) => Number(a.id === hoverId) - Number(b.id === hoverId)),
    [geo.paths, hoverId],
  );
  const hovered = geo.paths.find((p) => p.id === hoverId)?.analog ?? null;
  const dur = reduce ? 0 : 0.9;

  const track = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r || r.width === 0) return;
    setPointer({
      x: ((e.clientX - r.left) / r.width) * W,
      y: ((e.clientY - r.top) / r.height) * H,
    });
  };

  const label = hovered
    ? `${hovered.title}  ·  ${formatDate(hovered.date)}  ·  similarity ${formatPct(hovered.similarity, 0)}`
    : "";
  const lw = label.length * 6.1 + 16;
  const lx = pointer ? Math.min(Math.max(pointer.x + 12, M.l), W - M.r - lw) : M.l + 8;
  const ly = pointer ? Math.max(pointer.y - 30, M.t) : M.t + 6;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Normalized returns day 0 to day ${geo.maxDay}, ${analogs.length} historical analogs, median and 10 to 90 percentile band`}
      onMouseMove={track}
      onMouseLeave={() => {
        setPointer(null);
        onHover(null);
      }}
    >
      {geo.yTicks.map((t) => (
        <g key={t}>
          <line
            x1={M.l}
            x2={W - M.r}
            y1={geo.sy(t)}
            y2={geo.sy(t)}
            stroke={CHART.grid}
            strokeWidth={0.75}
          />
          <text
            x={M.l - 8}
            y={geo.sy(t) + 3}
            textAnchor="end"
            fontSize={10}
            fill={CHART.axis}
            fontFamily="IBM Plex Mono, monospace"
          >
            {formatPct(t, 1)}
          </text>
        </g>
      ))}
      {geo.xTicks.map((d) => (
        <text
          key={d}
          x={geo.sx(d)}
          y={H - M.b + 16}
          textAnchor="middle"
          fontSize={10}
          fill={CHART.axis}
          fontFamily="IBM Plex Mono, monospace"
        >
          {d}
        </text>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 4} textAnchor="middle" fontSize={10} fill={CHART.axis}>
        Trading days after event
      </text>
      <line
        x1={M.l}
        x2={W - M.r}
        y1={geo.sy(0)}
        y2={geo.sy(0)}
        stroke={CHART.axis}
        strokeWidth={0.75}
        strokeDasharray="3 3"
      />

      <motion.path
        d={geo.bandPoly}
        fill={CHART.band}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduce ? 0 : 0.6, delay: reduce ? 0 : 0.5 }}
      />

      <AnimatePresence>
        {ordered.map(({ id, pts }) => {
          const on = id === hoverId;
          return (
            <motion.path
              key={id}
              d={line(pts.map((p) => ({ x: geo.sx(p.day), y: geo.sy(p.ret) })))}
              fill="none"
              stroke={on ? CHART.primary : CHART.faint}
              strokeWidth={on ? 2 : 1}
              strokeLinejoin="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: hoverId && !on ? 0.55 : 1 }}
              exit={{ opacity: 0, transition: { duration: 0.25 } }}
              transition={{
                pathLength: { duration: dur, ease: EASE },
                opacity: { duration: 0.25 },
              }}
            />
          );
        })}
      </AnimatePresence>

      <motion.path
        d={line(geo.median.map((p) => ({ x: geo.sx(p.day), y: geo.sy(p.ret) })))}
        fill="none"
        stroke={CHART.ink}
        strokeWidth={2.75}
        strokeLinejoin="round"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: dur, ease: EASE }}
      />

      {geo.paths.map(({ id, pts }) => (
        <path
          key={`hit-${id}`}
          d={line(pts.map((p) => ({ x: geo.sx(p.day), y: geo.sy(p.ret) })))}
          fill="none"
          stroke="transparent"
          strokeWidth={10}
          pointerEvents="stroke"
          style={{ cursor: "pointer" }}
          onMouseEnter={() => onHover(id)}
        />
      ))}

      <line
        x1={geo.sx(0)}
        x2={geo.sx(0)}
        y1={M.t - 6}
        y2={H - M.b}
        stroke={CHART.primary}
        strokeWidth={1.5}
      />
      <text
        x={geo.sx(0) + 6}
        y={M.t - 12 + 8}
        fontSize={10.5}
        fontWeight={600}
        fill={CHART.primary}
      >
        Event (day 0)
      </text>

      {hovered ? (
        <g pointerEvents="none">
          <rect
            x={lx}
            y={ly}
            width={lw}
            height={22}
            rx={3}
            fill="var(--paper, #fff)"
            stroke={CHART.primary}
            strokeWidth={0.75}
          />
          <text
            x={lx + 8}
            y={ly + 15}
            fontSize={10.5}
            fill={CHART.ink}
            fontFamily="IBM Plex Mono, monospace"
          >
            {label}
          </text>
        </g>
      ) : null}
    </svg>
  );
}
