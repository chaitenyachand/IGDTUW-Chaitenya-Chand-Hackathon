import { useAlerts, useStressRules } from "@/api/client";
import type { Alert, Envelope, StressRule } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { openSignal } from "@/lib/drawer";
import { useSettings } from "@/lib/settings";
import { Panel, QueryBoundary } from "@/components/terminal/kit";

const SEV: Record<Alert["severity"], { color: string; label: string }> = {
  info: { color: "oklch(0.72 0.006 285)", label: "Info" },
  warning: { color: "var(--severity-3)", label: "Warning" },
  critical: { color: "var(--primary)", label: "Critical" },
};

export function RulesList() {
  const q = useStressRules();
  return (
    <Panel
      title="Alert rules"
      info="Conditions that auto-trigger a stress run when a matching signal arrives."
      source={q.data?.meta.source}
    >
      <p className="mb-2 text-xs text-muted-foreground">
        Alert rules are derived from Stress Lab trigger rules
      </p>
      <QueryBoundary<Envelope<StressRule[]>>
        query={q}
        endpoint="GET /api/stress/rules"
        isEmpty={(d) => d.data.length === 0}
        emptyTitle="No trigger rules defined"
      >
        {(env) => (
          <ul className="divide-y divide-hairline">
            {env.data.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-2 py-1.5 text-xs"
              >
                <span className="text-foreground">
                  IF <b className="font-medium">{r.eventType}</b> AND impact &gt;{" "}
                  <span className="num">{r.minImpact}</span>
                  {r.minIntegrity != null ? (
                    <>
                      {" "}
                      AND integrity &ge; <span className="num">{r.minIntegrity}</span>
                    </>
                  ) : null}{" "}
                  THEN run <span className="num">{r.scenarioId}</span>
                </span>
                <span className="num text-[11px] text-muted-foreground">
                  {r.enabled ? "enabled" : "disabled"} · cooldown {r.cooldownMinutes}m
                </span>
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
    </Panel>
  );
}

export function AlertFeed() {
  const q = useAlerts();
  const { tz } = useSettings();
  return (
    <Panel
      title="Alert feed"
      info="Alerts that have fired, newest first, with severity: info, warning or critical."
      source={q.data?.meta.source}
    >
      <QueryBoundary<Envelope<Alert[]>>
        query={q}
        endpoint="GET /api/alerts"
        isEmpty={(d) => d.data.length === 0}
        emptyTitle="No alerts have fired yet"
      >
        {(env) => (
          <ul data-lenis-prevent className="max-h-[520px] space-y-2 overflow-y-auto">
            {[...env.data]
              .sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))
              .map((a) => {
                const s = SEV[a.severity] ?? SEV.info;
                return (
                  <li
                    key={a.id}
                    className="rounded-[3px] border border-hairline p-2.5"
                    style={{ borderLeft: `3px solid ${s.color}` }}
                  >
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <span
                        className="uppercase tracking-label"
                        style={{ color: a.severity === "info" ? undefined : s.color }}
                      >
                        {s.label}
                      </span>
                      <span className="num text-muted-foreground">{formatDateTime(a.ts, tz)}</span>
                    </div>
                    <div className="mt-0.5 text-[13px] font-medium text-foreground">{a.title}</div>
                    <p className="text-xs text-muted-foreground">{a.message}</p>
                    {a.signalId ? (
                      <button
                        type="button"
                        onClick={() => openSignal(a.signalId)}
                        className="mt-1 text-xs text-primary underline-offset-2 outline-none hover:underline focus-visible:underline"
                      >
                        Open signal
                      </button>
                    ) : null}
                  </li>
                );
              })}
          </ul>
        )}
      </QueryBoundary>
    </Panel>
  );
}
