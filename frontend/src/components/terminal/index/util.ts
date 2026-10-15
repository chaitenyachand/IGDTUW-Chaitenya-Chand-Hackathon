/** UI-only helpers for the Adaptive Index screen. */

/** Fixed neutral/crimson ramp picked by series index (not data). */
export function seriesColor(i: number): string {
  const crimson = i % 2 === 0;
  const l = 0.36 + ((i * 0.09) % 0.46);
  return crimson ? `oklch(${l.toFixed(3)} 0.19 20)` : `oklch(${(l + 0.04).toFixed(3)} 0.012 285)`;
}

export function fmtStamp(iso: string | undefined, tz: "UTC" | "local"): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: tz === "UTC" ? "UTC" : undefined,
  }).format(d);
}

/** YYYY-MM-DD of an instant in the chosen timezone. */
export function dayKey(iso: string | number, tz: "UTC" | "local"): string {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: tz === "UTC" ? "UTC" : undefined,
  }).format(new Date(iso));
}
