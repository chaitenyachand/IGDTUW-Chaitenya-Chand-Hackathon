import { useEffect, useRef, useState, type ReactNode } from "react";
import { animate, useReducedMotion } from "framer-motion";
import { AlertTriangle, Info, Inbox, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";
import { ApiError } from "@/api/errors";
import type { ProvenanceSource } from "@/api/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";

/* ------------------------------------------------------------ ProvenanceBadge */

const PROVENANCE: Record<ProvenanceSource, { label: string; tip: string }> = {
  live: { label: "LIVE", tip: "Computed by the live pipeline from current sources." },
  replay: { label: "REPLAY", tip: "A real archived event replayed through the live pipeline." },
  backfill: { label: "BACKFILL", tip: "Historical data processed after the fact; not real-time." },
  synthetic: {
    label: "SYNTHETIC",
    tip: "Generated data (for example a synthetic portfolio), not real positions.",
  },
};

export function ProvenanceBadge({
  source,
  className,
}: {
  source: ProvenanceSource | null | undefined;
  className?: string;
}) {
  if (!source) return null;
  const info = PROVENANCE[source] ?? PROVENANCE.synthetic;
  const dot =
    source === "live"
      ? "bg-primary"
      : source === "replay"
        ? "border border-primary bg-transparent"
        : source === "backfill"
          ? "bg-[oklch(0.7_0.006_285)]"
          : "border border-[oklch(0.62_0.006_285)] [background-image:repeating-linear-gradient(45deg,oklch(0.62_0.006_285)_0_1px,transparent_1px_2.5px)]";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-sm px-1 font-mono text-[10px] uppercase leading-none tracking-wider text-muted-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring",
            source === "live" && "text-primary",
            className,
          )}
        >
          <span className={cn("inline-block size-1.5 rounded-full", dot)} />
          {info.label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-60 text-xs">{info.tip}</TooltipContent>
    </Tooltip>
  );
}

/* -------------------------------------------------------------------- InfoTip */

export function InfoTip({ text, className }: { text: ReactNode; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Definition"
          className={cn(
            "inline-flex text-muted-foreground/70 outline-none hover:text-foreground focus-visible:text-foreground",
            className,
          )}
        >
          <Info className="size-3" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-64 text-xs leading-snug">{text}</TooltipContent>
    </Tooltip>
  );
}

/* ---------------------------------------------------------------------- Panel */

export function Panel({
  title,
  info,
  source,
  actions,
  children,
  className,
  bodyClassName,
  id,
}: {
  title: ReactNode;
  info?: ReactNode;
  source?: ProvenanceSource | null | undefined;
  actions?: ReactNode;
  children: ReactNode;
  className?: string | undefined;
  bodyClassName?: string | undefined;
  id?: string | undefined;
}) {
  return (
    <section
      id={id}
      className={cn(
        "flex min-h-0 flex-col rounded-[3px] border border-hairline bg-paper",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-hairline px-3 py-2">
        <h2 className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-label text-muted-foreground">
          {title}
          {info ? <InfoTip text={info} /> : null}
        </h2>
        <div className="flex items-center gap-2">
          {actions}
          <ProvenanceBadge source={source} />
        </div>
      </header>
      <div className={cn("min-h-0 flex-1 p-3", bodyClassName)}>{children}</div>
    </section>
  );
}

/* ---------------------------------------------------------------- Num/CountUp */

export function Num({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("num", className)}>{children}</span>;
}

/** Counts up from 0 on first render and tweens between later values. null renders "—". */
export function CountUp({
  value,
  format,
  className,
  duration = 0.9,
}: {
  value: number | null | undefined;
  format: (n: number | null) => string;
  className?: string;
  duration?: number;
}) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState<number | null>(reduce ? (value ?? null) : null);
  const prev = useRef(0);
  useEffect(() => {
    if (value == null || !Number.isFinite(value)) {
      setShown(null);
      return;
    }
    if (reduce) {
      setShown(value);
      prev.current = value;
      return;
    }
    const controls = animate(prev.current, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setShown(v),
      onComplete: () => {
        prev.current = value;
        setShown(value);
      },
    });
    return () => controls.stop();
  }, [value, duration, reduce]);
  const display = value == null || !Number.isFinite(value) ? null : (shown ?? 0);
  return <span className={cn("num", className)}>{format(display)}</span>;
}

/* ----------------------------------------------------------------------- Stat */

export function Stat({
  label,
  info,
  value,
  sub,
  className,
}: {
  label: ReactNode;
  info?: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-center gap-1 text-[11px] uppercase tracking-label text-muted-foreground">
        {label}
        {info ? <InfoTip text={info} /> : null}
      </div>
      <div className="num mt-0.5 truncate text-[20px] leading-tight text-foreground">{value}</div>
      {sub ? <div className="num mt-0.5 text-[11px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------ states: loading/empty/error */

export function SkeletonBlock({ className, lines = 0 }: { className?: string; lines?: number }) {
  if (lines > 0)
    return (
      <div className={cn("space-y-2", className)} aria-busy="true" aria-label="Loading">
        {Array.from({ length: lines }, (_, i) => (
          <Skeleton
            key={i}
            className="h-3.5 w-full"
            style={{ width: `${100 - ((i * 13) % 35)}%` }}
          />
        ))}
      </div>
    );
  return (
    <Skeleton className={cn("h-24 w-full", className)} aria-busy="true" aria-label="Loading" />
  );
}

export function EmptyState({
  title,
  hint,
  className,
  icon,
}: {
  title: string;
  hint?: string | undefined;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex min-h-32 flex-col items-center justify-center gap-1.5 px-4 py-8 text-center",
        className,
      )}
    >
      <div className="text-muted-foreground/60">{icon ?? <Inbox className="size-5" />}</div>
      <p className="text-[13px] font-medium text-foreground">{title}</p>
      {hint ? <p className="max-w-sm text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function ErrorCard({
  error,
  onRetry,
  endpoint,
  className,
}: {
  error: unknown;
  onRetry?: (() => void) | undefined;
  endpoint?: string | undefined;
  className?: string;
}) {
  const api = error instanceof ApiError ? error : null;
  const ep = api?.endpoint || endpoint || "unknown endpoint";
  const message = api?.message ?? (error instanceof Error ? error.message : "Request failed");
  return (
    <div
      role="alert"
      className={cn(
        "flex min-h-32 flex-col items-center justify-center gap-2 px-4 py-6 text-center",
        className,
      )}
    >
      <AlertTriangle className="size-5 text-primary" />
      <p className="text-[13px] font-medium text-foreground">Could not load data</p>
      <p className="num rounded-sm bg-surface px-1.5 py-0.5 text-[11px] text-foreground">{ep}</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        {message}
        {api && api.status ? ` (HTTP ${api.status}${api.code ? `, ${api.code}` : ""})` : ""}
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2.5 py-1 text-xs font-medium text-foreground outline-none transition-colors hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
        >
          <RefreshCw className="size-3" /> Retry
        </button>
      ) : null}
    </div>
  );
}

interface QLike<T> {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
  data: T | undefined;
}

/**
 * Renders skeleton -> error card (endpoint + Retry) -> empty state -> content.
 * Placeholder numbers are never rendered while loading.
 */
export function QueryBoundary<T>({
  query,
  endpoint,
  isEmpty,
  emptyTitle = "Nothing here yet",
  emptyHint,
  skeleton,
  children,
}: {
  query: QLike<T>;
  endpoint?: string | undefined;
  isEmpty?: ((data: T) => boolean) | undefined;
  emptyTitle?: string | undefined;
  emptyHint?: string;
  skeleton?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <>{skeleton ?? <SkeletonBlock lines={5} />}</>;
  if (query.isError || query.data === undefined)
    return (
      <ErrorCard error={query.error} endpoint={endpoint} onRetry={() => void query.refetch()} />
    );
  if (isEmpty?.(query.data)) return <EmptyState title={emptyTitle} hint={emptyHint} />;
  return <>{children(query.data)}</>;
}
