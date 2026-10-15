import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Pause, Play } from "lucide-react";

import { flattenSignals, useSignals } from "@/api/client";
import type { Signal } from "@/api/types";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import {
  EventChip,
  ImpactBadge,
  IntegrityDot,
  ModeMarker,
  SentimentBar,
} from "@/components/terminal/chips";
import { formatTime } from "@/lib/format";
import { openSignal } from "@/lib/drawer";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";

function Row({
  s,
  flash,
  animateIn,
  tz,
}: {
  s: Signal;
  flash: boolean;
  animateIn: boolean;
  tz: "UTC" | "local";
}) {
  return (
    <motion.li
      layout
      initial={animateIn ? { opacity: 0, y: -18 } : false}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="border-b border-hairline last:border-b-0"
    >
      <button
        type="button"
        onClick={() => openSignal(s.id)}
        aria-label={`Open signal: ${s.entity} ${s.headline}`}
        className={cn(
          "grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-3 py-1.5 text-left outline-none transition-colors hover:bg-surface focus-visible:bg-surface",
          flash && "sig-flash",
        )}
      >
        <span className="num text-[11px] text-muted-foreground">{formatTime(s.ts, tz)}</span>
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-[13px] font-medium text-foreground">{s.entity}</span>
          {s.ticker ? (
            <span className="num text-[11px] text-muted-foreground">{s.ticker}</span>
          ) : null}
          <ModeMarker mode={s.mode} />
          <EventChip type={s.eventType} className="hidden sm:inline-block" />
        </span>
        <span className="flex items-center gap-3">
          <SentimentBar value={s.sentiment} showValue={false} className="hidden md:inline-flex" />
          <ImpactBadge value={s.impact} />
          <IntegrityDot score={s.integrity.score} />
        </span>
      </button>
    </motion.li>
  );
}

export function SignalStream() {
  const q = useSignals({ limit: 50 });
  const { tz } = useSettings();
  const live = useMemo(() => flattenSignals(q.data), [q.data]);
  const [snapshot, setSnapshot] = useState<Signal[] | null>(null);
  const seen = useRef<Set<string>>(new Set());
  const flash = useRef<Set<string>>(new Set());
  const ready = useRef(false);

  // Mark ids that appear after the first batch (idempotent, safe under double render).
  if (ready.current) for (const s of live) if (!seen.current.has(s.id)) flash.current.add(s.id);
  useEffect(() => {
    if (!q.data) return;
    for (const s of live) seen.current.add(s.id);
    ready.current = true;
  }, [live, q.data]);

  const paused = snapshot !== null;
  const shown = snapshot ?? live;
  const newCount = paused ? live.filter((s) => !snapshot.some((x) => x.id === s.id)).length : 0;

  const toggle = (
    <button
      type="button"
      onClick={() => setSnapshot(paused ? null : live)}
      aria-pressed={paused}
      aria-label={paused ? "Resume live stream" : "Pause live stream"}
      className="inline-flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2 py-0.5 text-[11px] text-foreground outline-none transition-colors hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
    >
      {paused ? <Play className="size-3" /> : <Pause className="size-3" />}
      {paused ? "Resume" : "Pause"}
      {paused && newCount > 0 ? <span className="num text-primary">{newCount} new</span> : null}
    </button>
  );

  return (
    <Panel
      title="Live Signal Stream"
      info="Scored news and social items, newest first. New items arrive over the WebSocket. Impact is 1-10 (— while the impact model is not live); the dot shows integrity."
      source={q.data?.pages[0]?.meta.source}
      actions={toggle}
      className="h-full"
      bodyClassName="p-0"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/signals"
        skeleton={
          <div className="p-3">
            <SkeletonBlock lines={8} />
          </div>
        }
      >
        {() =>
          shown.length === 0 ? (
            <EmptyState
              title="Waiting for the first signals"
              hint="New items appear here as soon as the pipeline scores them."
            />
          ) : (
            <div data-lenis-prevent className="max-h-[520px] overflow-y-auto">
              <ul>
                <AnimatePresence initial={false}>
                  {shown.map((s) => {
                    const fresh = flash.current.has(s.id);
                    return <Row key={s.id} s={s} flash={fresh} animateIn={fresh} tz={tz} />;
                  })}
                </AnimatePresence>
              </ul>
              {q.hasNextPage ? (
                <div className="p-2 text-center">
                  <button
                    type="button"
                    disabled={q.isFetchingNextPage}
                    onClick={() => void q.fetchNextPage()}
                    className="rounded-sm border border-hairline px-3 py-1 text-xs text-foreground outline-none hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                  >
                    {q.isFetchingNextPage ? "Loading…" : "Load more"}
                  </button>
                </div>
              ) : null}
            </div>
          )
        }
      </QueryBoundary>
    </Panel>
  );
}
