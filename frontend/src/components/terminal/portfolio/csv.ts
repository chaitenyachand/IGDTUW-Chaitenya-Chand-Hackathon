/** Client-side CSV parsing and validation for the portfolio import preview (no upload endpoint exists). */
import type { Holding } from "@/api/types";

export const REQUIRED_COLUMNS = [
  "assetType",
  "counterparty",
  "sector",
  "country",
  "notional",
  "marketValue",
  "rating",
  "maturity",
] as const;
const ASSET_TYPES = ["Loan", "Bond", "Derivative"] as const;

/** RFC4180-ish: quoted fields, escaped quotes (""), commas and newlines inside quotes, CRLF, BOM. */
export function parseCsv(input: string): string[][] {
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text.charAt(i);
    if (quoted) {
      if (ch === '"') {
        if (text.charAt(i + 1) === '"') {
          field += '"';
          i++;
        } else quoted = false;
      } else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text.charAt(i + 1) === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += ch;
  }
  if (quoted) throw new Error("Unterminated quoted field: the file ends inside a quote.");
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

export type PreviewRow = Omit<Holding, "id">;
export interface RowError {
  row: number;
  reasons: string[];
}
export type ImportResult =
  | { kind: "error"; title: string; detail: string; missing?: string[] }
  | { kind: "ok"; total: number; valid: PreviewRow[]; errors: RowError[]; extraColumns: string[] };

const isNum = (s: string) => s.trim() !== "" && Number.isFinite(Number(s.trim().replace(/,/g, "")));
const num = (s: string) => Number(s.trim().replace(/,/g, ""));

export function validateCsv(text: string): ImportResult {
  if (text.trim() === "")
    return {
      kind: "error",
      title: "The file is empty",
      detail:
        "No content was found. Choose a CSV file with a header row and at least one data row.",
    };
  let rows: string[][];
  try {
    rows = parseCsv(text);
  } catch (e) {
    return {
      kind: "error",
      title: "The file could not be parsed",
      detail: e instanceof Error ? e.message : "Unreadable CSV.",
    };
  }
  const header = (rows[0] ?? []).map((h) => h.trim());
  const idx = new Map<string, number>();
  header.forEach((h, i) => idx.set(h.toLowerCase(), i));
  const missing = REQUIRED_COLUMNS.filter((c) => !idx.has(c.toLowerCase()));
  if (missing.length > 0)
    return {
      kind: "error",
      title: "Required columns are missing",
      detail: `Found: ${header.filter(Boolean).join(", ") || "none"}. Column names are matched case-insensitively.`,
      missing: [...missing],
    };
  const known = new Set(REQUIRED_COLUMNS.map((c) => c.toLowerCase()));
  const extraColumns = header.filter((h) => h && !known.has(h.toLowerCase()));
  const body = rows.slice(1);
  const valid: PreviewRow[] = [];
  const errors: RowError[] = [];
  let total = 0;
  body.forEach((cells, k) => {
    if (cells.every((c) => c.trim() === "")) return;
    total++;
    const get = (c: (typeof REQUIRED_COLUMNS)[number]) =>
      (cells[idx.get(c.toLowerCase()) ?? -1] ?? "").trim();
    const reasons: string[] = [];
    const at = ASSET_TYPES.find((t) => t.toLowerCase() === get("assetType").toLowerCase());
    if (!at)
      reasons.push(`assetType "${get("assetType")}" must be one of ${ASSET_TYPES.join(", ")}`);
    for (const c of ["counterparty", "sector", "country", "rating"] as const)
      if (get(c) === "") reasons.push(`${c} is required`);
    for (const c of ["notional", "marketValue"] as const)
      if (!isNum(get(c))) reasons.push(`${c} "${get(c)}" is not a number`);
    const mat = get("maturity");
    if (mat === "" || Number.isNaN(Date.parse(mat)))
      reasons.push(`maturity "${mat}" is not a valid date`);
    if (cells.length !== header.length)
      reasons.push(`expected ${header.length} fields, found ${cells.length}`);
    if (reasons.length > 0 || !at) errors.push({ row: k + 2, reasons });
    else
      valid.push({
        assetType: at,
        counterparty: get("counterparty"),
        sector: get("sector"),
        country: get("country"),
        notional: num(get("notional")),
        marketValue: num(get("marketValue")),
        rating: get("rating"),
        maturity: mat,
      });
  });
  if (total === 0)
    return {
      kind: "error",
      title: "No data rows",
      detail: "The header is present but the file has no data rows.",
    };
  return { kind: "ok", total, valid, errors, extraColumns };
}
