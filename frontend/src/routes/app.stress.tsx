import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";

import {
  useLastStressRun,
  usePrecedent,
  useRunStress,
  useScenarios,
  useStressRules,
} from "@/api/client";
import { AssetClassChart, DeltaBars } from "@/components/terminal/stress/breakdowns";
import { NarrativeCard } from "@/components/terminal/stress/brief";
import { BigNumbers, Waterfall } from "@/components/terminal/stress/impact-summary";
import { EmptyState, Panel } from "@/components/terminal/kit";
import { ReverseStress, TriggerRules } from "@/components/terminal/stress/rules";
import { ScenarioLibrary } from "@/components/terminal/stress/scenario-library";
import { ModeToggle, ShockPanel, type StressMode } from "@/components/terminal/stress/shock-panel";
import {
  shocksFromScenario,
  toRequestShocks,
  type ShockValues,
} from "@/components/terminal/stress/shocks";

export const Route = createFileRoute("/app/stress")({
  head: () => ({ meta: [{ title: "Stress Lab — SENTINEL Terminal" }] }),
  validateSearch: (s: Record<string, unknown>) => ({
    signal: typeof s["signal"] === "string" ? s["signal"] : undefined,
    mode:
      s["mode"] === "calibrated" || s["mode"] === "manual" ? (s["mode"] as StressMode) : undefined,
    scenario: typeof s["scenario"] === "string" ? s["scenario"] : undefined,
  }),
  component: StressLab,
});

function StressLab() {
  const search = Route.useSearch();
  const scenarios = useScenarios();
  const rules = useStressRules();
  const last = useLastStressRun();
  const run = useRunStress();
  const precedent = usePrecedent(search.signal);

  const [mode, setMode] = useState<StressMode>(
    search.mode ?? (search.signal ? "calibrated" : "manual"),
  );
  const [selectedId, setSelectedId] = useState<string | null>(search.scenario ?? null);
  const [values, setValues] = useState<ShockValues>(() => shocksFromScenario(undefined));

  const list = scenarios.data?.data;
  const selected = list?.find((s) => s.id === selectedId);
  // Default selection once scenarios load: the last run's scenario, else the first.
  useEffect(() => {
    if (!list?.length || selectedId) return;
    setSelectedId(last.data?.data.scenarioId ?? list[0]?.id ?? null);
  }, [list, selectedId, last.data]);
  useEffect(() => {
    setValues(shocksFromScenario(selected));
  }, [selected]);

  const result = last.data?.data;
  const resultSource = last.data?.meta.source;
  const resultScenario = list?.find((s) => s.id === result?.scenarioId);
  const armedRules = useMemo(() => rules.data?.data ?? [], [rules.data]);

  const runWith = (m: StressMode) => {
    if (!selectedId) return;
    if (m === "calibrated")
      run.mutate({
        scenarioId: selectedId,
        mode: "calibrated",
        ...(search.signal ? { signalId: search.signal } : {}),
      });
    else run.mutate({ scenarioId: selectedId, mode: "manual", shocks: toRequestShocks(values) });
  };
  const changeMode = (m: StressMode) => {
    setMode(m);
    runWith(m);
  };

  return (
    <div className="grid grid-cols-1 gap-3 p-4 text-[13px] lg:grid-cols-12">
      <div className="lg:col-span-3">
        <ScenarioLibrary
          scenarios={scenarios}
          rules={armedRules}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </div>

      <div className="space-y-3 lg:col-span-6">
        <Panel
          title={`Portfolio impact${resultScenario ? ` — ${resultScenario.name}` : ""}`}
          info="Value of the book before and after the shock, with the loss attributed to each risk factor."
          source={resultSource}
          actions={
            <div className="flex items-center gap-2">
              {run.isPending ? (
                <Loader2
                  className="size-3.5 animate-spin text-muted-foreground"
                  aria-label="Running"
                />
              ) : null}
              <ModeToggle mode={mode} onChange={changeMode} />
            </div>
          }
        >
          {result ? (
            <div className="space-y-4">
              <BigNumbers r={result} />
              <Waterfall r={result} />
            </div>
          ) : (
            <EmptyState
              title="Run a scenario to see the impact on the book"
              hint="Pick a scenario on the left and press Run."
            />
          )}
        </Panel>
        <ShockPanel
          mode={mode}
          values={values}
          onChange={(k, v) => setValues((p) => ({ ...p, [k]: v }))}
          precedent={precedent.data}
          signalId={search.signal}
          canRun={!!selectedId}
          running={run.isPending}
          onRun={() => runWith(mode)}
        />
      </div>

      <div className="space-y-3 lg:col-span-3">
        <Panel
          title="By asset class"
          info="Book value per asset class before and after the shock."
          source={resultSource}
        >
          {result ? (
            <AssetClassChart r={result} />
          ) : (
            <EmptyState title="Run a scenario to see the impact on the book" />
          )}
        </Panel>
        <Panel
          title="By sector"
          info="Change in value per sector (top 8 by absolute impact)."
          source={resultSource}
        >
          {result ? (
            <DeltaBars
              rows={result.bySector.map((x) => ({ name: x.sector, delta: x.delta }))}
              label="Sector impact"
            />
          ) : (
            <EmptyState title="No result yet" />
          )}
        </Panel>
        <Panel
          title="By country"
          info="Change in value per country (top 8 by absolute impact)."
          source={resultSource}
        >
          {result ? (
            <DeltaBars
              rows={result.byCountry.map((x) => ({ name: x.country, delta: x.delta }))}
              label="Country impact"
            />
          ) : (
            <EmptyState title="No result yet" />
          )}
        </Panel>
      </div>

      <div className="lg:col-span-7">
        <TriggerRules rules={rules} scenarios={list ?? []} />
      </div>
      <div className="lg:col-span-5">
        <ReverseStress />
      </div>
      <div className="lg:col-span-12">
        <NarrativeCard r={result} scenario={resultScenario} source={resultSource} />
      </div>
    </div>
  );
}
