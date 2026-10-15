import { createFileRoute } from "@tanstack/react-router";

import { ConfigPanel } from "@/components/terminal/index/config-panel";
import { ConstituentsPanel } from "@/components/terminal/index/constituents";
import { IndexKpis } from "@/components/terminal/index/kpis";
import { PerformancePanel } from "@/components/terminal/index/performance";
import { RebalanceLog } from "@/components/terminal/index/rebalance-log";
import { WeightsChart } from "@/components/terminal/index/weights-chart";

export const Route = createFileRoute("/app/adaptive-index")({
  head: () => ({ meta: [{ title: "Adaptive Index — SENTINEL Terminal" }] }),
  component: AdaptiveIndex,
});

function AdaptiveIndex() {
  return (
    <div className="space-y-3 p-4 text-[13px]">
      <IndexKpis />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <div className="space-y-3 lg:col-span-8">
          <WeightsChart />
          <PerformancePanel />
        </div>
        <div className="lg:col-span-4">
          <ConfigPanel />
        </div>
        <div className="lg:col-span-7">
          <ConstituentsPanel />
        </div>
        <div className="lg:col-span-5">
          <RebalanceLog />
        </div>
      </div>
    </div>
  );
}
