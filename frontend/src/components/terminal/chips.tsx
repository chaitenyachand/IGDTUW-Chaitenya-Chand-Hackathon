import { cn } from "@/lib/utils";
import type { EventType, IntegrityFlag, SignalMode } from "@/api/types";
import { DASH, formatNumber, formatScore } from "@/lib/format";
import { EVENT_TYPE_HINT, FLAG_INFO, impactColor } from "@/lib/severity";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function EventChip({
  type,
  className,
}: {
  type: EventType | null | undefined;
  className?: string;
}) {
  if (!type) return <span className="num text-muted-foreground">{DASH}</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-block max-w-full truncate rounded-sm border border-hairline bg-surface px-1.5 py-px text-[11px] leading-4 text-foreground",
            className,
          )}
        >
          {type}
        </span>
      </TooltipTrigger>
      <TooltipContent className="text-xs">{EVENT_TYPE_HINT[type] ?? type}</TooltipContent>
    </Tooltip>
  );
}

/** Diverging bar for sentiment -1..1: crimson to the left, slate-green to the right. */
export function SentimentBar({
  value,
  showValue = true,
  className,
}: {
  value: number | null | undefined;
  showValue?: boolean;
  className?: string;
}) {
  const ok = value != null && Number.isFinite(value);
  const v = ok ? Math.max(-1, Math.min(1, value as number)) : 0;
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={ok ? `Sentiment ${formatNumber(v, { maximumFractionDigits: 2 })}` : "No sentiment"}
    >
      <span className="relative h-1.5 w-14 overflow-hidden rounded-full bg-surface">
        <span className="absolute inset-y-0 left-1/2 w-px bg-hairline" />
        {ok ? (
          <span
            className="absolute inset-y-0"
            style={{
              left: v < 0 ? `${50 + v * 50}%` : "50%",
              width: `${Math.abs(v) * 50}%`,
              background: v < 0 ? "var(--primary)" : "var(--positive)",
            }}
          />
        ) : null}
      </span>
      {showValue ? (
        <span className="num w-9 text-right text-[11px] text-muted-foreground">
          {ok
            ? formatNumber(v, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
                signDisplay: "exceptZero",
              })
            : DASH}
        </span>
      ) : null}
    </span>
  );
}

/** Severity badge for impact / book impact. null renders an em dash and is never coloured as 0. */
export function ImpactBadge({
  value,
  className,
  label,
}: {
  value: number | null | undefined;
  className?: string;
  label?: string;
}) {
  const isNull = value == null || !Number.isFinite(value);
  const t = isNull ? 0 : ((value as number) - 1) / 9;
  return (
    <span
      title={isNull ? "Impact model not live" : `${label ?? "Impact"} ${formatScore(value)} / 10`}
      className={cn(
        "num inline-flex h-5 min-w-8 items-center justify-center rounded-sm px-1.5 text-[11px]",
        isNull ? "bg-surface text-muted-foreground" : t >= 0.45 ? "text-white" : "text-foreground",
        className,
      )}
      style={isNull ? undefined : { background: impactColor(value) }}
    >
      {formatScore(value)}
    </span>
  );
}
export const SeverityBadge = ImpactBadge;

export function IntegrityDot({
  score,
  className,
}: {
  score: number | null | undefined;
  className?: string;
}) {
  const ok = score != null && Number.isFinite(score);
  const color = !ok
    ? "var(--hairline)"
    : (score as number) >= 0.7
      ? "var(--positive)"
      : (score as number) >= 0.4
        ? "var(--severity-2)"
        : "var(--severity-4)";
  return (
    <span
      className={cn("inline-flex items-center gap-1", className)}
      title={
        ok ? `Integrity ${formatNumber(score, { maximumFractionDigits: 2 })}` : "No integrity score"
      }
    >
      <span className="inline-block size-2 rounded-full" style={{ background: color }} />
      <span className="num text-[11px] text-muted-foreground">
        {ok ? (score as number).toFixed(2) : DASH}
      </span>
    </span>
  );
}

export function ModeMarker({ mode }: { mode: SignalMode | undefined }) {
  if (!mode || mode === "live") return null;
  return (
    <span className="num rounded-sm border border-primary/50 px-1 text-[9px] uppercase leading-3 text-primary">
      {mode}
    </span>
  );
}

export function FlagChip({ flag }: { flag: IntegrityFlag }) {
  const info = FLAG_INFO[flag];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-block rounded-sm border border-primary/40 bg-accent px-1.5 py-px text-[11px] text-primary">
          {info.label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-60 text-xs">{info.explain}</TooltipContent>
    </Tooltip>
  );
}
