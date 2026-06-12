/**
 * Thin typed `fetch` wrapper for the REST API.
 *
 * Centralizes base URL, JSON handling, and error normalization so hooks and
 * services never deal with raw `fetch` semantics. Errors are thrown as
 * `ApiError` carrying the HTTP status and the backend error envelope.
 */

const API_BASE = "/api/v1";

export class ApiError extends Error {
  /** HTTP status code of the failed response. */
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  /** Extract a human-readable message from a non-2xx response. */
  try {
    const body = await response.json();
    return body?.error?.message ?? body?.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

/**
 * Perform a typed GET request.
 *
 * @param path - Path relative to the API base (e.g. "/customer/CUST-001").
 * @returns The parsed JSON body typed as `T`.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

/**
 * Perform a typed POST request with a JSON body.
 *
 * @param path - Path relative to the API base.
 * @param body - JSON-serializable request payload.
 * @returns The parsed JSON body typed as `T`.
 */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.json() as Promise<T>;
}

/** Absolute URL for the SSE event stream of a session. */
export function eventStreamUrl(sessionId: string): string {
  return `${API_BASE}/events/${sessionId}`;
}
