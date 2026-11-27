import { type ApiResult, buildUrl, type FetchLike, send } from "./http";
import type { operations } from "./schema";
import type { Session } from "./session";

type Operation = keyof operations;

type JsonBody<R> = R extends { content: { "application/json": infer B } } ? B : never;
type Responses<K extends Operation> = operations[K]["responses"];
type OkResponse<K extends Operation> =
  | (Responses<K> extends { 200: infer R } ? R : never)
  | (Responses<K> extends { 201: infer R } ? R : never)
  | (Responses<K> extends { 202: infer R } ? R : never);

/** Body of the success response of operation K (undefined when the operation returns 204). */
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

/** The generated type says `string[]` for binary files; in the browser they are File objects. */
export type UploadInput = Omit<
  operations["uploadFiles"]["requestBody"]["content"]["multipart/form-data"],
  "files"
> & { files: Blob[] };

export interface ClientOptions {
  baseUrl: string;
  session: Session;
  fetch?: FetchLike;
}

/** The refusal note on an access request is at most 200 characters (contract maxLength). */
export const NOTE_MAX = 200;

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
      if (outcome.kind === "unavailable") return { kind: outcome.reason };
      token = outcome.token;
    }
    session.endLocally();
    return { kind: "sessionExpired" };
  }

  const id = encodeURIComponent;
  const REASON_MIN = 3;
  const REASON_MAX = 1000;

  /** Reject, undo and reopen need a written reason of 3 to 1000 characters (D43, LinkReasonRequest). Any other length never leaves the browser. */
  function withReason<K extends "rejectLink" | "undoLink" | "reopenLink">(
    action: "reject" | "undo" | "reopen",
  ) {
    return (linkId: string, body: BodyOf<K>) => {
      const reason = (body as { reason: string }).reason.trim();
      const code =
        reason.length === 0
          ? "required"
          : reason.length < REASON_MIN
            ? "too_short"
            : reason.length > REASON_MAX
              ? "too_long"
              : undefined;
      if (code) {
        return Promise.resolve<ApiResult<Success<K>>>({
          kind: "invalid",
          fieldErrors: [{ field: "reason", code }],
        });
      }
      return call<Success<K>>("POST", `/links/${id(linkId)}/${action}`, {
        body: { ...(body as object), reason },
      });
    };
  }

  return {
    getMe: () => call<Success<"getMe">>("GET", "/me"),

    // A1 Upload
    uploadFiles: (request: UploadInput) => {
      const form = new FormData();
      form.append("case_number", request.case_number);
      form.append("district_id", request.district_id);
      for (const file of request.files) form.append("files", file);
      return call<Success<"uploadFiles">>("POST", "/uploads", { body: form });
    },
    listUploads: (query: QueryOf<"listUploads"> = {}) =>
      call<Success<"listUploads">>("GET", "/uploads", { query }),
    getUpload: (batchId: string) => call<Success<"getUpload">>("GET", `/uploads/${id(batchId)}`),

    // A2 Matching
    startMatchingRun: (body?: BodyOf<"startMatchingRun">) =>
      call<Success<"startMatchingRun">>("POST", "/matching/runs", { body }),
    listMatchingRuns: (query: QueryOf<"listMatchingRuns"> = {}) =>
      call<Success<"listMatchingRuns">>("GET", "/matching/runs", { query }),
    getMatchingRun: (runId: string) =>
      call<Success<"getMatchingRun">>("GET", `/matching/runs/${id(runId)}`),
    getLinkTotals: () => call<Success<"getLinkTotals">>("GET", "/stats/links"),

    // A3 Review queue
    listReviewQueue: (query: QueryOf<"listReviewQueue"> = {}) =>
      call<Success<"listReviewQueue">>("GET", "/review-queue", { query }),
    getLink: (linkId: string) => call<Success<"getLink">>("GET", `/links/${id(linkId)}`),
    getLinkExplanation: (linkId: string) =>
      call<Success<"getLinkExplanation">>("GET", `/links/${id(linkId)}/explanation`),
    confirmLink: (linkId: string, body: BodyOf<"confirmLink"> = {}) =>
      call<Success<"confirmLink">>("POST", `/links/${id(linkId)}/confirm`, { body }),
    rejectLink: withReason<"rejectLink">("reject"),
    undoLink: withReason<"undoLink">("undo"),
    reopenLink: withReason<"reopenLink">("reopen"),

    // A4 Approvals: access requests, grants
    listAccessRequests: (query: QueryOf<"listAccessRequests">) =>
      call<Success<"listAccessRequests">>("GET", "/access-requests", { query }),
    getAccessRequest: (requestId: string) =>
      call<Success<"getAccessRequest">>("GET", `/access-requests/${id(requestId)}`),
    approveAccessRequest: (requestId: string, body: Partial<BodyOf<"approveAccessRequest">> = {}) =>
      call<Success<"approveAccessRequest">>("POST", `/access-requests/${id(requestId)}/approve`, {
        body,
      }),
    denyAccessRequest: (requestId: string, body: BodyOf<"denyAccessRequest"> = {}) => {
      const note = body.note?.trim();
      if (note !== undefined && note.length > NOTE_MAX) {
        return Promise.resolve<ApiResult<Success<"denyAccessRequest">>>({
          kind: "invalid",
          fieldErrors: [{ field: "note", code: "too_long" }],
        });
      }
      return call<Success<"denyAccessRequest">>("POST", `/access-requests/${id(requestId)}/deny`, {
        body: note ? { note } : {},
      });
    },
    listGrants: (query: QueryOf<"listGrants">) =>
      call<Success<"listGrants">>("GET", "/grants", { query }),
    revokeGrant: (grantId: string) =>
      call<Success<"revokeGrant">>("POST", `/grants/${id(grantId)}/revoke`),

    // A4a Changes, A5 Users and roles, A7 Thresholds
    listUsers: (query: QueryOf<"listUsers"> = {}) =>
      call<Success<"listUsers">>("GET", "/users", { query }),
    getUser: (userId: string) => call<Success<"getUser">>("GET", `/users/${id(userId)}`),
    listRoles: () => call<Success<"listRoles">>("GET", "/roles"),
    listJurisdictions: () => call<Success<"listJurisdictions">>("GET", "/jurisdictions"),
    getThresholds: () => call<Success<"getThresholds">>("GET", "/thresholds"),
    proposeChange: (body: BodyOf<"proposeChange">) =>
      call<Success<"proposeChange">>("POST", "/pending-changes", { body }),
    listPendingChanges: (query: QueryOf<"listPendingChanges"> = {}) =>
      call<Success<"listPendingChanges">>("GET", "/pending-changes", { query }),
    getPendingChange: (changeId: string) =>
      call<Success<"getPendingChange">>("GET", `/pending-changes/${id(changeId)}`),
    approveChange: (changeId: string, body: BodyOf<"approveChange">) =>
      call<Success<"approveChange">>("POST", `/pending-changes/${id(changeId)}/approve`, { body }),
    denyChange: (changeId: string) =>
      call<Success<"denyChange">>("POST", `/pending-changes/${id(changeId)}/deny`),

    // A6 Activity log
    listAudit: (query: QueryOf<"listAudit"> = {}) =>
      call<Success<"listAudit">>("GET", "/audit", { query }),
    verifyAuditChain: () => call<Success<"verifyAuditChain">>("POST", "/audit/verify"),

    // A8 Network graph
    searchEntities: (query: QueryOf<"searchEntities">) =>
      call<Success<"searchEntities">>("GET", "/search/entities", { query }),
    getEntityGraph: (entityId: string, query: QueryOf<"getEntityGraph"> = {}) =>
      call<Success<"getEntityGraph">>("GET", `/entities/${id(entityId)}/graph`, { query }),
    getEntityCluster: (entityId: string) =>
      call<Success<"getEntityCluster">>("GET", `/entities/${id(entityId)}/cluster`),
    getEntityPaths: (entityId: string, query: QueryOf<"getEntityPaths"> = {}) =>
      call<Success<"getEntityPaths">>("GET", `/entities/${id(entityId)}/paths`, { query }),
  };
}

export type AdminClient = ReturnType<typeof createClient>;
