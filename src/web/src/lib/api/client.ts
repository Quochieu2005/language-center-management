export type ApiProblem = {
  detail?: string;
  code?: string;
  [field: string]: unknown;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: ApiProblem,
    readonly retryAfter: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const apiOrigin = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001")
  .replace(/\/+$/, "")
  .replace(/\/api\/v1$/, "");
const apiBase = `${apiOrigin}/api/v1`;
let csrfToken: string | null = null;
const pendingGetRequests = new Map<string, Promise<unknown>>();

async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${apiBase}/auth/csrf/`, { credentials: "include", cache: "no-store" });
  const data = (await response.json()) as { csrf_token?: string };
  if (!response.ok || !data.csrf_token) throw new ApiError("Không lấy được CSRF token.", response.status, data, null);
  csrfToken = data.csrf_token;
  return csrfToken;
}

export function query(values: Record<string, string | number | boolean | undefined | null>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

export function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const requestKey = method === "GET" && !init.signal && !init.headers ? `${apiBase}${path}` : null;
  if (!requestKey) return sendApiRequest<T>(path, init, method);

  const pending = pendingGetRequests.get(requestKey);
  if (pending) return pending as Promise<T>;

  const request = sendApiRequest<T>(path, init, method);
  pendingGetRequests.set(requestKey, request);
  void request.then(
    () => pendingGetRequests.delete(requestKey),
    () => pendingGetRequests.delete(requestKey),
  );
  return request;
}

async function sendApiRequest<T>(path: string, init: RequestInit, method: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers.set("X-CSRFToken", await getCsrfToken());

  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    method,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const problem = (payload && typeof payload === "object" ? payload : {}) as ApiProblem;
    const message = typeof problem.detail === "string" ? problem.detail : `Yêu cầu API thất bại (${response.status}).`;
    throw new ApiError(message, response.status, problem, response.headers.get("Retry-After"));
  }
  return payload as T;
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}
