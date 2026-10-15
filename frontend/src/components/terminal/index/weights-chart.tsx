import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Pause, Play, Square } from "lucide-react";

import { useIndexWeights } from "@/api/client";
import { ChartTooltip, axisProps } from "@/components/terminal/chart";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { Slider } from "@/components/ui/slider";
import { formatPct } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import type { WeightsResponse } from "@/api/types";
import { fmtStamp, seriesColor } from "./util";

const STEP_MS = 80;

function Inner({ data }: { data: WeightsResponse }) {
  const { tz } = useSettings();
  const pts = data.points;
  const n = pts.length;
  const [idx, setIdx] = useState(Math.max(0, n - 1));
  const [playing, setPlaying] = useState(false);
  const [replay, setReplay] = useState(false);
  const idxRef = useRef(idx);
  idxRef.current = idx;

  // Follow new data: jump to the latest point whenever the series length changes.
  useEffect(() => {
    setIdx(Math.max(0, n - 1));
    setPlaying(false);
    setReplay(false);
  }, [n]);

  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => {
      const next = idxRef.current + 1;
      if (next >= n - 1) {
        setIdx(n - 1);
        setPlaying(false);
        setReplay(false);
      } else setIdx(next);
    }, STEP_MS);
    return () => window.clearInterval(t);
  }, [playing, n]);

  const colorOf = useMemo(() => {
    const m = new Map<string, string>();
    data.tickers.forEach((t, i) => m.set(t, seriesColor(i)));
    return m;
  }, [data.tickers]);

  const rows = useMemo(
    () => pts.map((p, i) => (replay && i > idx ? { ts: p.ts } : { ts: p.ts, ...p.weights })),
    [pts, replay, idx],
  );

  const cur = pts[Math.min(idx, n - 1)];
  const last = pts[n - 1];
  const legend = useMemo(
    () =>
      [...data.tickers]
        .sort((a, b) => (last?.weights[b] ?? 0) - (last?.weights[a] ?? 0))
        .slice(0, 8),
    [data.tickers, last],
  );
  const readout = useMemo(
    () => Object.entries(cur?.weights ?? {}).sort((a, b) => b[1] - a[1]),
    [cur],
  );

  const start = () => {
    if (n < 2) return;
    if (!replay || idx >= n - 1) setIdx(0);
    setReplay(true);
    setPlaying(true);
  };
  const stop = () => {
    setPlaying(false);
    setReplay(false);
    setIdx(n - 1);
  };

  const btn =
    "inline-flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2 py-1 text-xs font-medium text-foreground outline-none transition-colors hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40";

  return (
    <div className="space-y-3">
      <div
        className="h-64 w-full"
        role="img"
        aria-label="Stacked area chart of constituent weights over time"
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--hairline)" vertical={false} />
            <XAxis
              dataKey="ts"
              {...axisProps}
              minTickGap={48}
              tickFormatter={(v: string) => fmtStamp(v, tz)}
            />
            <YAxis
              {...axisProps}
              width={40}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              domain={[0, "auto"]}
            />
            <Tooltip
              isAnimationActive={false}
              content={(p) => (
                <ChartTooltip
                  active={p.active}
                  label={p.label as string | undefined}
                  payload={[
                    ...((p.payload ?? []) as {
                      name?: string;
                      value?: number;
                      color?: string;
                      dataKey?: string;
                    }[]),
                  ].sort((a, b) => (b.value ?? 0) - (a.value ?? 0))}
                  labelFormatter={(l) => fmtStamp(String(l), tz)}
                  valueFormatter={(v) => formatPct(v, 2)}
                />
              )}
            />
            {data.tickers.map((t) => (
              <Area
                key={t}
                type="monotone"
                dataKey={t}
                name={t}
                stackId="w"
                stroke="var(--paper)"
                strokeWidth={0.5}
                fill={colorOf.get(t)}
                fillOpacity={0.95}
                isAnimationActive={false}
              />
            ))}
            {cur ? <ReferenceLine x={cur.ts} stroke="var(--ink)" strokeDasharray="3 3" /> : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div
        className="flex flex-wrap items-center gap-x-3 gap-y-1"
        aria-label="Legend: top 8 constituents by current weight"
      >
        {legend.map((t) => (
          <span key={t} className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <span
              className="inline-block size-2 rounded-sm"
              style={{ background: colorOf.get(t) }}
            />
            <span className="num text-foreground">{t}</span>
            <span className="num">{formatPct(last?.weights[t], 1)}</span>
          </span>
        ))}
        {data.tickers.length > legend.length ? (
          <span className="text-[11px] text-muted-foreground">
            +{data.tickers.length - legend.length} more (see tooltip)
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex shrink-0 items-center gap-1.5">
          {playing ? (
            <button type="button" className={btn} onClick={() => setPlaying(false)}>
              <Pause className="size-3" /> Pause
            </button>
          ) : (
            <button
              type="button"
              className={btn}
              onClick={start}
              disabled={n < 2}
              title={n < 2 ? "Needs at least 2 points" : "Animate weights from first to last point"}
            >
              <Play className="size-3" /> {replay && idx < n - 1 ? "Resume" : "Replay"}
            </button>
          )}
          <button
            type="button"
            className={btn}
            onClick={stop}
            disabled={!replay && !playing}
            aria-label="Stop replay"
          >
            <Square className="size-3" /> Stop
          </button>
        </div>
        <Slider
          aria-label="Time scrubber"
          min={0}
          max={Math.max(0, n - 1)}
          step={1}
          value={[Math.min(idx, Math.max(0, n - 1))]}
          disabled={n < 2}
          onValueChange={(v) => {
            setPlaying(false);
            setReplay(false);
            setIdx(v[0] ?? 0);
          }}
        />
        <span className="num w-24 shrink-0 text-right text-[11px] text-muted-foreground">
          {fmtStamp(cur?.ts, tz)}
        </span>
      </div>

      <div className="rounded-[3px] border border-hairline bg-surface px-2 py-1.5">
        <div className="mb-1 text-[11px] uppercase tracking-label text-muted-foreground">
          Weights at {fmtStamp(cur?.ts, tz)}
        </div>
        <div
          data-lenis-prevent
          className="flex max-h-16 flex-wrap gap-x-3 gap-y-0.5 overflow-y-auto"
        >
          {readout.map(([t, w]) => (
            <span key={t} className="flex items-center gap-1 text-[11px]">
              <span
                className="inline-block size-1.5 rounded-full"
                style={{ background: colorOf.get(t) }}
              />
              <span className="num text-foreground">{t}</span>
              <span className="num text-muted-foreground">{formatPct(w, 1)}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function WeightsChart() {
  const q = useIndexWeights();
  return (
    <Panel
      title="Constituent weights over time"
      info="Stacked weights of each constituent at every point of the weights history. Drag the scrubber or press Replay to animate; hover for the weights at that moment."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/index/weights"
        skeleton={<SkeletonBlock className="h-80" />}
        isEmpty={(e) => e.data.points.length === 0}
        emptyTitle="No weight history yet"
        emptyHint="Weights appear once the index has produced at least one snapshot."
      >
        {(env) => <Inner data={env.data} />}
      </QueryBoundary>
    </Panel>
  );
}
