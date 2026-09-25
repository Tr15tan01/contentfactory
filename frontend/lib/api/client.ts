import type { ApiErrorBody } from "@/types/api";

export const API_BASE = "/api/v1";
const CSRF_COOKIE = "cf_csrf";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
// Endpoints where a 401 is a real answer, not an expired access token.
const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/verify-email", "/auth/password/"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Field-level messages from `details.fields`, when the backend supplies them. */
  get fields(): Record<string, string> {
    const fields = this.details?.fields;
    return fields && typeof fields === "object" ? (fields as Record<string, string>) : {};
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfRequest: Promise<string> | null = null;

async function csrfToken(force = false): Promise<string> {
  const existing = force ? null : readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfRequest ??= fetch(`${API_BASE}/auth/csrf`, { credentials: "same-origin", cache: "no-store" })
    .then((r) => r.json() as Promise<{ csrf_token: string }>)
    .then((b) => b.csrf_token)
    .finally(() => {
      csrfRequest = null;
    });
  return csrfRequest;
}

let refreshRequest: Promise<boolean> | null = null;

/** Rotate the session once, shared by every request that hit a 401 at the same time. */
export function refreshSession(): Promise<boolean> {
  refreshRequest ??= (async () => {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "x-csrf-token": await csrfToken() },
    });
    // 409 = another tab rotated the token a moment ago; its cookies are already ours.
    return res.status === 204 || res.status === 409;
  })().finally(() => {
    refreshRequest = null;
  });
  return refreshRequest;
}

async function toError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    /* non-JSON error (proxy down, HTML error page) */
  }
  if (body?.error) {
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details ?? null);
  }
  if (res.status >= 500 || res.status === 0) {
    return new ApiError(res.status, "service_unavailable", "ContentFactory is unreachable right now. Try again in a moment.");
  }
  return new ApiError(res.status, "http_error", `Request failed (${res.status}).`);
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: RequestOptions = {}, attempt = 0): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { accept: "application/json" };
  if (options.body !== undefined) headers["content-type"] = "application/json";
  if (UNSAFE.has(method)) headers["x-csrf-token"] = await csrfToken(attempt > 0);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "You appear to be offline. Check your connection and try again.");
  }

  if (res.ok) {
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  const error = await toError(res);
  if (attempt === 0) {
    if (error.status === 403 && error.code === "csrf_failed") return api<T>(path, options, 1);
    if (error.status === 401 && !NO_REFRESH.some((p) => path.startsWith(p)) && (await refreshSession())) {
      return api<T>(path, options, 1);
    }
  }
  throw error;
}
