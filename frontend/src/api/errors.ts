export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly endpoint: string;

  constructor(status: number, code: string, message: string, endpoint = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.endpoint = endpoint;
  }
}

export function toApiError(err: unknown, endpoint: string): ApiError {
  if (err instanceof ApiError) return err;
  const message = err instanceof Error ? err.message : "Unknown error";
  return new ApiError(0, "network_error", message, endpoint);
}
