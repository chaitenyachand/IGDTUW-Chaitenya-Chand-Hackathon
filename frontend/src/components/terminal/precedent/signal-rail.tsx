import { useMemo } from "react";

import { flattenSignals, useSignals } from "@/api/client";
import { formatRelativeTime } from "@/lib/format";
import { compareNullable } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { ImpactBadge, ModeMarker } from "@/components/terminal/chips";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import type { Signal } from "@/api/types";

/** Ranks the rail: impact desc when any impact exists, otherwise newest first. */
export function rankRail(all: Signal[]): { rows: Signal[]; impactLive: boolean } {
  const withImpact = all.filter((s) => s.impact != null);
  if (withImpact.length === 0) {
    return {
      rows: [...all].sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts)).slice(0, 25),
      impactLive: false,
    };
  }
  return {
    rows: withImpact.sort((a, b) => compareNullable(a.impact, b.impact, "desc")).slice(0, 25),
    impactLive: true,
  };
}

export function useRail() {
  const q = useSignals({ limit: 50 });
  const rail = useMemo(() => rankRail(flattenSignals(q.data)), [q.data]);
  return { q, ...rail };
}

export function SignalRail({
  rail,
  selectedId,
  onSelect,
}: {
  rail: ReturnType<typeof useRail>;
  selectedId: string | undefined;
  onSelect: (id: string) => void;
}) {
  const { q, rows, impactLive } = rail;
  return (
    <Panel
      title="High-impact signals"
      info="Recent signals ranked by model impact (1 to 10). Pick one to see how similar historical events played out."
      source={q.data?.pages[0]?.meta.source}
      className="lg:sticky lg:top-4"
      bodyClassName="p-0"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/signals"
        skeleton={<SkeletonBlock lines={8} className="p-3" />}
        isEmpty={() => rows.length === 0}
        emptyTitle="No signals yet"
        emptyHint="Signals appear here as they are scored."
      >
        {() => (
          <>
            {!impactLive ? (
              <EmptyState
                title="Impact model not live — no high-impact signals to rank"
                hint="Showing the most recent signals instead."
                className="min-h-0 border-b border-hairline py-4"
              />
            ) : null}
            <ul
              data-lenis-prevent
              className="max-h-[calc(100vh-220px)] divide-y divide-hairline overflow-y-auto"
            >
              {rows.map((s) => {
                const on = s.id === selectedId;
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      aria-current={on ? "true" : undefined}
                      onClick={() => onSelect(s.id)}
                      className={cn(
                        "block w-full border-l-2 px-3 py-2 text-left outline-none transition-colors hover:bg-surface/70 focus-visible:bg-surface",
                        on ? "border-l-primary bg-accent" : "border-l-transparent",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <ImpactBadge value={s.impact} />
                        <span className="min-w-0 flex-1 truncate text-[12px] font-medium">
                          {s.entity}
                        </span>
                        <ModeMarker mode={s.mode} />
                        <span className="num text-[10px] text-muted-foreground">
                          {formatRelativeTime(s.ts)}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[12px] leading-snug text-muted-foreground">
                        {s.headline}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </QueryBoundary>
    </Panel>
  );
}
