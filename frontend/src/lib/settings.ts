import { useSyncExternalStore } from "react";

/** Per-viewer UI preferences. Stored in localStorage (guarded: it can be unavailable or throw). */
export interface TerminalSettings {
  tz: "UTC" | "local";
  /** Sent to the WebSocket as ?minImpact=. null = no filter. */
  minImpact: number | null;
}

const KEY = "sentinel.terminal.settings";
const defaults: TerminalSettings = { tz: "UTC", minImpact: null };

let state: TerminalSettings = defaults;
let loaded = false;
const listeners = new Set<() => void>();

function load() {
  if (loaded) return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) state = { ...defaults, ...(JSON.parse(raw) as Partial<TerminalSettings>) };
  } catch {
    /* ignore */
  }
}

export function getSettings(): TerminalSettings {
  if (typeof window !== "undefined") load();
  return state;
}
export function updateSettings(patch: Partial<TerminalSettings>) {
  load();
  state = { ...state, ...patch };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}
export function useSettings(): TerminalSettings {
  return useSyncExternalStore(subscribe, getSettings, () => defaults);
}
