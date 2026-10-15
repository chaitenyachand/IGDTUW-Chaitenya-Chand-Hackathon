import { useModelMetrics } from "@/api/client";
import { CountUp, Panel, QueryBoundary, SkeletonBlock, Stat } from "@/components/terminal/kit";
import { formatNumber, formatPct } from "@/lib/format";

const f3 = (n: number | null) =>
  formatNumber(n, { minimumFractionDigits: 3, maximumFractionDigits: 3 });

export function MetricTiles() {
  const q = useModelMetrics();
  return (
    <Panel
      title="Model metrics"
      info="Held-out evaluation metrics of the models currently serving signals."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/model/metrics"
        skeleton={<SkeletonBlock lines={2} />}
      >
        {(env) => {
          const m = env.data;
          return (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Stat
                label="Sentiment macro-F1"
                info="Macro-averaged F1 of the sentiment classifier on held-out labelled items (1 is perfect)."
                value={<CountUp value={m.sentiment.f1} format={f3} />}
                sub={`accuracy ${formatPct(m.sentiment.accuracy, 1)}`}
              />
              <Stat
                label="Event macro-F1"
                info="F1 averaged equally over event types, so rare event classes count as much as common ones."
                value={<CountUp value={m.event.macroF1} format={f3} />}
                sub={`${m.event.labels.length} event types`}
              />
              <Stat
                label="Impact MAE"
                info="Mean absolute error of predicted impact against realised impact; lower is better."
                value={<CountUp value={m.impact.mae} format={f3} />}
                sub={`spearman ${formatNumber(m.impact.spearman, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}`}
              />
              <Stat
                label="Calibration error"
                info="Expected calibration error (ECE): average gap between stated confidence and observed accuracy; lower is better."
                value={<CountUp value={m.calibration.ece} format={f3} />}
                sub={`ece ${formatPct(m.calibration.ece, 1)}`}
              />
            </div>
          );
        }}
      </QueryBoundary>
    </Panel>
  );
}
