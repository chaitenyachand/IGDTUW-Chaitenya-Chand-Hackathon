import type { ReactNode } from "react";

/** One chart style for the whole terminal: white background, crimson primary, grey secondary, hairline grid. */
export const CHART = {
  primary: "var(--primary)",
  secondary: "oklch(0.72 0.006 285)",
  faint: "oklch(0.86 0.006 285)",
  ink: "var(--ink)",
  grid: "var(--hairline)",
  axis: "oklch(0.51 0.008 285)",
  positive: "var(--positive)",
  band: "oklch(0.55 0.217 20 / 0.10)",
} as const;

export const axisProps = {
  tick: { fontSize: 10, fill: "oklch(0.51 0.008 285)", fontFamily: "IBM Plex Mono, monospace" },
  tickLine: false,
  axisLine: { stroke: "var(--hairline)" },
} as const;

interface TipPayload {
  name?: string | number;
  value?: number | string | null;
  color?: string;
  dataKey?: string | number;
}

/** Shared tooltip for every recharts chart. */
export function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  valueFormatter,
}: {
  active?: boolean | undefined;
  payload?: TipPayload[] | undefined;
  label?: string | number | undefined;
  labelFormatter?: (l: string | number | undefined) => ReactNode;
  valueFormatter?: (v: number, name: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[3px] border border-hairline bg-paper px-2 py-1.5 text-[11px] shadow-sm">
      {label !== undefined ? (
        <div className="num mb-1 text-muted-foreground">
          {labelFormatter ? labelFormatter(label) : String(label)}
        </div>
      ) : null}
      {payload
        .filter((p) => p.value != null)
        .map((p, i) => (
          <div
            key={`${p.dataKey ?? p.name}-${i}`}
            className="flex items-center justify-between gap-4"
          >
            <span className="flex items-center gap-1.5 text-foreground">
              <span
                className="inline-block size-1.5 rounded-full"
                style={{ background: p.color }}
              />
              {p.name ?? p.dataKey}
            </span>
            <span className="num text-foreground">
              {typeof p.value === "number"
                ? valueFormatter
                  ? valueFormatter(p.value, String(p.name ?? ""))
                  : p.value.toFixed(2)
                : String(p.value)}
            </span>
          </div>
        ))}
    </div>
  );
}
