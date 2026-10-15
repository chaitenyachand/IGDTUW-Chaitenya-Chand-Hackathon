import { useRef, useState } from "react";
import { AlertTriangle, FileWarning, Upload } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatCurrency, formatDate } from "@/lib/format";
import { REQUIRED_COLUMNS, validateCsv, type ImportResult } from "./csv";

const NOTE =
  "Upload to the backend is not available yet (no import endpoint in the API contract). Validated rows are shown as a local preview only.";

export function ImportCsv() {
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    setName(f.name);
    let res: ImportResult;
    try {
      res = validateCsv(await f.text());
    } catch {
      res = {
        kind: "error",
        title: "The file could not be read",
        detail:
          "The browser could not read this file. Try exporting it again as plain CSV (UTF-8).",
      };
    }
    setResult(res);
    setOpen(true);
    if (input.current) input.current.value = "";
  };

  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        aria-label="Choose CSV file"
        tabIndex={-1}
        onChange={(e) => void onFile(e.target.files?.[0])}
      />
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="inline-flex items-center gap-1.5 rounded-sm border border-hairline bg-paper px-2.5 py-1 text-xs font-medium text-foreground outline-none transition-colors hover:border-primary hover:text-primary focus-visible:ring-1 focus-visible:ring-ring"
      >
        <Upload className="size-3" /> Import CSV
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl text-[13px]">
          <DialogHeader>
            <DialogTitle>CSV import check</DialogTitle>
            <DialogDescription className="num break-all">{name}</DialogDescription>
          </DialogHeader>
          {result?.kind === "error" ? (
            <div
              role="alert"
              className="flex flex-col items-center gap-2 rounded-[3px] border border-primary/40 bg-accent px-4 py-6 text-center"
            >
              <FileWarning className="size-6 text-primary" />
              <p className="font-medium text-foreground">{result.title}</p>
              <p className="max-w-md text-xs text-muted-foreground">{result.detail}</p>
              {result.missing ? (
                <ul className="flex flex-wrap justify-center gap-1">
                  {result.missing.map((m) => (
                    <li
                      key={m}
                      className="num rounded-sm border border-primary/50 px-1.5 text-[11px] text-primary"
                    >
                      {m}
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="text-[11px] text-muted-foreground">
                Required columns: <span className="num">{REQUIRED_COLUMNS.join(", ")}</span>
              </p>
            </div>
          ) : result ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-4">
                <div>
                  <div className="num text-[20px] text-foreground">{result.valid.length}</div>
                  <div className="text-[11px] uppercase tracking-label text-muted-foreground">
                    Rows OK
                  </div>
                </div>
                <div>
                  <div
                    className={`num text-[20px] ${result.errors.length ? "text-primary" : "text-foreground"}`}
                  >
                    {result.errors.length}
                  </div>
                  <div className="text-[11px] uppercase tracking-label text-muted-foreground">
                    Rows with errors
                  </div>
                </div>
                <div>
                  <div className="num text-[20px] text-foreground">{result.total}</div>
                  <div className="text-[11px] uppercase tracking-label text-muted-foreground">
                    Total rows
                  </div>
                </div>
              </div>
              {result.extraColumns.length ? (
                <p className="text-[11px] text-muted-foreground">
                  Ignored extra columns:{" "}
                  <span className="num">{result.extraColumns.join(", ")}</span>
                </p>
              ) : null}
              {result.errors.length ? (
                <div>
                  <div className="mb-1 flex items-center gap-1 text-[11px] uppercase tracking-label text-primary">
                    <AlertTriangle className="size-3" /> Errors
                  </div>
                  <ul
                    data-lenis-prevent
                    className="max-h-32 space-y-0.5 overflow-y-auto rounded-[3px] border border-hairline p-2 text-[12px]"
                  >
                    {result.errors.map((e) => (
                      <li key={e.row}>
                        <span className="num text-foreground">Row {e.row}</span>{" "}
                        <span className="text-muted-foreground">{e.reasons.join("; ")}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {result.valid.length ? (
                <div
                  data-lenis-prevent
                  className="max-h-56 overflow-auto rounded-[3px] border border-hairline"
                >
                  <table className="w-full min-w-[640px] text-[12px]">
                    <thead className="sticky top-0 bg-paper text-[11px] uppercase tracking-label text-muted-foreground">
                      <tr className="border-b border-hairline">
                        {[
                          "Type",
                          "Counterparty",
                          "Sector",
                          "Country",
                          "Notional",
                          "Market value",
                          "Rating",
                          "Maturity",
                        ].map((h, i) => (
                          <th
                            key={h}
                            className={`px-2 py-1 font-medium ${i === 4 || i === 5 ? "text-right" : "text-left"}`}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.valid.map((r, i) => (
                        <tr key={i} className="border-b border-hairline last:border-b-0">
                          <td className="px-2 py-1">{r.assetType}</td>
                          <td className="px-2 py-1">{r.counterparty}</td>
                          <td className="px-2 py-1">{r.sector}</td>
                          <td className="px-2 py-1">{r.country}</td>
                          <td className="num px-2 py-1 text-right">{formatCurrency(r.notional)}</td>
                          <td className="num px-2 py-1 text-right">
                            {formatCurrency(r.marketValue)}
                          </td>
                          <td className="num px-2 py-1">{r.rating}</td>
                          <td className="num px-2 py-1">{formatDate(r.maturity)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No valid rows to preview.</p>
              )}
            </div>
          ) : null}
          <p className="rounded-[3px] border border-hairline bg-surface px-2 py-1.5 text-[11px] text-muted-foreground">
            {NOTE}
          </p>
        </DialogContent>
      </Dialog>
    </>
  );
}
