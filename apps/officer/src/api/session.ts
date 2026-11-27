import { type ApiResult, buildUrl, type FetchLike, send } from "./http";
import type { components } from "./schema";

export type User = components["schemas"]["User"];
type TokenPair = components["schemas"]["TokenPair"];

export type SignInResult = ApiResult<User> | { kind: "badCredentials" };

export type RefreshOutcome =
  | { kind: "refreshed"; token: string }
  | { kind: "signedOut" }
  | { kind: "unavailable"; reason: "networkError" | "serverError" };

export interface SessionState {
  user: User;
  /** When the refresh token dies for good (8 hour absolute lifetime), in ms since epoch. */
  endsAt: number;
}

export interface SessionOptions {
  baseUrl: string;
  fetch?: FetchLike;
  now?: () => number;
}

export interface Session {
  signIn(username: string, password: string): Promise<SignInResult>;
  signOut(): Promise<void>;
  /** Current access token, or undefined when signed out. */
  accessToken(): string | undefined;
  /**
   * Called after a 401 made with `failedToken`. If another caller already rotated the tokens, returns the new
   * token at once; otherwise runs one refresh shared by every concurrent caller.
   */
  refreshAfter(failedToken: string | undefined): Promise<RefreshOutcome>;
  state(): SessionState | undefined;
  subscribe(listener: (state: SessionState | undefined) => void): () => void;
}

/**
 * Tokens live in memory only. The contract returns the refresh token in the response body (no cookie), so a
 * page reload signs the officer out; nothing is written to storage.
 */
export function createSession(options: SessionOptions): Session {
  const fetchImpl: FetchLike = options.fetch ?? ((...args) => fetch(...args));
  const now = options.now ?? Date.now;
  const listeners = new Set<(state: SessionState | undefined) => void>();
  let tokens: { access: string; refresh: string } | undefined;
  let current: SessionState | undefined;
  let inFlight: Promise<RefreshOutcome> | undefined;

  function publish(): void {
    for (const listener of listeners) listener(current);
  }

  function adopt(pair: TokenPair): void {
    tokens = { access: pair.access_token, refresh: pair.refresh_token };
    current = { user: pair.user, endsAt: now() + pair.refresh_expires_in * 1000 };
    publish();
  }

  function clear(): void {
    tokens = undefined;
    current = undefined;
    publish();
  }

  async function rotate(): Promise<RefreshOutcome> {
    const refreshToken = tokens?.refresh;
    if (!refreshToken) return { kind: "signedOut" };
    const result = await send<TokenPair>(fetchImpl, {
      method: "POST",
      url: buildUrl(options.baseUrl, "/auth/refresh"),
      body: { refresh_token: refreshToken },
    });
    if (result.kind === "ok") {
      adopt(result.data);
      return { kind: "refreshed", token: result.data.access_token };
    }
    if (result.kind === "networkError") return { kind: "unavailable", reason: "networkError" };
    if (result.kind === "serverError") return { kind: "unavailable", reason: "serverError" };
    // Any other answer means the server refused this refresh token: the session is over.
    clear();
    return { kind: "signedOut" };
  }

  return {
    async signIn(username, password) {
      const result = await send<TokenPair>(fetchImpl, {
        method: "POST",
        url: buildUrl(options.baseUrl, "/auth/login"),
        body: { username, password },
      });
      if (result.kind === "ok") {
        adopt(result.data);
        return { kind: "ok", data: result.data.user };
      }
      if (result.kind === "unauthorized") return { kind: "badCredentials" };
      return result;
    },

    async signOut() {
      const token = tokens?.access;
      clear();
      if (token) {
        await send<undefined>(fetchImpl, {
          method: "POST",
          url: buildUrl(options.baseUrl, "/auth/logout"),
          accessToken: token,
        });
      }
    },

    accessToken: () => tokens?.access,
    state: () => current,

    async refreshAfter(failedToken) {
      if (!tokens) return { kind: "signedOut" };
      if (tokens.access !== failedToken) return { kind: "refreshed", token: tokens.access };
      inFlight ??= rotate().finally(() => {
        inFlight = undefined;
      });
      return inFlight;
    },

    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
