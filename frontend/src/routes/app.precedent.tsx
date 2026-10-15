import { createFileRoute } from "@tanstack/react-router";

import { usePrecedent } from "@/api/client";
import { useGo } from "@/lib/nav";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { PrecedentView } from "@/components/terminal/precedent/precedent-view";
import { SignalRail, useRail } from "@/components/terminal/precedent/signal-rail";

export const Route = createFileRoute("/app/precedent")({
  head: () => ({ meta: [{ title: "Precedent Lab — SENTINEL Terminal" }] }),
  validateSearch: (s: Record<string, unknown>) => ({
    signal: typeof s["signal"] === "string" ? s["signal"] : undefined,
  }),
  component: PrecedentLab,
});

function PrecedentLab() {
  const go = useGo();
  const search = Route.useSearch();
  const rail = useRail();
  const selectedId = search.signal ?? rail.rows[0]?.id;
  const query = usePrecedent(selectedId);

  return (
    <div className="grid grid-cols-1 gap-5 p-4 text-[13px] lg:grid-cols-[280px_minmax(0,1fr)] lg:p-6">
      <aside>
        <SignalRail
          rail={rail}
          selectedId={selectedId}
          onSelect={(id) => go("/app/precedent", { signal: id })}
        />
      </aside>
      <main className="min-w-0">
        {!selectedId ? (
          <Panel title="Precedent Lab" info="Historical analogs for a selected signal.">
            <EmptyState
              title="Select a signal"
              hint="Pick a signal from the list to compare it with similar past events."
              className="py-16"
            />
          </Panel>
        ) : (
          <QueryBoundary
            query={query}
            endpoint="GET /api/precedent/{signalId}"
            skeleton={
              <Panel title="Precedent Lab" info="Historical analogs for a selected signal.">
                <SkeletonBlock className="h-96" />
              </Panel>
            }
          >
            {(env) =>
              env.data.status === "pending" ? (
                <Panel
                  title="Precedent Lab"
                  info="Historical analogs for a selected signal."
                  source={env.meta.source}
                >
                  <EmptyState
                    title="Computing precedents…"
                    hint="This updates automatically when the analysis is ready."
                    className="py-16"
                  />
                </Panel>
              ) : env.data.status === "insufficient_data" ? (
                <Panel
                  title="Precedent Lab"
                  info="Historical analogs for a selected signal."
                  source={env.meta.source}
                >
                  <EmptyState
                    title="Insufficient historical data"
                    hint={`Only n = ${env.data.n} comparable past events were found, too few for a calibrated view.`}
                    className="py-16"
                  />
                </Panel>
              ) : (
                <PrecedentView
                  env={env}
                  onRun={() => go("/app/stress", { signal: selectedId, mode: "calibrated" })}
                />
              )
            }
          </QueryBoundary>
        )}
      </main>
    </div>
  );
}
