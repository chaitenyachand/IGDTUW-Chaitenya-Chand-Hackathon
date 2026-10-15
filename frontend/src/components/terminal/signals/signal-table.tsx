import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { ArrowDown, ArrowUp } from "lucide-react";

import type { Signal } from "@/api/types";
import { formatTime } from "@/lib/format";
import { compareNullable } from "@/lib/severity";
import { cn } from "@/lib/utils";
import {
  EventChip,
  ImpactBadge,
  IntegrityDot,
  ModeMarker,
  SentimentBar,
} from "@/components/terminal/chips";
import { openSignal } from "@/lib/drawer";

export type SortKey =
  | "time"
  | "entity"
  | "headline"
  | "event"
  | "sentiment"
  | "impact"
  | "book"
  | "integrity"
  | "source";
export interface SortState {
  key: SortKey;
  dir: "asc" | "desc";
}

const ROW_H = 30;
const OVERSCAN = 8;
const COLS = "76px 150px minmax(240px,1fr) 130px 120px 60px 60px 66px 140px";

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "time", label: "Time", numeric: true },
  { key: "entity", label: "Entity", numeric: false },
  { key: "headline", label: "Headline", numeric: false },
  { key: "event", label: "Event", numeric: false },
  { key: "sentiment", label: "Sentiment", numeric: true },
  { key: "impact", label: "Impact", numeric: true },
  { key: "book", label: "Book", numeric: true },
  { key: "integrity", label: "Integrity", numeric: true },
  { key: "source", label: "Source", numeric: false },
];

export function sortSignals(rows: Signal[], sort: SortState): Signal[] {
  const num = (s: Signal): number | null => {
    switch (sort.key) {
      case "time":
        return Date.parse(s.ts);
      case "sentiment":
        return s.sentiment;
      case "impact":
        return s.impact;
      case "book":
        return s.bookImpact;
      case "integrity":
        return s.integrity.score;
      default:
        return null;
    }
  };
  const str = (s: Signal): string => {
    switch (sort.key) {
      case "entity":
        return s.entity;
      case "headline":
        return s.headline;
      case "event":
        return s.eventType;
      default:
        return s.sourceName;
    }
  };
  const numeric = COLUMNS.find((c) => c.key === sort.key)?.numeric ?? false;
  return [...rows].sort((a, b) =>
    numeric
      ? compareNullable(num(a), num(b), sort.dir)
      : sort.dir === "asc"
        ? str(a).localeCompare(str(b))
        : str(b).localeCompare(str(a)),
  );
}

export function SignalTable({
  rows,
  sort,
  onSort,
  tz,
  hasNextPage,
  isFetchingNext,
  fetchNext,
}: {
  rows: Signal[];
  sort: SortState;
  onSort: (key: SortKey) => void;
  tz: "UTC" | "local";
  hasNextPage: boolean;
  isFetchingNext: boolean;
  fetchNext: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(480);
  const [active, setActive] = useState(0);
  const activeIdx = Math.min(active, Math.max(0, rows.length - 1));

  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    setHeight(el.clientHeight || 480);
    const ro = new ResizeObserver(() => setHeight(el.clientHeight || 480));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const extra = hasNextPage ? 1 : 0;
  const total = (rows.length + extra) * ROW_H;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN);
  const end = Math.min(rows.length + extra, Math.ceil((scrollTop + height) / ROW_H) + OVERSCAN);

  useEffect(() => {
    if (hasNextPage && !isFetchingNext && end >= rows.length - 5) fetchNext();
  }, [end, rows.length, hasNextPage, isFetchingNext, fetchNext]);

  const reveal = useCallback((i: number) => {
    const el = scroller.current;
    if (!el) return;
    const top = i * ROW_H;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (top + ROW_H > el.scrollTop + el.clientHeight)
      el.scrollTop = top + ROW_H - el.clientHeight;
  }, []);

  const move = (i: number) => {
    const n = Math.max(0, Math.min(rows.length - 1, i));
    setActive(n);
    reveal(n);
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const page = Math.max(1, Math.floor(height / ROW_H) - 1);
    if (e.key === "ArrowDown") move(activeIdx + 1);
    else if (e.key === "ArrowUp") move(activeIdx - 1);
    else if (e.key === "PageDown") move(activeIdx + page);
    else if (e.key === "PageUp") move(activeIdx - page);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(rows.length - 1);
    else if (e.key === "Enter") {
      const s = rows[activeIdx];
      if (s) openSignal(s.id);
    } else return;
    e.preventDefault();
  };

  const visible = useMemo(() => rows.slice(start, Math.min(end, rows.length)), [rows, start, end]);
  const activeRow = rows[activeIdx];

  return (
    <div className="overflow-x-auto" data-lenis-prevent>
      <div role="grid" aria-label="Signals" aria-rowcount={rows.length} className="min-w-[1000px]">
        <div
          role="row"
          className="grid border-b border-hairline bg-surface/60 text-[11px] uppercase tracking-label text-muted-foreground"
          style={{ gridTemplateColumns: COLS }}
        >
          {COLUMNS.map((c) => {
            const on = sort.key === c.key;
            return (
              <div
                key={c.key}
                role="columnheader"
                aria-sort={on ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                className="px-2"
              >
                <button
                  type="button"
                  onClick={() => onSort(c.key)}
                  className={cn(
                    "inline-flex h-7 items-center gap-1 outline-none hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring",
                    on && "text-foreground",
                  )}
                >
                  {c.label}
                  {on ? (
                    sort.dir === "asc" ? (
                      <ArrowUp className="size-3" />
                    ) : (
                      <ArrowDown className="size-3" />
                    )
                  ) : null}
                </button>
              </div>
            );
          })}
        </div>
        <div
          ref={scroller}
          data-lenis-prevent
          tabIndex={0}
          role="rowgroup"
          aria-label="Signal rows. Use arrow keys to move and Enter to open."
          aria-activedescendant={activeRow ? `sig-row-${activeRow.id}` : undefined}
          onKeyDown={onKey}
          onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
          className="relative overflow-y-auto outline-none focus-visible:ring-1 focus-visible:ring-ring"
          style={{ height: "clamp(340px, calc(100vh - 330px), 900px)" }}
        >
          <div style={{ height: total, position: "relative" }}>
            {visible.map((s, k) => {
              const i = start + k;
              const isActive = i === activeIdx;
              return (
                <div
                  key={s.id}
                  id={`sig-row-${s.id}`}
                  role="row"
                  aria-rowindex={i + 1}
                  aria-selected={isActive}
                  onClick={() => {
                    setActive(i);
                    openSignal(s.id);
                  }}
                  className={cn(
                    "absolute inset-x-0 grid cursor-pointer items-center border-b border-hairline/60 text-[12px] hover:bg-surface/70",
                    isActive && "bg-accent",
                  )}
                  style={{ top: i * ROW_H, height: ROW_H, gridTemplateColumns: COLS }}
                >
                  <div role="gridcell" className="num px-2 text-muted-foreground">
                    {formatTime(s.ts, tz)}
                  </div>
                  <div role="gridcell" className="flex min-w-0 items-baseline gap-1 px-2">
                    <span className="truncate font-medium">{s.entity}</span>
                    {s.ticker ? (
                      <span className="num text-[10px] text-muted-foreground">{s.ticker}</span>
                    ) : null}
                  </div>
                  <div role="gridcell" className="truncate px-2" title={s.headline}>
                    {s.headline}
                  </div>
                  <div role="gridcell" className="min-w-0 px-2">
                    <EventChip type={s.eventType} />
                  </div>
                  <div role="gridcell" className="px-2">
                    <SentimentBar value={s.sentiment} />
                  </div>
                  <div role="gridcell" className="px-2">
                    <ImpactBadge value={s.impact} />
                  </div>
                  <div role="gridcell" className="px-2">
                    <ImpactBadge value={s.bookImpact} label="Book impact" />
                  </div>
                  <div role="gridcell" className="px-2">
                    <IntegrityDot score={s.integrity.score} />
                  </div>
                  <div role="gridcell" className="flex min-w-0 items-center gap-1 px-2">
                    <span className="truncate text-muted-foreground">{s.sourceName}</span>
                    <ModeMarker mode={s.mode} />
                  </div>
                </div>
              );
            })}
            {hasNextPage ? (
              <div
                role="row"
                className="absolute inset-x-0 flex items-center justify-center text-[11px] text-muted-foreground"
                style={{ top: rows.length * ROW_H, height: ROW_H }}
              >
                <span role="gridcell">Loading more…</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
