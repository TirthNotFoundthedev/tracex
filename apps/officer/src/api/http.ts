import type { components } from "./schema";

export type ApiError = components["schemas"]["Error"];
export type FieldError = NonNullable<ApiError["field_errors"]>[number];

/** What every officer API call gives back. The UI switches on `kind` and never reads status codes. */
export type ApiResult<T> =
  | { kind: "ok"; data: T }
  | { kind: "sessionExpired" }
  | { kind: "notFound" }
  | { kind: "notAllowed" }
  | { kind: "tryAgainShortly" }
  | { kind: "conflict"; code: ApiError["code"] | undefined }
  | { kind: "invalid"; fieldErrors: FieldError[] }
  | { kind: "tooManyAttempts" }
  | { kind: "networkError" }
  | { kind: "safetyPause" }
  | { kind: "serverError" };

/** Same as ApiResult, but 401 is left for the caller to name (wrong password, or expired session). */
export type HttpResult<T> =
  Exclude<ApiResult<T>, { kind: "sessionExpired" }> | { kind: "unauthorized" };

export type FetchLike = typeof fetch;

type Query = Record<string, string | number | boolean | undefined>;

export function buildUrl(baseUrl: string, path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) params.set(key, String(value));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return `${baseUrl.replace(/\/+$/, "")}${path}${suffix}`;
}

async function readError(response: Response): Promise<ApiError | undefined> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "code" in body) return body as ApiError;
  } catch {
    return undefined;
  }
  return undefined;
}

/**
 * Status mapping (access spec R2). 404 means "not found or not yours": unknown, hidden, withdrawn and redacted ids
 * all look the same, so the UI gets one "notFound" result and never guesses which. Only a stub from the API
 * (GET /stubs/{id}) shows the other-police-area card (D43). 403 means the case is visible but the role or the
 * grant does not allow the action.
 */
export async function toResult<T>(response: Response): Promise<HttpResult<T>> {
  const status = response.status;
  if (status >= 200 && status < 300) {
    if (status === 204) return { kind: "ok", data: undefined as T };
    return { kind: "ok", data: (await response.json()) as T };
  }
  if (status === 401) return { kind: "unauthorized" };
  if (status === 403) return { kind: "notAllowed" };
  if (status === 404) return { kind: "notFound" };
  // Any 503 is the safety pause; the app does not read the body code.
  if (status === 503) return { kind: "safetyPause" };
  if (status === 429) return { kind: "tooManyAttempts" };
  if (status === 409) {
    const error = await readError(response);
    if (error?.code === "RUN_IN_PROGRESS") return { kind: "tryAgainShortly" };
    return { kind: "conflict", code: error?.code };
  }
  if (status === 422) {
    const error = await readError(response);
    return { kind: "invalid", fieldErrors: error?.field_errors ?? [] };
  }
  return { kind: "serverError" };
}

export interface SendOptions {
  method: "GET" | "POST";
  url: string;
  accessToken?: string;
  body?: unknown;
}

export async function send<T>(fetchImpl: FetchLike, options: SendOptions): Promise<HttpResult<T>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.accessToken) headers.Authorization = `Bearer ${options.accessToken}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetchImpl(options.url, {
      method: options.method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
    });
  } catch {
    return { kind: "networkError" };
  }
  try {
    return await toResult<T>(response);
  } catch {
    return { kind: "serverError" };
  }
}
