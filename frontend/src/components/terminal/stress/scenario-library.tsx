import { useMemo } from "react";
import { Zap } from "lucide-react";

import type { Envelope, Scenario, StressRule } from "@/api/types";
import { EVENT_TYPES } from "@/api/types";
import { cn } from "@/lib/utils";
import { Panel, QueryBoundary } from "@/components/terminal/kit";

interface Q<T> {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
  data: Envelope<T> | undefined;
}

export function ScenarioLibrary({
  scenarios,
  rules,
  selectedId,
  onSelect,
}: {
  scenarios: Q<Scenario[]>;
  rules: StressRule[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const groups = useMemo(() => {
    const m = new Map<string, Scenario[]>();
    for (const s of scenarios.data?.data ?? []) {
      const k = s.eventType ?? "General";
      m.set(k, [...(m.get(k) ?? []), s]);
    }
    const order: string[] = [...EVENT_TYPES, "General"];
    return order.filter((k) => m.has(k)).map((k) => [k, m.get(k) ?? []] as const);
  }, [scenarios.data]);
  const targeted = useMemo(
    () => new Set(rules.filter((r) => r.enabled).map((r) => r.scenarioId)),
    [rules],
  );

  return (
    <Panel
      title="Scenario library"
      info="Predefined stress scenarios grouped by the type of event that would trigger them. Pick one, then Run."
      source={scenarios.data?.meta.source}
      bodyClassName="p-0"
    >
      <QueryBoundary
        query={scenarios}
        endpoint="GET /api/stress/scenarios"
        isEmpty={(d) => d.data.length === 0}
        emptyTitle="No scenarios defined"
      >
        {() => (
          <div data-lenis-prevent className="max-h-[640px] space-y-3 overflow-y-auto p-3">
            {groups.map(([group, items]) => (
              <div key={group}>
                <div className="mb-1.5 text-[11px] uppercase tracking-label text-muted-foreground">
                  {group}
                </div>
                <div className="space-y-1.5">
                  {items.map((s) => {
                    const armed = s.armed || targeted.has(s.id);
                    const sel = s.id === selectedId;
                    return (
                      <button
                        key={s.id}
                        type="button"
                        aria-pressed={sel}
                        onClick={() => onSelect(s.id)}
                        className={cn(
                          "w-full rounded-[3px] border bg-paper p-2 text-left outline-none transition-colors hover:border-primary/60 focus-visible:ring-1 focus-visible:ring-ring",
                          sel ? "border-primary bg-accent" : "border-hairline",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-medium text-foreground">{s.name}</span>
                          {armed ? (
                            <span className="inline-flex shrink-0 items-center gap-1 rounded-sm border border-primary/50 px-1 text-[10px] uppercase leading-4 text-primary">
                              <Zap className="size-2.5" /> Auto-trigger
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {s.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </QueryBoundary>
    </Panel>
  );
}
