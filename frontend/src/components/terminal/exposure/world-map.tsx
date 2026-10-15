import { useMemo, useState, type KeyboardEvent } from "react";

import { flattenSignals, useExposure, usePortfolio, useSignals } from "@/api/client";
import type { Exposure, Holding } from "@/api/types";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock, Stat } from "@/components/terminal/kit";
import { ModeMarker } from "@/components/terminal/chips";
import { formatCurrency, formatPct } from "@/lib/format";
import { openSignal } from "@/lib/drawer";
import { rampColor, SEVERITY_VARS } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { MAP_H, MAP_W, displayName, derivePins, mapShapes, resolveKey } from "./geo";

type Metric = "exposure" | "stressedLoss";
const METRICS: { id: Metric; label: string }[] = [
  { id: "exposure", label: "Exposure" },
  { id: "stressedLoss", label: "Stressed loss" },
];

export function WorldMap() {
  const exp = useExposure();
  const sig = useSignals({ limit: 100 });
  const pf = usePortfolio();
  const [metric, setMetric] = useState<Metric>("exposure");
  const [selected, setSelected] = useState<string | null>(null);
  const signals = useMemo(() => flattenSignals(sig.data), [sig.data]);

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
      <Panel
        className="lg:col-span-8"
        title="Country exposure"
        info="Portfolio exposure (sum of notional) per country, or the loss under the stressed scenario. Pulsing pins mark recent signals that name a portfolio country."
        source={exp.data?.meta.source}
        actions={
          <div role="group" aria-label="Map metric" className="flex gap-1">
            {METRICS.map((m) => (
              <button
                key={m.id}
                type="button"
                aria-pressed={metric === m.id}
                onClick={() => setMetric(m.id)}
                className={cn(
                  "rounded-sm border px-2 py-0.5 text-[11px] outline-none focus-visible:ring-1 focus-visible:ring-ring",
                  metric === m.id
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-hairline text-muted-foreground hover:text-foreground",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        }
      >
        <QueryBoundary
          query={exp}
          endpoint="GET /api/portfolio/exposure"
          skeleton={<SkeletonBlock className="h-80" />}
          isEmpty={(e) => e.data.byCountry.length === 0}
          emptyTitle="No country exposure"
          emptyHint="The portfolio has no holdings with a country."
        >
          {(env) => (
            <MapBody
              rows={env.data.byCountry}
              metric={metric}
              selected={selected}
              onSelect={setSelected}
              signals={signals}
              signalsReady={!sig.isPending}
            />
          )}
        </QueryBoundary>
      </Panel>
      <Panel
        className="lg:col-span-4"
        title="Country detail"
        info="Exposure, stressed loss, holdings and located signals for the selected country."
        source={exp.data?.meta.source}
      >
        <QueryBoundary
          query={exp}
          endpoint="GET /api/portfolio/exposure"
          skeleton={<SkeletonBlock lines={6} />}
        >
          {(env) => (
            <Detail rows={env.data.byCountry} selected={selected} pf={pf} signals={signals} />
          )}
        </QueryBoundary>
      </Panel>
    </div>
  );
}

type Row = Exposure["byCountry"][number];

/** Aggregate API rows onto world-atlas shape keys. */
function useJoined(rows: Row[]) {
  return useMemo(() => {
    const shapes = mapShapes();
    const keys = new Set(shapes.map((s) => s.key));
    const byKey = new Map<string, { name: string; exposure: number; stressedLoss: number }>();
    const unmapped: Row[] = [];
    for (const r of rows) {
      const k = resolveKey(r.country, keys);
      if (!k) {
        unmapped.push(r);
        continue;
      }
      const cur = byKey.get(k);
      if (cur) {
        cur.exposure += r.exposure;
        cur.stressedLoss += r.stressedLoss;
      } else
        byKey.set(k, {
          name: displayName(r.country),
          exposure: r.exposure,
          stressedLoss: r.stressedLoss,
        });
    }
    return { shapes, keys, byKey, unmapped };
  }, [rows]);
}

function MapBody({
  rows,
  metric,
  selected,
  onSelect,
  signals,
  signalsReady,
}: {
  rows: Row[];
  metric: Metric;
  selected: string | null;
  onSelect: (k: string | null) => void;
  signals: ReturnType<typeof flattenSignals>;
  signalsReady: boolean;
}) {
  const { shapes, byKey, unmapped } = useJoined(rows);
  const [hover, setHover] = useState<string | null>(null);
  const pins = useMemo(
    () =>
      derivePins(
        signals,
        rows.map((r) => r.country),
        shapes,
      ),
    [signals, rows, shapes],
  );
  const values = [...byKey.values()].map((v) => v[metric]);
  const max = values.length ? Math.max(...values) : 0;
  const min = values.length ? Math.min(...values) : 0;
  const hoverRow = hover ? byKey.get(hover) : undefined;

  return (
    <div>
      <div className="mb-1 flex h-5 items-center justify-between text-[11px]" aria-live="polite">
        {hoverRow ? (
          <span>
            <span className="font-medium">{hoverRow.name}</span>{" "}
            <span className="num text-muted-foreground">
              {formatCurrency(hoverRow.exposure)} exposure · {formatCurrency(hoverRow.stressedLoss)}{" "}
              stressed loss
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">Hover or focus a country; Enter selects it.</span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${MAP_W} ${MAP_H}`}
        className="h-auto w-full"
        role="group"
        aria-label="World map of portfolio exposure"
      >
        {shapes.map((s) => {
          const v = byKey.get(s.key);
          const has = !!v;
          const t = v && max > 0 ? v[metric] / max : null;
          const isSel = selected === s.key;
          const act = () => has && onSelect(isSel ? null : s.key);
          return (
            <path
              key={s.key}
              d={s.d}
              fill={has ? rampColor(t) : "var(--surface)"}
              stroke={isSel ? "var(--ink)" : "var(--hairline)"}
              strokeWidth={isSel ? 1.4 : 0.5}
              {...(has
                ? {
                    role: "button",
                    tabIndex: 0,
                    "aria-label": `${v.name}: ${formatCurrency(v.exposure)} exposure, ${formatCurrency(v.stressedLoss)} stressed loss`,
                    "aria-pressed": isSel,
                    onClick: act,
                    onKeyDown: (e: KeyboardEvent) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        act();
                      }
                    },
                    onMouseEnter: () => setHover(s.key),
                    onMouseLeave: () => setHover(null),
                    onFocus: () => setHover(s.key),
                    onBlur: () => setHover(null),
                    className: "cursor-pointer outline-none focus-visible:stroke-[var(--ink)]",
                  }
                : {})}
            />
          );
        })}
        {pins.map((p) => (
          <g
            key={p.signal.id}
            role="button"
            tabIndex={0}
            aria-label={`Open signal: ${p.signal.headline}`}
            className="cursor-pointer outline-none"
            onClick={() => openSignal(p.signal.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openSignal(p.signal.id);
              }
            }}
          >
            <title>{p.signal.headline}</title>
            <circle
              cx={p.x}
              cy={p.y}
              r={5}
              fill="var(--primary)"
              opacity={0.35}
              className="pin-pulse"
            />
            <circle
              cx={p.x}
              cy={p.y}
              r={2.6}
              fill="var(--primary)"
              stroke="var(--paper)"
              strokeWidth={0.8}
            />
          </g>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="num">{formatCurrency(min)}</span>
          <span
            className="flex h-2 w-32 overflow-hidden rounded-sm border border-hairline"
            aria-hidden
          >
            {SEVERITY_VARS.map((c) => (
              <span key={c} className="flex-1" style={{ background: c }} />
            ))}
          </span>
          <span className="num">{formatCurrency(max)}</span>
          <span className="ml-2 inline-flex items-center gap-1">
            <span className="inline-block size-2.5 rounded-sm border border-hairline bg-surface" />{" "}
            no data
          </span>
        </div>
        <span>
          {pins.length > 0
            ? `${pins.length} located event${pins.length === 1 ? "" : "s"}`
            : signalsReady
              ? "No located events in the latest signals"
              : "Loading signals…"}
        </span>
      </div>
      {unmapped.length > 0 ? (
        <p className="num mt-1 text-[10px] text-muted-foreground">
          Not shown on map (no matching shape):{" "}
          {unmapped.map((u) => `${u.country} ${formatCurrency(u.exposure)}`).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function Detail({
  rows,
  selected,
  pf,
  signals,
}: {
  rows: Row[];
  selected: string | null;
  pf: ReturnType<typeof usePortfolio>;
  signals: ReturnType<typeof flattenSignals>;
}) {
  const { shapes, keys, byKey } = useJoined(rows);
  const rec = selected ? byKey.get(selected) : undefined;
  const pins = useMemo(
    () =>
      derivePins(
        signals,
        rows.map((r) => r.country),
        shapes,
      ).filter((p) => p.key === selected),
    [signals, rows, shapes, selected],
  );
  if (!selected || !rec)
    return (
      <EmptyState
        title="Select a country"
        hint="Click a shaded country on the map to see its holdings and located signals."
      />
    );
  const ratio = rec.exposure > 0 ? rec.stressedLoss / rec.exposure : null;
  return (
    <div className="space-y-3">
      <div>
        <div className="text-[15px] font-medium">{rec.name}</div>
        <div className="mt-2 grid grid-cols-2 gap-3">
          <Stat
            label="Exposure"
            info="Sum of notional of holdings domiciled in this country."
            value={formatCurrency(rec.exposure)}
          />
          <Stat
            label="Stressed loss"
            info="Estimated loss for this country under the stressed scenario."
            value={formatCurrency(rec.stressedLoss)}
            sub={ratio == null ? undefined : `${formatPct(ratio, 1)} of exposure`}
          />
        </div>
      </div>
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-label text-muted-foreground">
          Holdings
        </div>
        <QueryBoundary
          query={pf}
          endpoint="GET /api/portfolio"
          skeleton={<SkeletonBlock lines={3} />}
        >
          {(env) => (
            <HoldingList
              holdings={env.data.filter((h: Holding) => resolveKey(h.country, keys) === selected)}
            />
          )}
        </QueryBoundary>
      </div>
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-label text-muted-foreground">
          Related signals
        </div>
        {pins.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No located events for this country in the latest signals.
          </p>
        ) : (
          <ul className="space-y-1" data-lenis-prevent>
            {pins.map((p) => (
              <li key={p.signal.id}>
                <button
                  type="button"
                  onClick={() => openSignal(p.signal.id)}
                  className="flex w-full items-start gap-1.5 rounded-sm px-1 py-0.5 text-left text-xs outline-none hover:bg-surface focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <ModeMarker mode={p.signal.mode} />
                  <span className="line-clamp-2">{p.signal.headline}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function HoldingList({ holdings }: { holdings: Holding[] }) {
  if (holdings.length === 0)
    return <p className="text-xs text-muted-foreground">No holdings in this country.</p>;
  return (
    <ul className="max-h-56 divide-y divide-hairline overflow-y-auto" data-lenis-prevent>
      {[...holdings]
        .sort((a, b) => b.notional - a.notional)
        .map((h) => (
          <li key={h.id} className="flex items-baseline justify-between gap-2 py-1 text-xs">
            <span className="min-w-0 truncate">
              {h.counterparty}{" "}
              <span className="text-muted-foreground">
                · {h.assetType} · {h.sector}
              </span>
            </span>
            <span className="num shrink-0">{formatCurrency(h.notional)}</span>
          </li>
        ))}
    </ul>
  );
}
