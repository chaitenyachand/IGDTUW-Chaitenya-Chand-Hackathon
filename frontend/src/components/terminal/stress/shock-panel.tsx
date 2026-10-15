import { Loader2, Play } from "lucide-react";

import type { Envelope, PrecedentResult } from "@/api/types";
import { cn } from "@/lib/utils";
import { InfoTip, Panel } from "@/components/terminal/kit";
import { Slider } from "@/components/ui/slider";
import { FACTORS, formatShock, precedentRange, type ShockValues } from "./shocks";

export type StressMode = "calibrated" | "manual";

export function ModeToggle({
  mode,
  onChange,
}: {
  mode: StressMode;
  onChange: (m: StressMode) => void;
}) {
  const opts: [StressMode, string][] = [
    ["calibrated", "Calibrated (PRECEDENT)"],
    ["manual", "Manual"],
  ];
  return (
    <div
      role="group"
      aria-label="Shock mode"
      className="inline-flex rounded-[3px] border border-hairline p-0.5"
    >
      {opts.map(([m, label]) => (
        <button
          key={m}
          type="button"
          aria-pressed={mode === m}
          onClick={() => onChange(m)}
          className={cn(
            "rounded-[2px] px-2.5 py-1 text-xs outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring",
            mode === m
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function ShockPanel({
  mode,
  values,
  onChange,
  precedent,
  signalId,
  canRun,
  running,
  onRun,
}: {
  mode: StressMode;
  values: ShockValues;
  onChange: (key: string, v: number) => void;
  precedent: Envelope<PrecedentResult> | undefined;
  signalId: string | undefined;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
}) {
  const calibrated = mode === "calibrated";
  return (
    <Panel
      title="Shock vector"
      info="The market moves applied to the book. Manual sliders start at the selected scenario's shocks; calibrated mode uses the historical shock vector from PRECEDENT."
      source={precedent?.meta.source}
      actions={
        <button
          type="button"
          disabled={!canRun || running}
          onClick={onRun}
          className="inline-flex items-center gap-1.5 rounded-sm bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground outline-none transition-opacity focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          {running ? <Loader2 className="size-3 animate-spin" /> : <Play className="size-3" />} Run
        </button>
      }
    >
      {calibrated ? (
        <p className="mb-3 text-xs text-muted-foreground">
          Calibrated mode uses the historical shock vector from PRECEDENT; switch to Manual to
          override.
          {!signalId
            ? " Open a signal in Precedent Lab and press Run in Stress Lab to calibrate."
            : null}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
        {FACTORS.map((f) => {
          const range = calibrated ? precedentRange(f, precedent?.data) : null;
          const v = values[f.key] ?? 0;
          return (
            <div key={f.key} className={cn(calibrated && "opacity-80")}>
              <div className="mb-1.5 flex items-center justify-between gap-2 text-xs">
                <span className="flex items-center gap-1 text-foreground">
                  {f.label}
                  <InfoTip text={f.info} />
                </span>
                <span className="num text-foreground">{formatShock(f, v)}</span>
              </div>
              <Slider
                aria-label={`${f.label} shock`}
                min={f.min}
                max={f.max}
                step={f.step}
                value={[v]}
                disabled={calibrated}
                onValueChange={(a) => onChange(f.key, a[0] ?? 0)}
              />
              {calibrated ? (
                <div className="num mt-1 text-[11px] text-muted-foreground">
                  p10–p90: {range ?? "—"}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
