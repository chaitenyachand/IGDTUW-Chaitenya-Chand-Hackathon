import type { ReactNode } from "react";

import { useIndexPerformance, useRebalances } from "@/api/client";
import type { ProvenanceSource } from "@/api/types";
import {
  CountUp,
  ProvenanceBadge,
  QueryBoundary,
  SkeletonBlock,
  Stat,
} from "@/components/terminal/kit";
import { formatNumber, formatPct } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import { dayKey } from "./util";

function Tile({ source, children }: { source?: ProvenanceSource; children: ReactNode }) {
  return (
    <div className="relative rounded-[3px] border border-hairline bg-paper p-3">
      <div className="absolute right-2 top-2">
        <ProvenanceBadge source={source} />
      </div>
      {children}
    </div>
  );
}

const skel = <SkeletonBlock className="h-14" />;
const signed = (n: number | null) =>
  formatNumber(n, {
    signDisplay: "exceptZero",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export function IndexKpis() {
  const perf = useIndexPerformance();
  const rebs = useRebalances();
  const { tz } = useSettings();
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <QueryBoundary
        query={perf}
        endpoint="GET /api/index/performance"
        skeleton={skel}
        isEmpty={(e) => e.data.series.length === 0}
        emptyTitle="No performance data"
      >
        {(env) => {
          const last = env.data.series[env.data.series.length - 1];
          const diff = last ? last.tilted - last.benchmark : null;
          const s = env.meta.source;
          return (
            <>
              <Tile source={s}>
                <Stat
                  label="Index value"
                  info="Sentiment-tilted index level at the latest point of the performance series, compared with the static benchmark at the same point."
                  value={
                    <CountUp
                      value={last?.tilted}
                      format={(n) => formatNumber(n, { minimumFractionDigits: 2 })}
                    />
                  }
                  sub={`Benchmark ${formatNumber(last?.benchmark, { minimumFractionDigits: 2 })}`}
                />
              </Tile>
              <Tile source={s}>
                <Stat
                  label="Tracking difference"
                  info="Latest tilted index level minus the benchmark level (index points). The sub-line shows the annualisation-agnostic tracking error reported by the API (stats.tilted.trackingError), a different measure: the volatility of the difference."
                  value={<CountUp value={diff} format={signed} />}
                  sub={`Tracking error ${formatPct(env.data.stats.tilted.trackingError)}`}
                />
              </Tile>
              <Tile source={s}>
                <Stat
                  label="30-day turnover"
                  info="Share of the index traded by the tilted strategy (stats.tilted.turnover). Lower means fewer, calmer rebalances."
                  value={
                    <CountUp
                      value={env.data.stats.tilted.turnover}
                      format={(n) => formatPct(n, 1)}
                    />
                  }
                  sub={`Naive ${formatPct(env.data.stats.naive.turnover, 1)}`}
                />
              </Tile>
            </>
          );
        }}
      </QueryBoundary>
      <QueryBoundary query={rebs} endpoint="GET /api/index/rebalances" skeleton={skel}>
        {(env) => {
          const today = dayKey(Date.now(), tz);
          const n = env.data.filter((r) => dayKey(r.ts, tz) === today).length;
          const pending = env.data.filter((r) => r.status === "pending").length;
          return (
            <Tile source={env.meta.source}>
              <Stat
                label="Rebalances today"
                info={`Rebalance events whose timestamp falls on today's date in the ${tz === "UTC" ? "UTC" : "local"} timezone (change in settings).`}
                value={
                  <CountUp
                    value={n}
                    format={(v) => formatNumber(v, { maximumFractionDigits: 0 })}
                  />
                }
                sub={`${pending} pending approval`}
              />
            </Tile>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
