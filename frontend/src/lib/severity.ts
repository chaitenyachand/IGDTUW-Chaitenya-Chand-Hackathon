import type { EventType, IntegrityFlag } from "@/api/types";

/** Severity ramp (CSS tokens defined in styles.css). Index 0 = lowest. */
export const SEVERITY_VARS = [
  "var(--severity-1)",
  "var(--severity-2)",
  "var(--severity-3)",
  "var(--severity-4)",
  "var(--severity-5)",
] as const;

/** Maps t in 0..1 to a ramp colour. null -> neutral grey (never treated as 0). */
export function rampColor(t: number | null | undefined): string {
  if (t == null || !Number.isFinite(t)) return "var(--hairline)";
  const i = Math.min(SEVERITY_VARS.length - 1, Math.max(0, Math.floor(t * SEVERITY_VARS.length)));
  return SEVERITY_VARS[i] ?? "var(--hairline)";
}

/** Impact 1..10 (or null) -> ramp colour. */
export function impactColor(impact: number | null | undefined): string {
  if (impact == null) return "var(--hairline)";
  return rampColor((impact - 1) / 9);
}

export function regimeColor(regime: "Calm" | "Elevated" | "Stressed" | undefined): string {
  if (regime === "Stressed") return "var(--severity-5)";
  if (regime === "Elevated") return "var(--severity-3)";
  if (regime === "Calm") return "var(--positive)";
  return "var(--hairline)";
}

export function riskValueColor(value: number | null | undefined): string {
  if (value == null) return "var(--hairline)";
  return rampColor(value / 100);
}

/** Total order for sorting where null always sorts last regardless of direction. */
export function compareNullable(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: "asc" | "desc",
): number {
  const an = a == null || !Number.isFinite(a);
  const bn = b == null || !Number.isFinite(b);
  if (an && bn) return 0;
  if (an) return 1;
  if (bn) return -1;
  return dir === "asc" ? (a as number) - (b as number) : (b as number) - (a as number);
}

export const FLAG_INFO: Record<IntegrityFlag, { label: string; explain: string }> = {
  single_source: {
    label: "Single source",
    explain: "Only one outlet reports this; no independent corroboration yet.",
  },
  burst: {
    label: "Burst",
    explain:
      "Unusually many near-identical items arrived at once, which can indicate coordinated amplification.",
  },
  bot_likely: { label: "Bot likely", explain: "Posting patterns resemble automated accounts." },
  divergence: {
    label: "News/social divergence",
    explain: "News and social sources disagree on the sentiment of this event.",
  },
};

/** One short definition per event type for legends/tooltips. */
export const EVENT_TYPE_HINT: Record<EventType, string> = {
  Geopolitical: "Conflict, sanctions, elections, diplomacy.",
  Macroeconomic: "Rates, inflation, growth, central bank decisions.",
  "Credit Event": "Defaults, downgrades, restructurings.",
  "Merger/Acquisition": "Deals, bids, takeovers, divestitures.",
  "Product Launch": "New products or services announced.",
  Regulatory: "New rules, fines, investigations, approvals.",
  "Supply Chain": "Disruptions to production or logistics.",
  Cyber: "Breaches, outages, ransomware.",
  "Natural Disaster": "Storms, earthquakes, floods, wildfires.",
  "Market Commentary": "Analyst or media commentary without a discrete event.",
  Earnings: "Quarterly results and guidance.",
};
