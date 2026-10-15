import { useHealth, useModelMetrics } from "@/api/client";
import { CountUp, Panel, QueryBoundary, SkeletonBlock, Stat } from "@/components/terminal/kit";
import { DASH, formatNumber } from "@/lib/format";

const SOCIAL = /reddit|social|twitter|stocktwits|x_|telegram/i;

export function HealthStrip() {
  const hq = useHealth();
  const mq = useModelMetrics();
  const metrics = mq.data?.data;
  return (
    <Panel
      title="System Health"
      info="Pipeline status: how many news and social sources are reporting, throughput, scoring latency and the deployed model."
      source={hq.data?.meta.source}
      className="h-full"
    >
      <QueryBoundary query={hq} endpoint="GET /api/health" skeleton={<SkeletonBlock lines={4} />}>
        {({ data: h }) => {
          const social = h.sources.filter((s) => SOCIAL.test(s.name));
          const news = h.sources.filter((s) => !SOCIAL.test(s.name));
          const live = (a: typeof news) => a.filter((s) => s.status === "ok").length;
          const spm = h.documents.lastHour / 60;
          const version = h.modelVersion ?? metrics?.modelVersion ?? null;
          return (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              <Stat
                label="News live"
                info="News sources whose last poll succeeded, out of all configured news sources."
                value={
                  <>
                    <CountUp
                      value={live(news)}
                      format={(n) => formatNumber(n, { maximumFractionDigits: 0 })}
                    />
                    <span className="text-muted-foreground">/{news.length}</span>
                  </>
                }
              />
              <Stat
                label="Social live"
                info="Social sources (Reddit, X, Stocktwits, Telegram and similar) whose last poll succeeded."
                value={
                  <>
                    <CountUp
                      value={live(social)}
                      format={(n) => formatNumber(n, { maximumFractionDigits: 0 })}
                    />
                    <span className="text-muted-foreground">/{social.length}</span>
                  </>
                }
              />
              <Stat
                label="Signals / min"
                info="Documents ingested in the last hour divided by 60."
                value={
                  <CountUp
                    value={spm}
                    format={(n) =>
                      formatNumber(n, { maximumFractionDigits: 1, minimumFractionDigits: 1 })
                    }
                  />
                }
                sub={`${formatNumber(h.documents.lastHour, { maximumFractionDigits: 0 })} last hour`}
              />
              <Stat
                label="p95 latency"
                info="95th percentile time to score a document end to end."
                value={
                  mq.isPending ? (
                    <SkeletonBlock className="h-6 w-16" />
                  ) : metrics ? (
                    <CountUp
                      value={metrics.latency.p95Ms}
                      format={(n) =>
                        n == null ? DASH : `${formatNumber(n, { maximumFractionDigits: 0 })} ms`
                      }
                    />
                  ) : (
                    DASH
                  )
                }
              />
              <Stat
                className="col-span-2"
                label="Model version"
                info="Version of the sentiment, event and impact models currently scoring signals."
                value={version ?? DASH}
              />
            </div>
          );
        }}
      </QueryBoundary>
    </Panel>
  );
}
