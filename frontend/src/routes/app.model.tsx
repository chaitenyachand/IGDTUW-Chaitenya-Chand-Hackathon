import { createFileRoute } from "@tanstack/react-router";

import {
  BacktestChart,
  DriftMonitor,
  LatencyHistogram,
  ReliabilityCurve,
} from "@/components/terminal/model/charts";
import { ConfusionMatrix } from "@/components/terminal/model/confusion";
import { SourceHealthTable } from "@/components/terminal/model/health-table";
import { ModelCard } from "@/components/terminal/model/model-card";
import { MetricTiles } from "@/components/terminal/model/tiles";

export const Route = createFileRoute("/app/model")({
  head: () => ({ meta: [{ title: "Model Lab — SENTINEL Terminal" }] }),
  component: ModelLab,
});

function ModelLab() {
  return (
    <div className="grid grid-cols-1 gap-3 p-4 text-[13px] lg:grid-cols-12">
      <div className="lg:col-span-12">
        <ModelCard />
      </div>
      <div className="lg:col-span-12">
        <MetricTiles />
      </div>
      <ConfusionMatrix />
      <ReliabilityCurve />
      <BacktestChart />
      <DriftMonitor />
      <LatencyHistogram />
      <SourceHealthTable />
    </div>
  );
}
