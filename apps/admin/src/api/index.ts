import { apiBaseFromEnv, createClient, type AdminClient } from "./client";
import type { FetchLike } from "./http";
import { createSession, type Session } from "./session";

export interface AdminApi {
  session: Session;
  client: AdminClient;
}

/** One session and one client over `VITE_API_URL`. Tests pass a fake `fetch`. */
export function createApi(options: { baseUrl?: string; fetch?: FetchLike } = {}): AdminApi {
  const baseUrl = options.baseUrl ?? apiBaseFromEnv();
  const base = options.fetch ? { fetch: options.fetch } : {};
  const session = createSession({ baseUrl, ...base });
  return { session, client: createClient({ baseUrl, session, ...base }) };
}
