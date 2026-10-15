import { useConstituents, useLastStressRun, usePortfolio } from "@/api/client";
import { CountUp, Panel, QueryBoundary, SkeletonBlock, Stat } from "@/components/terminal/kit";
import { DASH, formatCurrency, formatPct } from "@/lib/format";

export function PortfolioPulse() {
  const pq = usePortfolio();
  const cq = useConstituents();
  const last = useLastStressRun();
  const stressed = last.data?.data ?? null;
  return (
    <Panel
      title="Portfolio Pulse"
      info="Current book value, the book value after the most recent stress run, and how far the adaptive index sits from its benchmark."
      source={pq.data?.meta.source}
      className="h-full"
    >
      <div className="flex flex-col gap-4">
        <QueryBoundary
          query={pq}
          endpoint="GET /api/portfolio"
          skeleton={<SkeletonBlock className="h-14" />}
        >
          {({ data }) => {
            const total = data.length ? data.reduce((s, h) => s + h.marketValue, 0) : null;
            return (
              <Stat
                label="Portfolio value"
                info="Sum of market value across all holdings."
                value={
                  <CountUp value={total} format={(n) => formatCurrency(n, { compact: true })} />
                }
                sub={`${data.length} holdings`}
              />
            );
          }}
        </QueryBoundary>
        <Stat
          label="Last stressed value"
          info="Book value after the most recent stress run in this session."
          value={
            stressed ? (
              <CountUp
                value={stressed.valueAfter}
                format={(n) => formatCurrency(n, { compact: true })}
              />
            ) : (
              DASH
            )
          }
          sub={
            stressed
              ? `${formatCurrency(stressed.valueAfter - stressed.valueBefore, { compact: true })} vs before`
              : "No stress run yet"
          }
        />
        <QueryBoundary
          query={cq}
          endpoint="GET /api/index/constituents"
          skeleton={<SkeletonBlock className="h-14" />}
        >
          {({ data }) => {
            const tilt = data.length
              ? data.reduce((s, c) => s + Math.abs(c.currentWeight - c.benchmarkWeight), 0) / 2
              : null;
            return (
              <Stat
                label="Index tilt vs benchmark"
                info="Active share: half the sum of absolute weight differences between the adaptive index and its benchmark."
                value={<CountUp value={tilt} format={(n) => formatPct(n, 2)} />}
                sub={`${data.length} constituents`}
              />
            );
          }}
        </QueryBoundary>
      </div>
    </Panel>
  );
}
