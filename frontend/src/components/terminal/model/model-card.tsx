import { AlertTriangle } from "lucide-react";

import { useModelMetrics } from "@/api/client";
import { CountUp, Panel, QueryBoundary, SkeletonBlock, Stat } from "@/components/terminal/kit";
import { formatDateTime, formatNumber, formatPct } from "@/lib/format";
import { useSettings } from "@/lib/settings";

export function ModelCard() {
  const q = useModelMetrics();
  const { tz } = useSettings();
  return (
    <Panel
      title="Model card"
      info="Provenance of the deployed models: version, training date, training data and documented limitations."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/model/metrics"
        skeleton={<SkeletonBlock lines={6} />}
      >
        {(env) => {
          const m = env.data;
          const pv = m.precedentValidation;
          return (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
              <div className="lg:col-span-3">
                <div className="text-[11px] uppercase tracking-label text-muted-foreground">
                  Name
                </div>
                <div className="mt-0.5 text-[15px] font-medium">SENTINEL signal models</div>
                <div className="num mt-2 text-[12px]">Version {m.modelVersion}</div>
                <div className="num text-[12px] text-muted-foreground">
                  Trained {formatDateTime(m.trainedAt, tz)}
                </div>
              </div>
              <div className="lg:col-span-3">
                <div className="mb-1 text-[11px] uppercase tracking-label text-muted-foreground">
                  Training data
                </div>
                {m.card.trainingData.length ? (
                  <ul className="list-disc space-y-0.5 pl-4 text-[12px]">
                    {m.card.trainingData.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">Not documented.</p>
                )}
              </div>
              <div className="lg:col-span-3">
                <div className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-label text-primary">
                  <AlertTriangle className="size-3" /> Known limitations
                </div>
                {m.card.knownLimitations.length ? (
                  <ul className="list-disc space-y-0.5 rounded-sm border border-primary/30 bg-primary/5 py-2 pl-6 pr-2 text-[12px]">
                    {m.card.knownLimitations.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">None documented.</p>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3 lg:col-span-3 lg:grid-cols-1">
                <Stat
                  label="MAE vs naive"
                  info="Precedent-engine mean absolute error relative to a naive no-change baseline; lower than 1 beats naive."
                  value={
                    <CountUp
                      value={pv.maeVsNaive}
                      format={(n) => formatNumber(n, { maximumFractionDigits: 3 })}
                    />
                  }
                />
                <Stat
                  label="Directional hit rate"
                  info="Share of precedent forecasts that called the direction of the realised move correctly."
                  value={<CountUp value={pv.directionalHitRate} format={(n) => formatPct(n, 1)} />}
                />
                <Stat
                  label="Band coverage"
                  info="Share of realised outcomes that fell inside the forecast p10-p90 band; ideally near 80%."
                  value={<CountUp value={pv.bandCoverage} format={(n) => formatPct(n, 1)} />}
                />
              </div>
            </div>
          );
        }}
      </QueryBoundary>
    </Panel>
  );
}
