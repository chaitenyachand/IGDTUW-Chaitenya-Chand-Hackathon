import { API_BASE_URL, API_TOKEN } from "./config";
import { ApiError } from "./errors";
import type { Envelope } from "./types";

type Params = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

function buildUrl(path: string, params?: Params) {
  const url = new URL(API_BASE_URL + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) {
        if (v.length) url.searchParams.set(k, v.join(","));
      } else url.searchParams.set(k, String(v));
    }
  }
  return url;
}

async function parse<T>(res: Response, endpoint: string): Promise<Envelope<T>> {
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      throw new ApiError(res.status, "invalid_json", "Response was not valid JSON", endpoint);
    }
  }
  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? res.statusText,
      endpoint,
    );
  }
  const env = body as Envelope<T> | null;
  if (!env || typeof env !== "object" || !("data" in env) || !("meta" in env)) {
    throw new ApiError(res.status, "bad_envelope", "Response is missing { data, meta }", endpoint);
  }
  return env;
}

export async function apiGet<T>(
  path: string,
  params?: Params,
  signal?: AbortSignal,
): Promise<Envelope<T>> {
  const endpoint = `GET ${path}`;
  try {
    const res = await fetch(buildUrl(path, params), {
      headers: { Accept: "application/json" },
      signal: signal ?? null,
    });
    return await parse<T>(res, endpoint);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(
      0,
      "network_error",
      e instanceof Error ? e.message : "Network error",
      endpoint,
    );
  }
}

export async function apiSend<T>(
  method: "POST" | "DELETE" | "PUT",
  path: string,
  body?: unknown,
): Promise<Envelope<T>> {
  const endpoint = `${method} ${path}`;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (API_TOKEN) headers["Authorization"] = `Bearer ${API_TOKEN}`;
  try {
    const res = await fetch(buildUrl(path), {
      method,
      headers,
      body: body === undefined ? null : JSON.stringify(body),
    });
    return await parse<T>(res, endpoint);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(
      0,
      "network_error",
      e instanceof Error ? e.message : "Network error",
      endpoint,
    );
  }
}
