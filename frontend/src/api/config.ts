/** Build-time configuration. There is deliberately no fallback to sample data. */
const env = import.meta.env as Record<string, string | undefined>;

export const API_BASE_URL = (env["VITE_API_BASE_URL"] ?? "").trim().replace(/\/+$/, "");
export const WS_URL = (env["VITE_WS_URL"] ?? "").trim();
export const API_TOKEN = (env["VITE_API_TOKEN"] ?? "").trim();

export const isBackendConfigured = API_BASE_URL.length > 0;
