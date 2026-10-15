import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertOctagon, Check, Download, Link2, Loader2, ShieldCheck } from "lucide-react";

import { flattenAudit, useAudit, useVerifyAudit } from "@/api/client";
import type { AuditEntry } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { EmptyState, Panel, QueryBoundary, SkeletonBlock } from "@/components/terminal/kit";
import { downloadCsv } from "./csv";
import { EntryDrawer } from "./entry-drawer";

const btn =
  "inline-flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2.5 py-1 text-xs font-medium text-foreground outline-none transition-colors hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";

export function Ledger() {
  const q = useAudit();
  const verify = useVerifyAudit();
  const { tz } = useSettings();
  const rows = useMemo(() => flattenAudit(q.data), [q.data]);
  const [open, setOpen] = useState<AuditEntry | null>(null);
  const v = verify.data?.data;
  const brokenId = v && !v.intact ? v.brokenAtId : null;

  useEffect(() => {
    if (!brokenId) return;
    document
      .getElementById(`audit-row-${brokenId}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [brokenId]);

  const actions = (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className={btn}
        disabled={rows.length === 0}
        onClick={() => downloadCsv(rows)}
      >
        <Download className="size-3" /> Export CSV
      </button>
      <button
        type="button"
        className={btn}
        disabled={verify.isPending}
        onClick={() => verify.mutate()}
      >
        {verify.isPending ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <ShieldCheck className="size-3" />
        )}{" "}
        Verify chain
      </button>
    </div>
  );

  return (
    <Panel
      title="Audit ledger"
      info="Append-only log of system and user actions. Each entry stores its hash and the previous entry's hash, so any edit breaks the chain."
      source={q.data?.pages[0]?.meta.source}
      actions={actions}
    >
      <AnimatePresence>
        {verify.isPending ? (
          <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground" role="status">
            <Loader2 className="size-3.5 animate-spin" /> Verifying chain…
          </div>
        ) : v?.intact ? (
          <motion.div
            key="ok"
            role="status"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 flex items-center gap-2 rounded-[3px] border border-hairline bg-surface px-3 py-2 text-xs"
          >
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
              className="inline-flex size-5 items-center justify-center rounded-full text-white"
              style={{ background: "var(--positive)" }}
            >
              <Check className="size-3" />
            </motion.span>
            <span className="font-medium text-foreground">Chain intact</span>
            <span className="num text-muted-foreground">checked {v.checked} entries</span>
          </motion.div>
        ) : v ? (
          <motion.div
            key="bad"
            role="alert"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 flex items-center gap-2 rounded-[3px] border border-primary bg-accent px-3 py-2 text-xs text-primary"
          >
            <AlertOctagon className="size-4" />
            <span className="font-medium">Chain broken at entry {v.brokenAtId ?? "—"}</span>
            <span className="num text-muted-foreground">checked {v.checked} entries</span>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <QueryBoundary
        query={{
          isPending: q.isPending,
          isError: q.isError,
          error: q.error,
          refetch: q.refetch,
          data: q.data,
        }}
        endpoint="GET /api/audit"
        skeleton={<SkeletonBlock lines={8} />}
      >
        {() =>
          rows.length === 0 ? (
            <EmptyState
              title="No audit entries yet"
              hint="Actions such as stress runs and rebalances are recorded here."
            />
          ) : (
            <>
              <div data-lenis-prevent className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-xs">
                  <thead className="text-[11px] uppercase tracking-label text-muted-foreground">
                    <tr>
                      <th className="py-1 pr-3 font-medium">Time</th>
                      <th className="py-1 pr-3 font-medium">Actor</th>
                      <th className="py-1 pr-3 font-medium">Action</th>
                      <th className="py-1 pr-3 font-medium">Summary</th>
                      <th className="py-1 pr-3 font-medium">Hash</th>
                      <th className="py-1 font-medium">Prev</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const older = rows[i + 1];
                      const mismatch = older != null && r.prevHash !== older.hash;
                      return (
                        <tr
                          key={r.id}
                          id={`audit-row-${r.id}`}
                          tabIndex={0}
                          role="button"
                          aria-label={`Open audit entry ${r.id}`}
                          onClick={() => setOpen(r)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setOpen(r);
                            }
                          }}
                          className={cn(
                            "cursor-pointer border-t border-hairline outline-none hover:bg-surface focus-visible:bg-surface",
                            brokenId === r.id && "bg-accent ring-1 ring-inset ring-primary",
                          )}
                        >
                          <td className="num whitespace-nowrap py-1.5 pr-3 text-muted-foreground">
                            {formatDateTime(r.ts, tz)}
                          </td>
                          <td className="py-1.5 pr-3">
                            <span
                              className={cn(
                                "rounded-sm border px-1.5 py-px text-[11px]",
                                r.actor === "user"
                                  ? "border-primary/40 bg-accent text-primary"
                                  : "border-hairline bg-surface text-muted-foreground",
                              )}
                            >
                              {r.actor}
                            </span>
                          </td>
                          <td className="num py-1.5 pr-3 text-foreground">{r.action}</td>
                          <td
                            className="max-w-[360px] truncate py-1.5 pr-3 text-foreground"
                            title={r.summary}
                          >
                            {r.summary}
                          </td>
                          <td className="num py-1.5 pr-3" title={r.hash}>
                            {r.hash.slice(0, 8)}
                          </td>
                          <td
                            className="num whitespace-nowrap py-1.5 text-muted-foreground"
                            title={r.prevHash ?? "genesis"}
                          >
                            <span className="inline-flex items-center gap-1">
                              <Link2 className="size-3" />
                              {r.prevHash ? r.prevHash.slice(0, 6) : "—"}
                              {mismatch ? (
                                <span
                                  className="inline-block size-1.5 rounded-full"
                                  style={{ background: "var(--primary)", opacity: 0.6 }}
                                  title="prevHash does not match the next-older loaded row; run Verify chain for the authoritative result"
                                />
                              ) : null}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {q.hasNextPage ? (
                <div className="mt-3 flex justify-center">
                  <button
                    type="button"
                    className={btn}
                    disabled={q.isFetchingNextPage}
                    onClick={() => void q.fetchNextPage()}
                  >
                    {q.isFetchingNextPage ? <Loader2 className="size-3 animate-spin" /> : null} Load
                    more
                  </button>
                </div>
              ) : null}
            </>
          )
        }
      </QueryBoundary>
      <EntryDrawer entry={open} tz={tz} onClose={() => setOpen(null)} />
    </Panel>
  );
}
