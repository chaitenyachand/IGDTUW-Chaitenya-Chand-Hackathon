import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import type { AssetClassKey, Envelope, PrecedentResult } from "@/api/types";
import { formatDate, formatPct } from "@/lib/format";
import { ASSET_LABEL, buildOverlay } from "@/lib/precedent";
import { cn } from "@/lib/utils";
import { EmptyState, InfoTip, Panel } from "@/components/terminal/kit";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { HeroChart } from "./hero-chart";
import { AnalogTable, HalfLifeCurve } from "./side-panels";
import { ShockTable } from "./shock-table";

const TABS: { label: string; keys: AssetClassKey[] }[] = [
  { label: "Equity Index", keys: ["equity_index"] },
  { label: "Energy", keys: ["energy"] },
  { label: "Banks", keys: ["banks"] },
  { label: "Rates", keys: ["long_treasury", "mid_treasury"] },
  { label: "Credit Spreads", keys: ["high_yield", "inv_grade"] },
  { label: "FX", keys: ["dollar"] },
];

export function PrecedentView({
  env,
  onRun,
}: {
  env: Envelope<PrecedentResult>;
  onRun: () => void;
}) {
  const p = env.data;
  const source = env.meta.source;
  const available = (keys: AssetClassKey[]) => keys.filter((k) => p.series[k]);
  const firstTab = TABS.findIndex((t) => available(t.keys).length > 0);
  const [tab, setTab] = useState(Math.max(0, firstTab));
  const [sub, setSub] = useState<AssetClassKey | null>(null);
  const [minSim, setMinSim] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);

  // Reset to the first tab that has data when a different signal's result arrives.
  useEffect(() => {
    setTab(
      Math.max(
        0,
        TABS.findIndex((t) => t.keys.some((k) => p.series[k])),
      ),
    );
    setSub(null);
    setHoverId(null);
  }, [p.signalId]); // eslint-disable-line react-hooks/exhaustive-deps

  const cur = TABS[tab] ?? TABS[0]!;
  const keys = available(cur.keys);
  const asset: AssetClassKey | null = (sub && keys.includes(sub) ? sub : keys[0]) ?? null;
  const overlay = useMemo(
    () => (asset ? buildOverlay(p, asset, minSim) : null),
    [p, asset, minSim],
  );
  const tableAnalogs = useMemo(
    () => p.analogs.filter((a) => a.similarity >= minSim),
    [p.analogs, minSim],
  );
  const s = asset ? p.series[asset] : undefined;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="space-y-4"
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title="Event study: normalized returns"
          info="Return of each historical analog (grey) from the event date, the median across analogs (dark) and the 10th to 90th percentile band (shaded). The crimson marker is the event itself (day 0)."
          source={source}
          bodyClassName="p-4"
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div role="tablist" aria-label="Asset class" className="inline-flex flex-wrap gap-1">
              {TABS.map((t, i) => {
                const has = available(t.keys).length > 0;
                const btn = (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={i === tab}
                    disabled={!has}
                    onClick={() => {
                      setTab(i);
                      setSub(null);
                    }}
                    className={cn(
                      "rounded-sm border px-2.5 py-1 text-xs outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40",
                      i === tab
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-hairline bg-paper hover:bg-surface",
                    )}
                  >
                    {t.label}
                  </button>
                );
                return has ? (
                  <span key={t.label}>{btn}</span>
                ) : (
                  <Tooltip key={t.label}>
                    <TooltipTrigger asChild>
                      <span tabIndex={0}>{btn}</span>
                    </TooltipTrigger>
                    <TooltipContent className="text-xs">
                      No {t.label} series for this event
                    </TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
            <label className="flex w-60 items-center gap-2 text-[11px] uppercase tracking-label text-muted-foreground">
              <span className="flex shrink-0 items-center gap-1">
                Min similarity{" "}
                <InfoTip text="Hide analogs less similar to this event than the threshold." />
              </span>
              <Slider
                min={0}
                max={1}
                step={0.01}
                value={[minSim]}
                onValueChange={(v) => setMinSim(v[0] ?? 0)}
                aria-label="Minimum similarity"
              />
              <span className="num w-9 text-right normal-case tracking-normal text-foreground">
                {formatPct(minSim, 0)}
              </span>
            </label>
          </div>
          {keys.length > 1 ? (
            <div className="mb-2 flex gap-1" role="group" aria-label={`${cur.label} series`}>
              {keys.map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={k === asset}
                  onClick={() => setSub(k)}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] outline-none focus-visible:ring-1 focus-visible:ring-ring",
                    k === asset
                      ? "border-ink bg-ink text-paper"
                      : "border-hairline hover:bg-surface",
                  )}
                >
                  {ASSET_LABEL[k]}
                </button>
              ))}
            </div>
          ) : null}
          {asset && overlay ? (
            <>
              <HeroChart
                key={`${p.signalId}-${asset}`}
                precedent={p}
                asset={asset}
                analogs={overlay.analogs}
                hoverId={hoverId}
                onHover={setHoverId}
              />
              <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-hairline pt-3 text-[12px]">
                <span className="num">
                  <span className="text-muted-foreground">n </span>
                  <strong className="font-semibold">{s?.n ?? 0}</strong>
                  <span className="text-muted-foreground">
                    {" "}
                    in {ASSET_LABEL[asset]} · {overlay.analogs.length} of {p.analogs.length} analogs
                    shown · {p.n} total
                  </span>
                </span>
                <span className="num">
                  <span className="text-muted-foreground">History used: </span>
                  <strong className="font-semibold">
                    {formatDate(p.dateRange.from)} – {formatDate(p.dateRange.to)}
                  </strong>
                </span>
                <span className="ml-auto flex items-center gap-3 text-[11px] text-muted-foreground">
                  <Key color="var(--primary)" label="Event (day 0)" />
                  <Key color="var(--ink)" label="Median" thick />
                  <Key color="oklch(0.86 0.006 285)" label="Analog" />
                  <Key color="oklch(0.55 0.217 20 / 0.18)" label="P10–P90" block />
                </span>
              </div>
            </>
          ) : (
            <EmptyState title="No return series available for this event" />
          )}
        </Panel>
        <div className="space-y-4">
          <AnalogTable
            analogs={tableAnalogs}
            hoverId={hoverId}
            onHover={setHoverId}
            source={source}
          />
          <HalfLifeCurve precedent={p} source={source} />
        </div>
      </div>
      <ShockTable precedent={p} source={source} onRun={onRun} />
    </motion.div>
  );
}

function Key({
  color,
  label,
  thick,
  block,
}: {
  color: string;
  label: string;
  thick?: boolean;
  block?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="inline-block"
        style={{ width: 14, height: block ? 8 : thick ? 3 : 1.5, background: color }}
      />
      {label}
    </span>
  );
}
