import { useEffect, useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Copy, X } from "lucide-react";
import { toast } from "sonner";

import type { AuditEntry } from "@/api/types";
import { formatDateTime } from "@/lib/format";

function reasoningOf(p: Record<string, unknown>): string | null {
  for (const k of ["reasoning", "rationale", "explanation"]) {
    const v = p[k];
    if (typeof v === "string" && v.trim()) return v;
  }
  return null;
}

export function EntryDrawer({
  entry,
  tz,
  onClose,
}: {
  entry: AuditEntry | null;
  tz: "UTC" | "local";
  onClose: () => void;
}) {
  useEffect(() => {
    if (!entry) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [entry, onClose]);

  const json = useMemo(() => (entry ? JSON.stringify(entry.payload, null, 2) : ""), [entry]);
  const reasoning = entry ? reasoningOf(entry.payload) : null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      toast.success("JSON copied");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  return (
    <AnimatePresence>
      {entry ? (
        <>
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-black/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            key="panel"
            role="dialog"
            aria-modal="true"
            aria-label={`Audit entry ${entry.id}`}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[520px] flex-col border-l border-hairline bg-paper shadow-xl"
            initial={{ x: 520 }}
            animate={{ x: 0 }}
            exit={{ x: 520 }}
            transition={{ type: "tween", duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <header className="flex items-start justify-between gap-3 border-b border-hairline px-4 py-3">
              <div className="min-w-0">
                <div className="num text-[11px] uppercase tracking-label text-muted-foreground">
                  {entry.action}
                </div>
                <div className="mt-0.5 text-[13px] text-foreground">{entry.summary}</div>
                <div className="num mt-1 text-[11px] text-muted-foreground">
                  {formatDateTime(entry.ts, tz)} · {entry.actor}
                </div>
              </div>
              <button
                type="button"
                autoFocus
                aria-label="Close"
                onClick={onClose}
                className="rounded-sm p-1 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
              >
                <X className="size-4" />
              </button>
            </header>
            <div data-lenis-prevent className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
              <dl className="space-y-2 text-[11px]">
                <div>
                  <dt className="uppercase tracking-label text-muted-foreground">Hash</dt>
                  <dd className="num break-all text-foreground">{entry.hash}</dd>
                </div>
                <div>
                  <dt className="uppercase tracking-label text-muted-foreground">Previous hash</dt>
                  <dd className="num break-all text-foreground">
                    {entry.prevHash ?? "— (genesis)"}
                  </dd>
                </div>
              </dl>
              {reasoning ? (
                <div className="rounded-[3px] border border-hairline bg-surface p-3">
                  <div className="mb-1 text-[11px] uppercase tracking-label text-muted-foreground">
                    Reasoning
                  </div>
                  <p className="text-[13px] leading-snug text-foreground">{reasoning}</p>
                </div>
              ) : null}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[11px] uppercase tracking-label text-muted-foreground">
                    Payload
                  </span>
                  <button
                    type="button"
                    onClick={() => void copy()}
                    className="inline-flex items-center gap-1 rounded-sm border border-hairline px-2 py-0.5 text-xs outline-none hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <Copy className="size-3" /> Copy JSON
                  </button>
                </div>
                <pre
                  data-lenis-prevent
                  className="num max-h-[60vh] overflow-auto rounded-[3px] border border-hairline bg-surface p-3 text-[11px] leading-snug"
                >
                  {json}
                </pre>
              </div>
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
