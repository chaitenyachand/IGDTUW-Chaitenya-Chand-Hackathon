import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Rocket, Search, Settings, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import { API_BASE_URL, WS_URL, isBackendConfigured } from "@/api/config";
import {
  flattenSignals,
  useConstituents,
  useDemoScenarios,
  useHealth,
  useInjectDemo,
  useRiskIndex,
  useSignals,
} from "@/api/client";
import { useLiveSignals, useWsStatus } from "@/api/ws";
import { updateSettings, useSettings } from "@/lib/settings";
import { openSignal } from "@/lib/drawer";
import { useGo } from "@/lib/nav";
import { regimeColor } from "@/lib/severity";
import { formatDateTime, formatNumber } from "@/lib/format";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider, Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NAV } from "./nav";
import { EmptyState, ErrorCard, InfoTip, SkeletonBlock } from "./kit";
import { SignalDrawer } from "./signal-drawer";

/* ------------------------------------------------------------ not configured */

export function BackendNotConfigured() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="max-w-md rounded-[3px] border border-hairline p-6 text-center">
        <ShieldAlert className="mx-auto size-6 text-primary" />
        <h1 className="mt-3 text-[18px] font-semibold text-foreground">Backend not configured</h1>
        <p className="mt-2 text-[13px] text-muted-foreground">
          The terminal only shows real data. Set these environment variables in{" "}
          <span className="num">frontend/.env</span> and restart the dev server:
        </p>
        <pre className="num mt-3 rounded-sm bg-surface p-3 text-left text-[12px] text-foreground">
          {`VITE_API_BASE_URL=https://your-api-host
VITE_WS_URL=wss://your-api-host/ws/signals`}
        </pre>
        <p className="mt-3 text-xs text-muted-foreground">
          See <span className="num">src/api/CONTRACT.md</span> for the endpoints the backend must
          serve.
        </p>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------- hotkeys */

function useHotkeys(openPalette: () => void, toggleDemo: () => void) {
  const go = useGo();
  useEffect(() => {
    let gPending = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.tagName === "SELECT" ||
          t.isContentEditable)
      )
        return;
      const k = e.key.toLowerCase();
      if (gPending) {
        gPending = false;
        if (timer) clearTimeout(timer);
        const item = NAV.find((n) => n.key === k);
        if (item) {
          e.preventDefault();
          go(item.to);
        }
        return;
      }
      if (k === "g") {
        gPending = true;
        timer = setTimeout(() => (gPending = false), 1200);
      } else if (k === "d") {
        e.preventDefault();
        toggleDemo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (timer) clearTimeout(timer);
    };
  }, [go, openPalette, toggleDemo]);
}

/* --------------------------------------------------------------------- rail */

function Rail() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      aria-label="Terminal"
      className="no-print group absolute inset-y-0 left-0 z-30 flex w-16 flex-col overflow-hidden border-r border-hairline bg-paper py-2 transition-[width] duration-200 hover:w-[220px] focus-within:w-[220px]"
    >
      {NAV.map((item) => {
        const active = item.exact
          ? path === item.to || path === `${item.to}/`
          : path.startsWith(item.to);
        const Icon = item.icon;
        return (
          <Link
            key={item.to}
            to={item.to as never}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex h-10 items-center gap-3 whitespace-nowrap px-[22px] text-[13px] outline-none transition-colors focus-visible:bg-surface focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring",
              active
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:bg-surface hover:text-foreground",
            )}
          >
            {active ? <span className="absolute inset-y-1 left-0 w-0.5 bg-primary" /> : null}
            <Icon className="size-[18px] shrink-0" />
            <span className="flex-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
              {item.label}
            </span>
            <span className="num text-[10px] uppercase text-muted-foreground/70 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
              G {item.key}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

/* ------------------------------------------------------------------- top bar */

function WsIndicator() {
  const status = useWsStatus();
  const label = !WS_URL
    ? "NO WS"
    : status === "live"
      ? "LIVE"
      : status === "connecting"
        ? "CONNECTING"
        : "RECONNECTING";
  const tip = !WS_URL
    ? "VITE_WS_URL is not set, so live push is off. Data refreshes by polling and on focus."
    : status === "live"
      ? "WebSocket connected. New signals arrive in real time."
      : "Trying to (re)connect. Missed events are replayed once the connection returns.";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="num inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground"
          tabIndex={0}
        >
          <span
            className={cn(
              "inline-block size-1.5 rounded-full",
              status === "live" && WS_URL
                ? "animate-pulse bg-primary"
                : "bg-[oklch(0.7_0.006_285)]",
            )}
          />
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-60 text-xs">{tip}</TooltipContent>
    </Tooltip>
  );
}

function RiskChip() {
  const q = useRiskIndex();
  const r = q.data?.data;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className="inline-flex h-7 items-center gap-2 rounded-sm border border-hairline px-2 text-[12px]"
          aria-label="Global Risk Index"
        >
          <span className="text-[10px] uppercase tracking-label text-muted-foreground">GRI</span>
          {r ? (
            <>
              <span className="num font-medium text-foreground">
                {formatNumber(r.value, { maximumFractionDigits: 0 })}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px]">
                <span
                  className="inline-block size-2 rounded-full"
                  style={{ background: regimeColor(r.regime) }}
                />
                {r.regime}
              </span>
            </>
          ) : q.isError ? (
            <span className="num text-muted-foreground">ERR</span>
          ) : (
            <span className="num text-muted-foreground">—</span>
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-64 text-xs">
        Global Risk Index (0–100): aggregate signal impact across the market. Regimes: Calm,
        Elevated, Stressed. Updates live over the WebSocket.
      </TooltipContent>
    </Tooltip>
  );
}

function TopBar({ onPalette, onSettings }: { onPalette: () => void; onSettings: () => void }) {
  const { tz } = useSettings();
  return (
    <header className="no-print relative z-40 flex h-11 shrink-0 items-center gap-3 border-b border-hairline bg-paper pr-3">
      <div className="flex h-full w-16 items-center justify-center border-r border-hairline">
        <span className="font-mono text-[11px] font-medium tracking-[0.2em] text-primary">
          SNTL
        </span>
      </div>
      <button
        type="button"
        onClick={onPalette}
        className="flex h-7 w-72 max-w-[40%] items-center gap-2 rounded-sm border border-hairline bg-surface px-2 text-left text-xs text-muted-foreground outline-none transition-colors hover:border-primary/50 focus-visible:ring-1 focus-visible:ring-ring"
      >
        <Search className="size-3.5" />
        <span className="flex-1 truncate">Search tickers, events, pages…</span>
        <kbd className="num rounded-sm border border-hairline bg-paper px-1 text-[10px]">
          Ctrl K
        </kbd>
      </button>
      <div className="ml-auto flex items-center gap-3">
        <RiskChip />
        <button
          type="button"
          onClick={() => updateSettings({ tz: tz === "UTC" ? "local" : "UTC" })}
          className="num h-7 rounded-sm border border-hairline px-2 text-[11px] uppercase text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
          aria-label={`Time zone: ${tz}. Click to switch.`}
        >
          {tz === "UTC" ? "UTC" : "Local"}
        </button>
        <WsIndicator />
        <button
          type="button"
          onClick={onSettings}
          aria-label="Settings"
          className="rounded-sm p-1.5 text-muted-foreground outline-none hover:bg-surface hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
        >
          <Settings className="size-4" />
        </button>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------ circuit breaker */

function CircuitBreaker() {
  const q = useRiskIndex();
  const go = useGo();
  const stressed = q.data?.data.regime === "Stressed";
  return (
    <AnimatePresence initial={false}>
      {stressed ? (
        <motion.div
          key="breaker"
          role="alert"
          className="no-print z-50 shrink-0 overflow-hidden bg-primary text-primary-foreground"
          initial={{ height: 0 }}
          animate={{ height: 28 }}
          exit={{ height: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="flex h-7 items-center justify-center gap-3 px-3 text-xs">
            <ShieldAlert className="size-3.5" />
            <span>Risk-off protocol suggested: aggregate impact above threshold</span>
            <button
              type="button"
              onClick={() => go("/app/stress")}
              className="rounded-sm border border-white/60 px-2 py-px text-[11px] font-medium outline-none hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-white"
            >
              Open Stress Lab
            </button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------- demo director */

function DemoMenu({ onDone }: { onDone: () => void }) {
  const q = useDemoScenarios();
  const inject = useInjectDemo();
  const list = q.data?.data ?? [];
  return (
    <div
      className="w-80 rounded-[3px] border border-hairline bg-paper p-1 shadow-lg"
      role="menu"
      aria-label="Demo scenarios"
    >
      <div className="flex items-center justify-between px-2 py-1.5 text-[11px] uppercase tracking-label text-muted-foreground">
        Replay a real archived event
        <InfoTip text="Replays a real archived event through the live pipeline. The resulting signals arrive marked REPLAY." />
      </div>
      {q.isPending ? (
        <div className="p-2">
          <SkeletonBlock lines={3} />
        </div>
      ) : q.isError ? (
        <ErrorCard
          error={q.error}
          endpoint="GET /api/demo/scenarios"
          onRetry={() => void q.refetch()}
          className="min-h-24 py-3"
        />
      ) : list.length === 0 ? (
        <EmptyState
          title="No demo scenarios"
          hint="The backend returned no archived events to replay."
          className="min-h-20 py-4"
        />
      ) : (
        <ul className="max-h-72 overflow-y-auto" data-lenis-prevent>
          {list.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                role="menuitem"
                disabled={inject.isPending}
                onClick={() => {
                  inject.mutate(s.id);
                  onDone();
                }}
                className="w-full rounded-sm px-2 py-1.5 text-left outline-none hover:bg-surface focus-visible:bg-surface disabled:opacity-50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-medium text-foreground">{s.title}</span>
                  <span className="num text-[10px] text-muted-foreground">
                    {s.eventDate.slice(0, 10)}
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {s.eventType} — {s.description}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DemoDirector({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, setOpen]);
  return (
    <div ref={ref} className="no-print fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2">
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.18 }}
          >
            <DemoMenu onDone={() => setOpen(false)} />
          </motion.div>
        ) : null}
      </AnimatePresence>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-full bg-ink px-3.5 py-2 text-xs font-medium text-paper shadow-lg outline-none transition-colors hover:bg-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <Rocket className="size-3.5" />
        Demo Director
        <kbd className="num rounded-sm bg-white/15 px-1 text-[10px]">D</kbd>
      </button>
    </div>
  );
}

/* ----------------------------------------------------------- command palette */

function PaletteContent({ close }: { close: () => void }) {
  const go = useGo();
  const cons = useConstituents();
  const sigs = useSignals({ limit: 30 });
  const events = flattenSignals(sigs.data).slice(0, 30);
  return (
    <>
      <CommandInput placeholder="Search tickers, events, pages…" />
      <CommandList>
        <CommandEmpty>No matches.</CommandEmpty>
        <CommandGroup heading="Pages">
          {NAV.map((n) => (
            <CommandItem
              key={n.to}
              value={`page ${n.label}`}
              onSelect={() => {
                close();
                go(n.to);
              }}
            >
              <n.icon className="mr-2 size-4" />
              {n.label}
              <span className="num ml-auto text-[10px] uppercase text-muted-foreground">
                G {n.key}
              </span>
            </CommandItem>
          ))}
        </CommandGroup>
        {cons.data?.data.length ? (
          <CommandGroup heading="Tickers">
            {cons.data.data.map((c) => (
              <CommandItem
                key={c.ticker}
                value={`ticker ${c.ticker} ${c.name}`}
                onSelect={() => {
                  close();
                  go("/app/signals", { entity: c.ticker });
                }}
              >
                <span className="num mr-2 w-14">{c.ticker}</span>
                <span className="truncate text-muted-foreground">{c.name}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {events.length ? (
          <CommandGroup heading="Recent events">
            {events.map((s) => (
              <CommandItem
                key={s.id}
                value={`event ${s.entity} ${s.ticker ?? ""} ${s.headline} ${s.eventType}`}
                onSelect={() => {
                  close();
                  openSignal(s.id);
                }}
              >
                <span className="truncate">{s.headline}</span>
                <span className="num ml-auto pl-2 text-[10px] text-muted-foreground">
                  {s.eventType}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
      </CommandList>
    </>
  );
}

/* ------------------------------------------------------------ settings dialog */

export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const status = useWsStatus();
  const settings = useSettings();
  const health = useHealth();
  const h = health.data?.data;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg text-[13px]" data-lenis-prevent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Connection details come from the build environment and are read-only here.
          </DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-2 text-xs">
          <dt className="text-muted-foreground">API base URL</dt>
          <dd className="num break-all">{API_BASE_URL || "—"}</dd>
          <dt className="text-muted-foreground">WebSocket URL</dt>
          <dd className="num break-all">{WS_URL || "not set"}</dd>
          <dt className="text-muted-foreground">WebSocket status</dt>
          <dd className="num uppercase">{WS_URL ? status : "off"}</dd>
          <dt className="text-muted-foreground">GET /api/health</dt>
          <dd>
            {health.isPending ? (
              <SkeletonBlock lines={2} />
            ) : health.isError || !h ? (
              <ErrorCard
                error={health.error}
                endpoint="GET /api/health"
                onRetry={() => void health.refetch()}
                className="min-h-0 items-start py-1 text-left"
              />
            ) : (
              <div className="num space-y-0.5">
                <div>status: {h.status}</div>
                <div>
                  documents: {formatNumber(h.documents.total, { maximumFractionDigits: 0 })} (
                  {formatNumber(h.documents.lastHour, { maximumFractionDigits: 0 })} last hour)
                </div>
                <div>latest: {formatDateTime(h.documents.latestPublishedAt, settings.tz)}</div>
                <div>
                  sources ok: {h.sources.filter((s) => s.status === "ok").length}/{h.sources.length}
                </div>
              </div>
            )}
          </dd>
        </dl>
        <div className="space-y-3 border-t border-hairline pt-3">
          <label className="flex items-center justify-between gap-3 text-xs">
            <span>
              Live stream minimum impact
              <span className="block text-[11px] text-muted-foreground">
                Sent to the WebSocket as ?minImpact=. Empty = all signals.
              </span>
            </span>
            <Input
              type="number"
              min={1}
              max={10}
              step={0.5}
              className="num h-8 w-20"
              value={settings.minImpact ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                updateSettings({ minImpact: v === "" ? null : Number(v) });
              }}
            />
          </label>
          <div className="flex items-center justify-between gap-3 text-xs">
            <span>Time zone</span>
            <div className="inline-flex overflow-hidden rounded-sm border border-hairline">
              {(["UTC", "local"] as const).map((z) => (
                <button
                  key={z}
                  type="button"
                  onClick={() => updateSettings({ tz: z })}
                  className={cn(
                    "px-2.5 py-1 text-[11px] uppercase outline-none focus-visible:ring-1 focus-visible:ring-ring",
                    settings.tz === z
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-surface",
                  )}
                >
                  {z}
                </button>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------------------- shell */

export function TerminalShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const [palette, setPalette] = useState(false);
  const [settings, setSettings] = useState(false);
  const [demo, setDemo] = useState(false);
  useLiveSignals();
  useHotkeys(
    () => setPalette(true),
    () => setDemo((d) => !d),
  );

  if (!isBackendConfigured) return <BackendNotConfigured />;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="terminal-root fixed inset-0 flex flex-col bg-paper text-[13px] text-foreground">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded-sm focus:bg-primary focus:px-2 focus:py-1 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <CircuitBreaker />
        <TopBar onPalette={() => setPalette(true)} onSettings={() => setSettings(true)} />
        <div className="relative flex min-h-0 flex-1">
          <Rail />
          <main
            id="main"
            tabIndex={-1}
            data-lenis-prevent
            className="terminal-main min-w-0 flex-1 overflow-y-auto pl-16 outline-none"
          >
            <motion.div
              key={path}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="min-h-full"
            >
              {children}
            </motion.div>
          </main>
        </div>
        <DemoDirector open={demo} setOpen={setDemo} />
        <SignalDrawer />
        <CommandDialog open={palette} onOpenChange={setPalette}>
          {palette ? <PaletteContent close={() => setPalette(false)} /> : null}
        </CommandDialog>
        <SettingsDialog open={settings} onOpenChange={setSettings} />
        <Toaster />
      </div>
    </TooltipProvider>
  );
}
