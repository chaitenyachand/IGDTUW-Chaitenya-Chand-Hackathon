import { useEffect, useState, type ReactNode } from "react";

import { useIndexConfig, useSaveIndexConfig } from "@/api/client";
import type { IndexConfig } from "@/api/types";
import { InfoTip, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { formatNumber, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function Field({
  label,
  info,
  value,
  children,
}: {
  label: string;
  info: string;
  value: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[12px]">
        <span className="flex items-center gap-1 text-muted-foreground">
          {label}
          <InfoTip text={info} />
        </span>
        <span className="num text-foreground">{value}</span>
      </div>
      {children}
    </div>
  );
}

function Toggle({
  id,
  label,
  info,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  info: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label htmlFor={id} className="flex items-center gap-1 text-[12px] text-foreground">
        {label}
        <InfoTip text={info} />
      </label>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function Form({ server }: { server: IndexConfig }) {
  const save = useSaveIndexConfig();
  const [cfg, setCfg] = useState<IndexConfig>(server);
  const sig = JSON.stringify(server);
  useEffect(() => setCfg(server), [sig]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = <K extends keyof IndexConfig>(k: K, v: IndexConfig[K]) =>
    setCfg((c) => ({ ...c, [k]: v }));
  const invalid = cfg.minWeight > cfg.maxWeight;
  const dirty = JSON.stringify(cfg) !== sig;
  const pct = (k: "maxWeight" | "minWeight" | "maxTurnover", max: number) => (
    <Slider
      aria-label={k}
      min={0}
      max={max}
      step={0.5}
      value={[Math.round(cfg[k] * 1000) / 10]}
      onValueChange={(v) => set(k, (v[0] ?? 0) / 100)}
    />
  );
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid) save.mutate(cfg);
      }}
    >
      <div>
        <div className="mb-1 flex items-center gap-1 text-[12px] text-muted-foreground">
          Rebalance mode
          <InfoTip text="Auto applies rebalances immediately. PM approval holds each rebalance as pending until approved in the log." />
        </div>
        <div
          role="group"
          aria-label="Rebalance mode"
          className="inline-flex overflow-hidden rounded-sm border border-hairline"
        >
          {(
            [
              ["auto", "Auto"],
              ["approval", "PM approval"],
            ] as const
          ).map(([v, l]) => (
            <button
              key={v}
              type="button"
              aria-pressed={cfg.mode === v}
              onClick={() => set("mode", v)}
              className={cn(
                "px-3 py-1 text-xs font-medium outline-none focus-visible:ring-1 focus-visible:ring-ring",
                cfg.mode === v
                  ? "bg-primary text-primary-foreground"
                  : "bg-paper text-foreground hover:bg-surface",
              )}
            >
              {l}
            </button>
          ))}
        </div>
      </div>
      <Field
        label="Max weight cap"
        info="Upper bound on any single constituent's weight."
        value={formatPct(cfg.maxWeight, 1)}
      >
        {pct("maxWeight", 100)}
      </Field>
      <Field
        label="Min weight"
        info="Lower bound on any single constituent's weight. Must not exceed the max weight."
        value={formatPct(cfg.minWeight, 1)}
      >
        {pct("minWeight", 100)}
      </Field>
      {invalid ? (
        <p role="alert" className="text-[11px] text-primary">
          Min weight must be less than or equal to max weight.
        </p>
      ) : null}
      <Field
        label="Max turnover per rebalance"
        info="Cap on the share of the index that may be traded in one rebalance."
        value={formatPct(cfg.maxTurnover, 1)}
      >
        {pct("maxTurnover", 100)}
      </Field>
      <Field
        label="Sentiment threshold"
        info="Minimum absolute sentiment (0..1) before a signal can trigger a rebalance."
        value={formatNumber(cfg.sentimentThreshold, { minimumFractionDigits: 2 })}
      >
        <Slider
          aria-label="Sentiment threshold"
          min={0}
          max={1}
          step={0.01}
          value={[cfg.sentimentThreshold]}
          onValueChange={(v) => set("sentimentThreshold", v[0] ?? 0)}
        />
      </Field>
      <Toggle
        id="cfg-corr"
        label="Require corroboration"
        info="Only act on signals confirmed by more than one independent source."
        checked={cfg.requireCorroboration}
        onChange={(v) => set("requireCorroboration", v)}
      />
      <Toggle
        id="cfg-decay"
        label="Signal decay"
        info="Fade the effect of a signal over its half-life instead of holding the tilt indefinitely."
        checked={cfg.decay}
        onChange={(v) => set("decay", v)}
      />
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={invalid || !dirty || save.isPending}
          className="rounded-sm border border-primary bg-primary px-3 py-1 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : "Save configuration"}
        </button>
        <button
          type="button"
          disabled={!dirty}
          onClick={() => setCfg(server)}
          className="text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:underline disabled:opacity-40"
        >
          Reset
        </button>
      </div>
    </form>
  );
}

export function ConfigPanel() {
  const q = useIndexConfig();
  return (
    <Panel
      title="Index configuration"
      info="Rules that govern how sentiment tilts the index. Saving applies them on the server and refreshes the charts."
      source={q.data?.meta.source}
    >
      <QueryBoundary
        query={q}
        endpoint="GET /api/index/config"
        skeleton={<SkeletonBlock lines={8} />}
      >
        {(env) => <Form server={env.data} />}
      </QueryBoundary>
    </Panel>
  );
}
