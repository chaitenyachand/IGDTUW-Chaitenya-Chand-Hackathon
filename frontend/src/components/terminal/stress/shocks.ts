import type { AssetClassKey, PrecedentResult, Scenario, ScenarioShock } from "@/api/types";
import { formatBps, formatPct } from "@/lib/format";

export interface FactorDef {
  key: string;
  label: string;
  unit: "pct" | "bps";
  min: number;
  max: number;
  step: number;
  info: string;
}

/** Slider geometry is UI-only. pct sliders are in percent points; bps sliders in basis points. */
export const FACTORS: FactorDef[] = [
  {
    key: "equity",
    label: "Equity",
    unit: "pct",
    min: -50,
    max: 50,
    step: 0.5,
    info: "Percentage move in broad equity prices.",
  },
  {
    key: "rates",
    label: "Rates",
    unit: "bps",
    min: -300,
    max: 300,
    step: 5,
    info: "Parallel move in government yields, in basis points.",
  },
  {
    key: "credit_spread",
    label: "Credit spread",
    unit: "bps",
    min: -100,
    max: 800,
    step: 5,
    info: "Change in credit spreads over government yields, in basis points.",
  },
  {
    key: "fx",
    label: "FX (USD)",
    unit: "pct",
    min: -30,
    max: 30,
    step: 0.5,
    info: "Percentage move of the US dollar against a trade-weighted basket.",
  },
  {
    key: "commodities",
    label: "Commodities",
    unit: "pct",
    min: -60,
    max: 60,
    step: 0.5,
    info: "Percentage move in commodity prices (oil, gold).",
  },
  {
    key: "volatility",
    label: "Volatility",
    unit: "pct",
    min: -50,
    max: 200,
    step: 1,
    info: "Percentage change in implied volatility.",
  },
];

/** Which PRECEDENT asset classes calibrate which shock factor. */
const FACTOR_OF: Partial<Record<AssetClassKey, string>> = {
  equity_index: "equity",
  long_treasury: "rates",
  mid_treasury: "rates",
  high_yield: "credit_spread",
  inv_grade: "credit_spread",
  dollar: "fx",
  oil: "commodities",
  gold: "commodities",
  volatility: "volatility",
};

export type ShockValues = Record<string, number>;

function toDisplay(f: FactorDef, s: ScenarioShock): number {
  if (f.unit === "pct") return s.unit === "pct" ? s.value * 100 : s.value / 100;
  return s.unit === "bps" ? s.value : s.value * 10_000;
}

/** Slider start values from a scenario. A factor absent from the scenario starts at 0 (UI default). */
export function shocksFromScenario(sc: Scenario | undefined): ShockValues {
  const out: ShockValues = {};
  for (const f of FACTORS) {
    const hit = sc?.shocks.find((s) => s.factor.toLowerCase() === f.key);
    out[f.key] = hit ? Math.max(f.min, Math.min(f.max, toDisplay(f, hit))) : 0;
  }
  return out;
}

export function toRequestShocks(values: ShockValues): ScenarioShock[] {
  return FACTORS.map((f) => ({
    factor: f.key,
    value: f.unit === "pct" ? (values[f.key] ?? 0) / 100 : (values[f.key] ?? 0),
    unit: f.unit,
  }));
}

export function formatShock(f: FactorDef, v: number): string {
  return f.unit === "pct"
    ? `${v > 0 ? "+" : ""}${v.toFixed(1)}%`
    : `${v > 0 ? "+" : ""}${Math.round(v)} bps`;
}

/** p10-p90 range string for a factor from PRECEDENT, or null when unavailable. */
export function precedentRange(f: FactorDef, p: PrecedentResult | undefined): string | null {
  if (!p || p.status !== "ready") return null;
  const rows = p.shocks.filter((s) => FACTOR_OF[s.assetClass] === f.key);
  if (!rows.length) return null;
  const lo = Math.min(...rows.map((r) => r.p10));
  const hi = Math.max(...rows.map((r) => r.p90));
  const fmt = (v: number) => (f.unit === "pct" ? formatPct(v, 1, true) : formatBps(v, 0));
  return `${fmt(lo)} to ${fmt(hi)}`;
}
