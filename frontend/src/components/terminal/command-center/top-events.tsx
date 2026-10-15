import { useMemo } from "react";
import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";

import { flattenSignals, usePrecedent, useSignals } from "@/api/client";
import type { Signal } from "@/api/types";
import {
  EmptyState,
  Panel,
  ProvenanceBadge,
  QueryBoundary,
  SkeletonBlock,
} from "@/components/terminal/kit";
import { EventChip, ImpactBadge } from "@/components/terminal/chips";
import { CHART } from "@/components/terminal/chart";
import { openSignal } from "@/lib/drawer";
import { ASSET_LABEL, pickAssetClass } from "@/lib/precedent";
import { compareNullable } from "@/lib/severity";

function MiniPrecedent({ id }: { id: string }) {
  const q = usePrecedent(id);
  const box = "flex h-12 items-center text-[11px] text-muted-foreground";
  if (q.isPending) return <div className={box}>Computing precedent…</div>;
  if (q.isError)
    return (
      <div className={box}>
        Precedent failed.
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            void q.refetch();
          }}
          className="ml-1 text-primary underline outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          Retry
        </button>
      </div>
    );
  const p = q.data.data;
  if (p.status === "pending") return <div className={box}>Computing precedent…</div>;
  const asset = pickAssetClass(p);
  const median = asset ? p.series[asset]?.median : undefined;
  if (p.status === "insufficient_data" || !asset || !median || median.length < 2)
    return <div className={box}>Insufficient history</div>;
  return (
    <div
      className="h-12"
      title={`Median analog path, ${ASSET_LABEL[asset]}`}
      aria-label={`Precedent median path for ${ASSET_LABEL[asset]}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={median} margin={{ top: 3, right: 2, bottom: 3, left: 2 }}>
          <XAxis dataKey="day" hide />
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="ret"
            stroke={CHART.primary}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function EventCard({ s }: { s: Signal }) {
  return (
    <article
      onClick={() => openSignal(s.id)}
      className="flex cursor-pointer flex-col gap-2 rounded-[3px] border border-hairline bg-paper p-3 transition-colors hover:border-primary/60"
    >
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openSignal(s.id);
          }}
          className="min-w-0 truncate text-left text-[13px] font-medium text-foreground outline-none hover:text-primary focus-visible:text-primary"
        >
          {s.entity}
          {s.ticker ? (
            <span className="num ml-1.5 text-[11px] font-normal text-muted-foreground">
              {s.ticker}
            </span>
          ) : null}
        </button>
        <ProvenanceBadge source={s.mode} />
      </div>
      <p className="line-clamp-2 min-h-[2lh] text-xs text-muted-foreground">{s.headline}</p>
      <div className="flex items-center justify-between gap-2">
        <EventChip type={s.eventType} />
        <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
          Book impact <ImpactBadge value={s.bookImpact} label="Book impact" />
        </span>
      </div>
      <MiniPrecedent id={s.id} />
    </article>
  );
}

export function TopEvents() {
  const q = useSignals({ limit: 200 });
  const top = useMemo(
    () =>
      flattenSignals(q.data)
        .filter((s) => s.bookImpact != null)
        .sort((a, b) => compareNullable(a.bookImpact, b.bookImpact, "desc"))
        .slice(0, 5),
    [q.data],
  );
  return (
    <Panel
      title="Top 5 events by book impact"
      info="Recent signals ranked by estimated impact on the current portfolio (1-10), each with the median historical path of similar past events."
      source={q.data?.pages[0]?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/signals"
        skeleton={
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {Array.from({ length: 5 }, (_, i) => (
              <SkeletonBlock key={i} className="h-36" />
            ))}
          </div>
        }
      >
        {() =>
          top.length < 1 ? (
            <EmptyState
              title="Impact model not live — book impact unavailable"
              hint="Events will be ranked here once the impact model scores signals against the book."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {top.map((s) => (
                <EventCard key={s.id} s={s} />
              ))}
            </div>
          )
        }
      </QueryBoundary>
    </Panel>
  );
}
