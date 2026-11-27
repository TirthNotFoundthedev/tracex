import { type ApiResult, buildUrl, type FetchLike, send } from "./http";
import type { operations } from "./schema";
import type { Session } from "./session";

type Operation = keyof operations;

type JsonBody<R> = R extends { content: { "application/json": infer B } } ? B : never;
type Responses<K extends Operation> = operations[K]["responses"];
type OkResponse<K extends Operation> =
  | (Responses<K> extends { 200: infer R } ? R : never)
  | (Responses<K> extends { 201: infer R } ? R : never);

/** Body of the success response of operation K (void when the operation returns 204). */
export type Success<K extends Operation> = [JsonBody<OkResponse<K>>] extends [never]
  ? undefined
  : JsonBody<OkResponse<K>>;

type QueryOf<K extends Operation> = operations[K]["parameters"] extends { query?: infer Q }
  ? Exclude<Q, undefined | never>
  : never;

type BodyOf<K extends Operation> = operations[K] extends {
  requestBody?: { content: { "application/json": infer B } };
}
  ? B
  : never;

export interface ClientOptions {
  baseUrl: string;
  session: Session;
  fetch?: FetchLike;
}

export const REASON_MIN = 10;
export const REASON_MAX = 500;

/** The access-request reason must be 10 to 500 characters after trimming (contract minLength, maxLength). */
export function isValidReason(trimmedReason: string): boolean {
  return trimmedReason.length >= REASON_MIN && trimmedReason.length <= REASON_MAX;
}

/** Base URL from the Vite environment; empty means same origin. */
export function apiBaseFromEnv(): string {
  const value: unknown = import.meta.env.VITE_API_URL;
  return typeof value === "string" ? value : "";
}

export function createClient(options: ClientOptions) {
  const { session } = options;
  const fetchImpl: FetchLike = options.fetch ?? ((...args) => fetch(...args));

  async function call<T>(
    method: "GET" | "POST",
    path: string,
    extra: { query?: object; body?: unknown } = {},
  ): Promise<ApiResult<T>> {
    const url = buildUrl(options.baseUrl, path, extra.query as Record<string, string | undefined>);
    let token = session.accessToken();
    // One retry at most: a second 401 after a good refresh means the session is dead.
    for (let attempt = 0; attempt < 2; attempt++) {
      const result = await send<T>(fetchImpl, {
        method,
        url,
        accessToken: token,
        body: extra.body,
      });
      if (result.kind !== "unauthorized") return result;
      if (attempt === 1) break;
      const outcome = await session.refreshAfter(token);
      if (outcome.kind === "signedOut") return { kind: "sessionExpired" };
      if (outcome.kind === "unavailable") return outcome.result;
      token = outcome.token;
    }
    return { kind: "sessionExpired" };
  }

  const id = encodeURIComponent;

  return {
    getMe: () => call<Success<"getMe">>("GET", "/me"),

    listCases: (query: QueryOf<"listCases"> = {}) =>
      call<Success<"listCases">>("GET", "/cases", { query }),
    listCaseEntities: (caseId: string, query: QueryOf<"listCaseEntities"> = {}) =>
      call<Success<"listCaseEntities">>("GET", `/cases/${id(caseId)}/entities`, { query }),
    getEntity: (entityId: string) => call<Success<"getEntity">>("GET", `/entities/${id(entityId)}`),
    searchEntities: (query: QueryOf<"searchEntities">) =>
      call<Success<"searchEntities">>("GET", "/search/entities", { query }),

    listLinks: (query: QueryOf<"listLinks"> = {}) =>
      call<Success<"listLinks">>("GET", "/links", { query }),
    getLink: (linkId: string) => call<Success<"getLink">>("GET", `/links/${id(linkId)}`),
    getLinkExplanation: (linkId: string) =>
      call<Success<"getLinkExplanation">>("GET", `/links/${id(linkId)}/explanation`),

    confirmLink: (linkId: string, body: BodyOf<"confirmLink"> = {}) =>
      call<Success<"confirmLink">>("POST", `/links/${id(linkId)}/confirm`, { body }),
    rejectLink: (linkId: string, body: BodyOf<"rejectLink">) =>
      call<Success<"rejectLink">>("POST", `/links/${id(linkId)}/reject`, { body }),
    undoLink: (linkId: string, body: BodyOf<"undoLink">) =>
      call<Success<"undoLink">>("POST", `/links/${id(linkId)}/undo`, { body }),

    reopenLink: (linkId: string, body: BodyOf<"reopenLink">) =>
      call<Success<"reopenLink">>("POST", `/links/${id(linkId)}/reopen`, { body }),

    getStub: (stubId: string) => call<Success<"getStub">>("GET", `/stubs/${id(stubId)}`),
    createAccessRequest: (body: BodyOf<"createAccessRequest">) => {
      const reason = body.reason.trim();
      if (!isValidReason(reason)) {
        return Promise.resolve<ApiResult<Success<"createAccessRequest">>>({
          kind: "invalid",
          fieldErrors: [
            { field: "reason", code: reason.length < REASON_MIN ? "too_short" : "too_long" },
          ],
        });
      }
      return call<Success<"createAccessRequest">>("POST", "/access-requests", {
        body: { ...body, reason },
      });
    },
    listAccessRequests: (query: QueryOf<"listAccessRequests">) =>
      call<Success<"listAccessRequests">>("GET", "/access-requests", { query }),
    getAccessRequest: (requestId: string) =>
      call<Success<"getAccessRequest">>("GET", `/access-requests/${id(requestId)}`),
    withdrawAccessRequest: (requestId: string) =>
      call<Success<"withdrawAccessRequest">>("POST", `/access-requests/${id(requestId)}/withdraw`),
  };
}

export type OfficerClient = ReturnType<typeof createClient>;
