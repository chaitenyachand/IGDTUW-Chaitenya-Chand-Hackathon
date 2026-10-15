import type { AssetClassKey, PrecedentResult } from "@/api/types";

export const ASSET_LABEL: Record<AssetClassKey, string> = {
  equity_index: "Equity Index",
  energy: "Energy",
  financials: "Financials",
  technology: "Technology",
  health_care: "Health Care",
  industrials: "Industrials",
  utilities: "Utilities",
  staples: "Staples",
  discretionary: "Discretionary",
  communication: "Communication",
  banks: "Banks",
  long_treasury: "Long Treasury",
  mid_treasury: "Mid Treasury",
  high_yield: "High Yield",
  inv_grade: "Inv. Grade",
  dollar: "US Dollar",
  oil: "Oil",
  gold: "Gold",
  volatility: "Volatility",
};

/** First asset class that has a series, preferring `preferred`. */
export function pickAssetClass(
  p: PrecedentResult | undefined,
  preferred: AssetClassKey = "equity_index",
): AssetClassKey | null {
  if (!p) return null;
  if (p.series[preferred]) return preferred;
  const first = Object.keys(p.series)[0] as AssetClassKey | undefined;
  return first ?? null;
}

export interface OverlayRow {
  day: number;
  median: number | null;
  band: [number, number] | null;
  [analogKey: string]: number | [number, number] | null;
}

/**
 * Merges the median path, the p10-p90 band and every analog path (for one asset class) into one row per day.
 * Analogs below `minSimilarity` are dropped. Nothing is interpolated: a missing day stays null.
 */
export function buildOverlay(p: PrecedentResult, asset: AssetClassKey, minSimilarity = 0) {
  const s = p.series[asset];
  const analogs = p.analogs
    .filter((a) => a.similarity >= minSimilarity && a.paths[asset]?.length)
    .map((a) => ({ id: a.eventId, key: `a_${a.eventId}`, analog: a }));
  const days = new Set<number>();
  s?.median.forEach((m) => days.add(m.day));
  s?.band.forEach((b) => days.add(b.day));
  analogs.forEach(({ analog }) => analog.paths[asset]?.forEach((pt) => days.add(pt.day)));
  const med = new Map(s?.median.map((m) => [m.day, m.ret]));
  const band = new Map(s?.band.map((b) => [b.day, [b.p10, b.p90] as [number, number]]));
  const paths = analogs.map(({ analog, key }) => ({
    key,
    map: new Map(analog.paths[asset]?.map((pt) => [pt.day, pt.ret])),
  }));
  const rows: OverlayRow[] = [...days]
    .sort((a, b) => a - b)
    .map((day) => {
      const row: OverlayRow = { day, median: med.get(day) ?? null, band: band.get(day) ?? null };
      for (const pth of paths) row[pth.key] = pth.map.get(day) ?? null;
      return row;
    });
  return { rows, analogs };
}
