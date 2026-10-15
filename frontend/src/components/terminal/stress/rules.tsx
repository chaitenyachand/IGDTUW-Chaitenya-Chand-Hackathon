import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import {
  useDeleteStressRule,
  useReverseStress,
  useUpsertStressRule,
  useWatchlist,
} from "@/api/client";
import type { Envelope, EventType, ReverseStressRow, Scenario, StressRule } from "@/api/types";
import { EVENT_TYPES } from "@/api/types";
import { formatCurrency, formatPct } from "@/lib/format";
import { CHART } from "@/components/terminal/chart";
import { EventChip } from "@/components/terminal/chips";
import { Panel, QueryBoundary } from "@/components/terminal/kit";
import { Switch } from "@/components/ui/switch";

const field =
  "h-7 rounded-sm border border-hairline bg-paper px-1.5 text-xs text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring";

function newId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
      return crypto.randomUUID();
  } catch {
    /* fall through */
  }
  return `rule-${Date.now().toString(36)}-${Math.floor(performance.now() * 1000).toString(36)}`;
}

interface RulesQ {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
  data: Envelope<StressRule[]> | undefined;
}

export function TriggerRules({ rules, scenarios }: { rules: RulesQ; scenarios: Scenario[] }) {
  const upsert = useUpsertStressRule();
  const del = useDeleteStressRule();
  const [eventType, setEventType] = useState<EventType>(EVENT_TYPES[0]);
  const [minImpact, setMinImpact] = useState("6");
  const [scenarioId, setScenarioId] = useState("");
  const [minIntegrity, setMinIntegrity] = useState("");
  const [cooldown, setCooldown] = useState("60");
  const sid = scenarioId || scenarios[0]?.id || "";
  const nameOf = (id: string) => scenarios.find((s) => s.id === id)?.name ?? id;
  const impactNum = Number(minImpact);
  const valid = sid !== "" && minImpact.trim() !== "" && Number.isFinite(impactNum);

  const add = () => {
    if (!valid) return;
    const integ = minIntegrity.trim() === "" ? null : Number(minIntegrity);
    upsert.mutate({
      id: newId(),
      eventType,
      minImpact: impactNum,
      minIntegrity: integ != null && Number.isFinite(integ) ? integ : null,
      scenarioId: sid,
      enabled: true,
      cooldownMinutes: Math.max(0, Math.round(Number(cooldown) || 0)),
    });
  };

  return (
    <Panel
      title="Trigger rules"
      info="Automation: when a signal of the chosen event type exceeds the impact threshold, the chosen scenario is run automatically against the book."
      source={rules.data?.meta.source}
    >
      <div className="mb-3 flex flex-wrap items-end gap-2 text-xs">
        <span className="pb-1.5 font-medium text-primary">IF</span>
        <label className="grid gap-0.5 text-muted-foreground">
          event type =
          <select
            aria-label="Event type"
            className={field}
            value={eventType}
            onChange={(e) => setEventType(e.target.value as EventType)}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <span className="pb-1.5 font-medium text-primary">AND</span>
        <label className="grid gap-0.5 text-muted-foreground">
          impact &gt;
          <input
            aria-label="Minimum impact"
            type="number"
            min={1}
            max={10}
            step={0.5}
            className={`${field} w-16 num`}
            value={minImpact}
            onChange={(e) => setMinImpact(e.target.value)}
          />
        </label>
        <span className="pb-1.5 font-medium text-primary">THEN run</span>
        <label className="grid gap-0.5 text-muted-foreground">
          scenario
          <select
            aria-label="Scenario"
            className={`${field} max-w-44`}
            value={sid}
            onChange={(e) => setScenarioId(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-0.5 text-muted-foreground">
          min integrity (opt.)
          <input
            aria-label="Minimum integrity"
            type="number"
            min={0}
            max={1}
            step={0.05}
            className={`${field} w-20 num`}
            value={minIntegrity}
            onChange={(e) => setMinIntegrity(e.target.value)}
          />
        </label>
        <label className="grid gap-0.5 text-muted-foreground">
          cooldown min
          <input
            aria-label="Cooldown minutes"
            type="number"
            min={0}
            step={5}
            className={`${field} w-20 num`}
            value={cooldown}
            onChange={(e) => setCooldown(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={!valid || upsert.isPending}
          onClick={add}
          className="inline-flex h-7 items-center gap-1 rounded-sm bg-primary px-2.5 text-xs font-medium text-primary-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          <Plus className="size-3" /> Add rule
        </button>
      </div>
      <QueryBoundary
        query={rules}
        endpoint="GET /api/stress/rules"
        isEmpty={(d) => d.data.length === 0}
        emptyTitle="No trigger rules armed"
        emptyHint="Add a rule above to auto-run a scenario when a matching signal arrives."
      >
        {(d) => (
          <ul className="divide-y divide-hairline border-t border-hairline">
            {d.data.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="text-muted-foreground">IF</span> <EventChip type={r.eventType} />
                  <span className="text-muted-foreground">AND impact &gt;</span>{" "}
                  <span className="num">{r.minImpact}</span>
                  {r.minIntegrity != null ? (
                    <>
                      <span className="text-muted-foreground">integrity ≥</span>{" "}
                      <span className="num">{r.minIntegrity}</span>
                    </>
                  ) : null}
                  <span className="text-muted-foreground">THEN run</span>{" "}
                  <span className="font-medium">{nameOf(r.scenarioId)}</span>
                  <span className="num text-muted-foreground">(cooldown {r.cooldownMinutes}m)</span>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    aria-label={`${r.enabled ? "Disable" : "Enable"} rule for ${r.eventType}`}
                    checked={r.enabled}
                    disabled={upsert.isPending}
                    onCheckedChange={(v) => upsert.mutate({ ...r, enabled: v })}
                  />
                  <button
                    type="button"
                    aria-label={`Delete rule for ${r.eventType}`}
                    disabled={del.isPending}
                    onClick={() => del.mutate(r.id)}
                    className="rounded-sm p-1 text-muted-foreground outline-none hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
    </Panel>
  );
}

export function ReverseStress() {
  const q = useReverseStress();
  const watch = useWatchlist();
  const rows = [...(q.data?.data ?? [])].sort((a, b) => b.loss - a.loss);
  const maxPct = Math.max(0, ...rows.map((r) => Math.abs(r.lossPct)));
  return (
    <Panel
      title="Reverse stress test"
      info="Starts from the loss and works backwards: which event types would hurt this portfolio the most, ranked by estimated loss."
      source={q.data?.meta.source}
    >
      <QueryBoundary<Envelope<ReverseStressRow[]>>
        query={q}
        endpoint="GET /api/stress/reverse"
        isEmpty={(d) => d.data.length === 0}
        emptyTitle="No reverse stress results yet"
      >
        {() => (
          <div data-lenis-prevent className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-label text-muted-foreground">
                <tr>
                  <th className="py-1 pr-2 font-medium">#</th>
                  <th className="py-1 pr-2 font-medium">Event type</th>
                  <th className="py-1 pr-2 text-right font-medium">Loss</th>
                  <th className="min-w-28 py-1 pr-2 font-medium">% of book</th>
                  <th className="py-1 font-medium">
                    <span className="sr-only">Watchlist</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.eventType} className="border-t border-hairline">
                    <td className="num py-1.5 pr-2 text-muted-foreground">{i + 1}</td>
                    <td className="py-1.5 pr-2">
                      <EventChip type={r.eventType} />
                    </td>
                    <td className="num py-1.5 pr-2 text-right">{formatCurrency(r.loss)}</td>
                    <td className="py-1.5 pr-2">
                      <span className="flex items-center gap-2">
                        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
                          <span
                            className="block h-full"
                            style={{
                              width: `${maxPct > 0 ? (Math.abs(r.lossPct) / maxPct) * 100 : 0}%`,
                              background: CHART.primary,
                            }}
                          />
                        </span>
                        <span className="num w-14 text-right text-muted-foreground">
                          {formatPct(r.lossPct, 1)}
                        </span>
                      </span>
                    </td>
                    <td className="py-1.5 text-right">
                      <button
                        type="button"
                        aria-pressed={r.onWatchlist}
                        disabled={watch.isPending}
                        onClick={() =>
                          watch.mutate({ eventType: r.eventType, onWatchlist: !r.onWatchlist })
                        }
                        className={`rounded-sm border px-2 py-0.5 text-[11px] outline-none focus-visible:ring-1 focus-visible:ring-ring ${r.onWatchlist ? "border-primary text-primary" : "border-hairline text-foreground hover:border-primary"}`}
                      >
                        {r.onWatchlist ? "On watchlist" : "Add to watchlist"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryBoundary>
    </Panel>
  );
}
