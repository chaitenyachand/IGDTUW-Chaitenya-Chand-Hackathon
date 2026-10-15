/** Number formatting (Intl). Render the result inside an element with the `num` class (IBM Plex Mono + tabular-nums). */
export const DASH = "—";

type N = number | null | undefined;
const ok = (n: N): n is number => typeof n === "number" && Number.isFinite(n);

export function formatNumber(n: N, opts: Intl.NumberFormatOptions = {}): string {
  if (!ok(n)) return DASH;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, ...opts }).format(n);
}

export function formatCurrency(
  n: N,
  opts: { compact?: boolean; currency?: string; digits?: number } = {},
): string {
  if (!ok(n)) return DASH;
  const compact = opts.compact ?? Math.abs(n) >= 100_000;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: opts.currency ?? "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: opts.digits ?? (compact ? 2 : 0),
  }).format(n);
}

/** Input is a fraction: 0.0123 -> "1.23%". */
export function formatPct(n: N, digits = 2, signed = false): string {
  if (!ok(n)) return DASH;
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(n);
}

/** Input is a fraction: 0.0012 -> "12.0 bps". */
export function formatBps(n: N, digits = 1): string {
  if (!ok(n)) return DASH;
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n * 10_000)} bps`;
}

/** Input already in bps. */
export function formatBpsRaw(n: N, digits = 0): string {
  if (!ok(n)) return DASH;
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, signDisplay: "exceptZero" }).format(n)} bps`;
}

export function formatRelativeTime(
  iso: string | null | undefined,
  now: number = Date.now(),
): string {
  if (!iso) return DASH;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return DASH;
  const diffSec = Math.round((t - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto", style: "short" });
  const abs = Math.abs(diffSec);
  if (abs < 45) return rtf.format(diffSec, "second");
  if (abs < 45 * 60) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 22 * 3600) return rtf.format(Math.round(diffSec / 3600), "hour");
  return rtf.format(Math.round(diffSec / 86400), "day");
}

export function formatTime(
  iso: string | null | undefined,
  tz: "UTC" | "local" = "UTC",
  withSeconds = true,
): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return DASH;
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
    hour12: false,
    timeZone: tz === "UTC" ? "UTC" : undefined,
  }).format(d);
}

export function formatDateTime(
  iso: string | null | undefined,
  tz: "UTC" | "local" = "UTC",
): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return DASH;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    hour12: false,
    timeZone: tz === "UTC" ? "UTC" : undefined,
  }).format(d);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return DASH;
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" }).format(d);
}

/** Impact-style score (1..10) that may be null while the impact model is not live. */
export function formatScore(n: N, digits = 1): string {
  if (!ok(n)) return DASH;
  return n.toFixed(digits);
}
