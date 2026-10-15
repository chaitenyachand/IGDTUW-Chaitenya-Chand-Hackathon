import { useSyncExternalStore } from "react";

/** Global state for the reusable Signal drawer. */
let openId: string | null = null;
const listeners = new Set<() => void>();

export function openSignal(id: string | null) {
  openId = id;
  listeners.forEach((l) => l());
}
export function closeSignal() {
  openSignal(null);
}
export function useOpenSignalId() {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => openId,
    () => null,
  );
}
