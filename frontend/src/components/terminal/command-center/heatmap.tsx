import { useEffect, useMemo, useState } from "react";

import { flattenSignals } from "@/api/client";
import { EVENT_TYPES } from "@/api/types";
import type { Signal } from "@/api/types";
import { Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { formatNumber, formatTime } from "@/lib/format";
import { rampColor, SEVERITY_VARS } from "@/lib/severity";
import { useSettings } from "@/lib/settings";
import { useSignals } from "@/api/client";

const HOUR = 3_600_000;
const COLS = 24;

interface Cell {
  count: number;
  sum: number;
  n: number;
}

export function buildGrid(signals: Signal[], now: number) {
  const grid = new Map<string, Cell>();
  for (const s of signals) {
    const t = Date.parse(s.ts);
    if (Number.isNaN(t)) continue;
    const ago = Math.max(0, Math.floor((now - t) / HOUR));
    if (ago >= COLS) continue;
    const key = `${s.eventType}|${COLS - 1 - ago}`;
    const c = grid.get(key) ?? { count: 0, sum: 0, n: 0 };
    c.count += 1;
    if (s.impact != null && Number.isFinite(s.impact)) {
      c.sum += s.impact;
      c.n += 1;
    }
    grid.set(key, c);
  }
  return grid;
}

export function Heatmap() {
  const q = useSignals({ limit: 200 });
  const { tz } = useSettings();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);
  const signals = useMemo(() => flattenSignals(q.data), [q.data]);
  const grid = useMemo(() => buildGrid(signals, now), [signals, now]);
  const label = (col: number) =>
    formatTime(new Date(now - (COLS - 1 - col) * HOUR).toISOString(), tz, false);

  return (
    <Panel
      title="Event Heatmap"
      info="Event type by hour for the last 24 hours. Colour is the mean impact (1-10) of scored signals in that hour. Grey = signals exist but the impact model is not live. Blank = no signals."
      source={q.data?.pages[0]?.meta.source}
      className="h-full"
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/signals"
        skeleton={<SkeletonBlock className="h-64" />}
      >
        {() => (
          <div>
            <div data-lenis-prevent className="overflow-x-auto">
              <div className="min-w-[420px]">
                {EVENT_TYPES.map((type) => (
                  <div
                    key={type}
                    className="grid items-center gap-px"
                    style={{ gridTemplateColumns: `96px repeat(${COLS}, minmax(0, 1fr))` }}
                  >
                    <span className="truncate pr-2 text-[11px] text-muted-foreground" title={type}>
                      {type}
                    </span>
                    {Array.from({ length: COLS }, (_, col) => {
                      const c = grid.get(`${type}|${col}`);
                      const mean = c && c.n > 0 ? c.sum / c.n : null;
                      const tip = !c
                        ? `${type}, ${label(col)}: no signals`
                        : mean == null
                          ? `${type}, ${label(col)}: ${c.count} signals, impact model not live`
                          : `${type}, ${label(col)}: ${c.count} signals, mean impact ${formatNumber(mean, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}`;
                      return (
                        <span
                          key={col}
                          title={tip}
                          aria-label={tip}
                          className="my-px block h-4 rounded-[1px] border border-hairline"
                          style={
                            c
                              ? {
                                  background:
                                    mean == null ? "var(--hairline)" : rampColor((mean - 1) / 9),
                                  borderColor: "transparent",
                                }
                              : undefined
                          }
                        />
                      );
                    })}
                  </div>
                ))}
                <div
                  className="grid gap-px pt-1"
                  style={{ gridTemplateColumns: `96px repeat(${COLS}, minmax(0, 1fr))` }}
                >
                  <span />
                  {Array.from({ length: COLS }, (_, col) => (
                    <span key={col} className="num text-center text-[9px] text-muted-foreground">
                      {col % 6 === 0 ? label(col).slice(0, 2) : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                Low
                <span className="inline-flex">
                  {SEVERITY_VARS.map((c) => (
                    <span key={c} className="block h-2 w-5" style={{ background: c }} />
                  ))}
                </span>
                High
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="block size-2.5 rounded-[1px]"
                  style={{ background: "var(--hairline)" }}
                />
                — impact model not live
              </span>
              <span className="num">
                {signals.length} recent signals, hours in {tz === "UTC" ? "UTC" : "local time"}
              </span>
            </div>
          </div>
        )}
      </QueryBoundary>
    </Panel>
  );
}
