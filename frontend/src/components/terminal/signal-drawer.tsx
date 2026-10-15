import { useEffect, useMemo, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, X } from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";
import { closeSignal, useOpenSignalId } from "@/lib/drawer";
import { useGo } from "@/lib/nav";
import { useSettings } from "@/lib/settings";
import { usePortfolio, usePrecedent, useSignal } from "@/api/client";
import type { Signal } from "@/api/types";
import { DASH, formatCurrency, formatDateTime, formatNumber, formatPct } from "@/lib/format";
import { FLAG_INFO } from "@/lib/severity";
import { buildOverlay, pickAssetClass, ASSET_LABEL } from "@/lib/precedent";
import { CountUp, EmptyState, ErrorCard, InfoTip, ProvenanceBadge, SkeletonBlock } from "./kit";
import { EventChip, FlagChip, ImpactBadge, ModeMarker } from "./chips";
import { CHART, ChartTooltip, axisProps } from "./chart";

export function SignalDrawer() {
  const id = useOpenSignalId();
  useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeSignal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id]);

  return (
    <AnimatePresence>
      {id ? (
        <>
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-ink/10"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeSignal}
            aria-hidden="true"
          />
          <motion.aside
            key="panel"
            role="dialog"
            aria-modal="true"
            aria-label="Signal details"
            className="fixed inset-y-0 right-0 z-50 flex w-[520px] max-w-full flex-col border-l border-hairline bg-paper shadow-xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 38 }}
          >
            <DrawerBody id={id} />
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

function DrawerBody({ id }: { id: string }) {
  const q = useSignal(id);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), [id]);
  const signal = q.data?.data;
  return (
    <>
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <span className="flex items-center gap-2 text-[11px] uppercase tracking-label text-muted-foreground">
          Signal <span className="num normal-case tracking-normal">{id}</span>
        </span>
        <div className="flex items-center gap-2">
          <ProvenanceBadge source={q.data?.meta.source} />
          <button
            ref={closeRef}
            type="button"
            aria-label="Close"
            onClick={closeSignal}
            className="rounded-sm p-1 text-muted-foreground outline-none hover:bg-surface hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>
      <div data-lenis-prevent className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {q.isPending ? (
          <SkeletonBlock lines={8} />
        ) : q.isError || !signal ? (
          <ErrorCard
            error={q.error}
            endpoint={`GET /api/signals/${id}`}
            onRetry={() => void q.refetch()}
          />
        ) : (
          <SignalDetail signal={signal} />
        )}
      </div>
    </>
  );
}

function SectionTitle({ children, info }: { children: React.ReactNode; info?: string }) {
  return (
    <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-label text-muted-foreground">
      {children}
      {info ? <InfoTip text={info} /> : null}
    </h3>
  );
}

function SignalDetail({ signal }: { signal: Signal }) {
  const { tz } = useSettings();
  return (
    <>
      {/* 1. headline */}
      <section>
        <h2 className="text-[16px] font-semibold leading-snug text-foreground">
          {signal.headline}
        </h2>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <a
            href={signal.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-foreground underline-offset-2 hover:text-primary hover:underline"
          >
            {signal.sourceName} <ExternalLink className="size-3" />
          </a>
          <span className="num">
            {formatDateTime(signal.ts, tz)} {tz === "UTC" ? "UTC" : ""}
          </span>
          <span>
            {signal.entity}
            {signal.ticker ? ` · ${signal.ticker}` : ""}
          </span>
          <ModeMarker mode={signal.mode} />
        </div>
      </section>

      {/* 2. explained text */}
      <section>
        <SectionTitle info="Words that pushed the model's sentiment score. Green raised it, crimson lowered it; stronger colour = larger weight. Hover for the weight.">
          Text
        </SectionTitle>
        <ExplainedText text={signal.text} explanation={signal.explanation} />
      </section>

      {/* 3. tiles */}
      <section className="grid grid-cols-3 gap-2">
        <Tile
          label="Sentiment"
          info="Model sentiment from -1 (very negative) to +1 (very positive)."
        >
          <CountUp
            value={signal.sentiment}
            format={(n) =>
              n == null
                ? DASH
                : formatNumber(n, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                    signDisplay: "exceptZero",
                  })
            }
          />
        </Tile>
        <Tile label="Event class" info="Primary event type assigned by the classifier.">
          <div className="space-y-1">
            <EventChip type={signal.eventType} />
            {signal.secondaryEventType ? (
              <EventChip type={signal.secondaryEventType} className="opacity-70" />
            ) : null}
          </div>
        </Tile>
        <Tile
          label="Impact"
          info="Expected market impact on a 1-10 scale. Shown as — while the impact model is not live."
        >
          <div className="flex items-center gap-2">
            <CountUp value={signal.impact} format={(n) => (n == null ? DASH : n.toFixed(1))} />
            <ImpactBadge value={signal.impact} />
          </div>
        </Tile>
      </section>

      {/* 4. integrity */}
      <section>
        <SectionTitle info="How trustworthy the signal is: corroboration across independent sources and checks for manipulation patterns.">
          Integrity
        </SectionTitle>
        <div className="flex gap-4">
          <IntegrityRing score={signal.integrity.score} />
          <div className="min-w-0 flex-1 space-y-2">
            <div>
              <div className="text-[11px] text-muted-foreground">Corroborated by</div>
              {signal.integrity.corroboratedBy.length ? (
                <ul className="mt-0.5 flex flex-wrap gap-1.5">
                  {signal.integrity.corroboratedBy.map((s) => (
                    <li key={s} className="rounded-sm border border-hairline px-1.5 py-px text-xs">
                      {s}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">No other sources yet.</p>
              )}
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">Flags</div>
              {signal.integrity.flags.length ? (
                <ul className="mt-1 space-y-1.5">
                  {signal.integrity.flags.map((f) => (
                    <li key={f} className="flex flex-col gap-0.5">
                      <FlagChip flag={f} />
                      <span className="text-[11px] text-muted-foreground">
                        {FLAG_INFO[f].explain}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">No integrity flags raised.</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 5. precedent */}
      <PrecedentSection signal={signal} />

      {/* 6. book impact */}
      <BookImpact signal={signal} />
    </>
  );
}

function Tile({
  label,
  info,
  children,
}: {
  label: string;
  info: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[3px] border border-hairline p-2.5">
      <div className="mb-1.5 flex items-center gap-1 text-[11px] uppercase tracking-label text-muted-foreground">
        {label}
        <InfoTip text={info} />
      </div>
      <div className="num text-[20px] leading-none text-foreground">{children}</div>
    </div>
  );
}

function ExplainedText({
  text,
  explanation,
}: {
  text: string;
  explanation: Signal["explanation"];
}) {
  const { map, max } = useMemo(() => {
    const m = new Map<string, number>();
    let mx = 0;
    for (const e of explanation) {
      const k = e.token.toLowerCase().replace(/[^\p{L}\p{N}'-]/gu, "");
      if (!k) continue;
      m.set(k, (m.get(k) ?? 0) + e.weight);
      mx = Math.max(mx, Math.abs(e.weight));
    }
    return { map: m, max: mx };
  }, [explanation]);
  const parts = text.split(/(\s+)/);
  return (
    <p className="text-[13px] leading-relaxed text-foreground">
      {parts.map((part, i) => {
        const key = part.toLowerCase().replace(/[^\p{L}\p{N}'-]/gu, "");
        const w = key ? map.get(key) : undefined;
        if (w === undefined || max === 0) return <span key={i}>{part}</span>;
        const a = 0.18 + 0.62 * Math.min(1, Math.abs(w) / max);
        const color =
          w >= 0
            ? `color-mix(in oklch, var(--positive) ${a * 100}%, transparent)`
            : `color-mix(in oklch, var(--primary) ${a * 100}%, transparent)`;
        return (
          <mark
            key={i}
            title={`weight ${w.toFixed(3)}`}
            className="rounded-[2px] px-px text-foreground"
            style={{ background: color }}
          >
            {part}
          </mark>
        );
      })}
    </p>
  );
}

function IntegrityRing({ score }: { score: number }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const s = Math.max(0, Math.min(1, score));
  return (
    <div className="relative size-16 shrink-0" title={`Integrity score ${score.toFixed(2)}`}>
      <svg viewBox="0 0 64 64" className="size-16 -rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--hairline)" strokeWidth="5" />
        <motion.circle
          cx="32"
          cy="32"
          r={r}
          fill="none"
          stroke={
            s >= 0.7 ? "var(--positive)" : s >= 0.4 ? "var(--severity-2)" : "var(--severity-4)"
          }
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - s) }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <span className="num absolute inset-0 flex items-center justify-center text-[13px]">
        {score.toFixed(2)}
      </span>
    </div>
  );
}

function PrecedentSection({ signal }: { signal: Signal }) {
  const q = usePrecedent(signal.id);
  const go = useGo();
  const p = q.data?.data;
  const asset = pickAssetClass(p);
  const overlay = useMemo(
    () => (p && asset && p.status === "ready" ? buildOverlay(p, asset) : null),
    [p, asset],
  );
  const top3 = useMemo(
    () => (p ? [...p.analogs].sort((a, b) => b.similarity - a.similarity).slice(0, 3) : []),
    [p],
  );
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <SectionTitle info="Historical events most similar to this one and what markets did afterwards (normalised return, day 0 = event).">
          Precedent
        </SectionTitle>
        <ProvenanceBadge source={q.data?.meta.source} />
      </div>
      {q.isPending ? (
        <SkeletonBlock className="h-40" />
      ) : q.isError || !p ? (
        <ErrorCard
          error={q.error}
          endpoint={`GET /api/precedent/${signal.id}`}
          onRetry={() => void q.refetch()}
          className="min-h-24"
        />
      ) : p.status === "pending" ? (
        <EmptyState
          title="Computing precedents"
          hint="This updates automatically when the analysis is ready."
          className="min-h-24"
        />
      ) : p.status === "insufficient_data" || !overlay || !asset ? (
        <EmptyState
          title="Not enough historical analogs"
          hint={`Only n=${p.n} comparable events were found.`}
          className="min-h-24"
        />
      ) : (
        <div className="space-y-3">
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={overlay.rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="day" {...axisProps} />
                <YAxis {...axisProps} width={44} tickFormatter={(v: number) => formatPct(v, 0)} />
                <ReferenceLine y={0} stroke={CHART.grid} />
                <Area
                  dataKey="band"
                  name="p10–p90"
                  stroke="none"
                  fill={CHART.band}
                  isAnimationActive={false}
                />
                {overlay.analogs.map(({ key, analog }) => (
                  <Line
                    key={key}
                    dataKey={key}
                    name={analog.title}
                    stroke={CHART.faint}
                    strokeWidth={1}
                    dot={false}
                    isAnimationActive={false}
                    connectNulls
                  />
                ))}
                <Line
                  dataKey="median"
                  name="Median"
                  stroke={CHART.primary}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
                <RTooltip
                  cursor={{ stroke: CHART.grid }}
                  content={
                    <ChartTooltip
                      labelFormatter={(l) => `Day ${l}`}
                      valueFormatter={(v) => formatPct(v, 2, true)}
                    />
                  }
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span>{ASSET_LABEL[asset]}</span>
            <span>
              n = <span className="num text-foreground">{p.n}</span>
            </span>
            <span>
              Half-life{" "}
              <span className="num text-foreground">
                {p.halfLifeDays == null
                  ? DASH
                  : `${formatNumber(p.halfLifeDays, { maximumFractionDigits: 1 })} d`}
              </span>
            </span>
          </div>
          <ul className="space-y-1.5">
            {top3.map((a) => (
              <li key={a.eventId} className="flex items-center gap-2 text-xs">
                <span className="min-w-0 flex-1 truncate" title={a.title}>
                  {a.title}
                </span>
                <span className="num text-muted-foreground">{a.date.slice(0, 10)}</span>
                <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-surface">
                  <span
                    className="absolute inset-y-0 left-0 bg-primary"
                    style={{ width: `${Math.max(0, Math.min(1, a.similarity)) * 100}%` }}
                  />
                </span>
                <span className="num w-9 text-right">{formatPct(a.similarity, 0)}</span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => {
              closeSignal();
              go("/app/precedent", { signal: signal.id });
            }}
            className="w-full rounded-sm bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground outline-none transition-colors hover:bg-primary-hover focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Open in Precedent Lab
          </button>
        </div>
      )}
    </section>
  );
}

function BookImpact({ signal }: { signal: Signal }) {
  const q = usePortfolio();
  const rows = useMemo(() => {
    const byId = new Map((q.data?.data ?? []).map((h) => [h.id, h]));
    return signal.affectedHoldings.map((a) => ({ ...a, holding: byId.get(a.holdingId) }));
  }, [q.data, signal.affectedHoldings]);
  const total = signal.affectedHoldings.reduce((s, a) => s + a.estLoss, 0);
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <SectionTitle info="Portfolio holdings this signal is expected to affect and the estimated loss on each.">
          Book impact
        </SectionTitle>
        <div className="flex items-center gap-2">
          <ImpactBadge value={signal.bookImpact} label="Book impact" />
          <ProvenanceBadge source={q.data?.meta.source} />
        </div>
      </div>
      {signal.affectedHoldings.length === 0 ? (
        <EmptyState
          title="No holdings affected"
          hint="This signal does not map to any current holding."
          className="min-h-20"
        />
      ) : (
        <>
          <div className="mb-2 flex items-baseline justify-between text-xs">
            <span className="text-muted-foreground">Estimated loss</span>
            <span className={cn("num text-[15px]", total > 0 ? "text-primary" : "text-foreground")}>
              {formatCurrency(total)}
            </span>
          </div>
          <ul className="divide-y divide-hairline rounded-[3px] border border-hairline">
            {rows.map((r) => (
              <li key={r.holdingId} className="flex items-center gap-2 px-2.5 py-1.5 text-xs">
                <span className="min-w-0 flex-1 truncate">
                  {r.holding ? r.holding.counterparty : r.holdingId}
                  {r.holding ? (
                    <span className="text-muted-foreground">
                      {" "}
                      · {r.holding.assetType} · {r.holding.sector}
                    </span>
                  ) : null}
                </span>
                <span className="num text-primary">{formatCurrency(r.estLoss)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
