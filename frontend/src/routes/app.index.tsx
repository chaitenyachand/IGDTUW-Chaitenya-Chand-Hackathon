import { createFileRoute } from "@tanstack/react-router";

import { HealthStrip } from "@/components/terminal/command-center/health-strip";
import { Heatmap } from "@/components/terminal/command-center/heatmap";
import { PortfolioPulse } from "@/components/terminal/command-center/portfolio-pulse";
import { RiskCard } from "@/components/terminal/command-center/risk-card";
import { SignalStream } from "@/components/terminal/command-center/signal-stream";
import { TopEvents } from "@/components/terminal/command-center/top-events";

export const Route = createFileRoute("/app/")({
  head: () => ({ meta: [{ title: "Command Center — SENTINEL Terminal" }] }),
  component: CommandCenter,
});

function CommandCenter() {
  return (
    <div className="grid grid-cols-1 gap-3 p-4 text-[13px] lg:grid-cols-12">
      <div className="lg:col-span-4">
        <RiskCard />
      </div>
      <div className="lg:col-span-4">
        <PortfolioPulse />
      </div>
      <div className="lg:col-span-4">
        <HealthStrip />
      </div>
      <div className="lg:col-span-7">
        <SignalStream />
      </div>
      <div className="lg:col-span-5">
        <Heatmap />
      </div>
      <div className="lg:col-span-12">
        <TopEvents />
      </div>
    </div>
  );
}
