import type { AuditEntry } from "@/api/types";

function q(v: string): string {
  return /[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

export function auditCsv(rows: AuditEntry[]): string {
  const head = ["id", "ts", "actor", "action", "summary", "hash", "prevHash"];
  const lines = rows.map((r) =>
    [r.id, r.ts, r.actor, r.action, r.summary, r.hash, r.prevHash ?? ""].map(q).join(","),
  );
  return [head.join(","), ...lines].join("\r\n");
}

export function downloadCsv(rows: AuditEntry[]) {
  const blob = new Blob([auditCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sentinel-audit-ledger.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
