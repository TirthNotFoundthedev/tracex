import { useEffect, useState } from "react";

import type { AdminApi } from "./api";
import type { components } from "./api/schema";
import { t, type AnyMessageKey, type Language } from "./i18n";

type History = components["schemas"]["LinkDetail"]["history"];
type Entry = History[number];

export interface Decision {
  state: "REJECTED" | "UNDONE";
  at: string;
  actorId: string | undefined;
  reason: string | undefined;
}

export interface Reopening {
  at: string;
  actorId: string | undefined;
  /** The reject or undo that came before. */
  earlier: Decision | undefined;
}

const actorOf = (entry: Entry): string | undefined =>
  "actor_user_id" in entry && entry.actor_user_id ? entry.actor_user_id : undefined;
const reasonOf = (entry: Entry): string | undefined =>
  "reason_text" in entry && entry.reason_text ? entry.reason_text : undefined;

/** The latest reject or undo in `history[0..before)`. */
export function lastDecision(history: History, before = history.length): Decision | undefined {
  for (let i = Math.min(before, history.length) - 1; i >= 0; i--) {
    const entry = history[i];
    if (entry && (entry.to === "REJECTED" || entry.to === "UNDONE")) {
      return {
        state: entry.to,
        at: entry.at,
        actorId: actorOf(entry),
        reason: reasonOf(entry),
      };
    }
  }
  return undefined;
}

/** Set when the link was reopened and nothing has happened to it since. */
export function reopeningOf(history: History): Reopening | undefined {
  const index = history.length - 1;
  const entry = history[index];
  if (entry && entry.to === "SUGGESTED" && (entry.from === "REJECTED" || entry.from === "UNDONE")) {
    return { at: entry.at, actorId: actorOf(entry), earlier: lastDecision(history, index) };
  }
  return undefined;
}

export interface Actor {
  name: string;
  role: components["schemas"]["Role"];
}

const ROLE_KEY: Record<Actor["role"], AnyMessageKey> = {
  JUNIOR: "role.junior",
  INVESTIGATOR: "role.investigator",
  SUPERVISOR: "role.supervisor",
  SENIOR: "role.senior",
  ADMIN: "role.admin",
};

export const roleLabel = (role: Actor["role"], lang: Language) => t(ROLE_KEY[role], lang);

/**
 * Name look-ups belong to the signed-in session. The cache is emptied at once when the session ends for any
 * reason (sign-out, expiry, a different person signing in), so names a SENIOR could read never reach the next
 * person at the same screen, and a refusal given to one role is never held against the next. Only a real
 * answer is kept: a found person, or a 403 or 404 (a refusal is the same for the whole session). A 429, any
 * other 5xx, a pause or a network error is dropped so the next opening asks again.
 */
interface SessionNames {
  map: Map<string, Promise<Actor | null>>;
}
const caches = new WeakMap<AdminApi, SessionNames>();

function namesFor(api: AdminApi): SessionNames {
  let names = caches.get(api);
  if (!names) {
    const fresh: SessionNames = { map: new Map() };
    names = fresh;
    caches.set(api, fresh);
    let owner = api.session.state()?.user.user_id;
    api.session.subscribe((state) => {
      const next = state?.user.user_id;
      if (next === owner && state) return;
      owner = next;
      // A new map, so an answer still on its way from the old session cannot land in the new one.
      fresh.map = new Map();
    });
  }
  return names;
}

function lookup(api: AdminApi, id: string): Promise<Actor | null> {
  const names = namesFor(api);
  const map = names.map;
  const kept = map.get(id);
  if (kept) return kept;
  const found = api.client.getUser(id).then((result) => {
    if (result.kind === "ok") return { name: result.data.display_name, role: result.data.role };
    if (result.kind !== "notAllowed" && result.kind !== "notFound") map.delete(id);
    return null;
  });
  map.set(id, found);
  return found;
}

/**
 * Names for the people who decided. Only the user id is on the link; a person who may not read user
 * details (a supervisor) gets null and the screen words the line without a name.
 * The result holds an id once its lookup is finished.
 */
export function useActors(
  api: AdminApi,
  ids: (string | undefined)[],
): Record<string, Actor | null> {
  const wanted = [...new Set(ids.filter((id): id is string => id !== undefined))].sort();
  const key = wanted.join(",");
  const [actors, setActors] = useState<Record<string, Actor | null>>({});
  useEffect(() => {
    let live = true;
    for (const id of key ? key.split(",") : []) {
      void lookup(api, id).then((actor) => {
        if (live) setActors((now) => (id in now ? now : { ...now, [id]: actor }));
      });
    }
    return () => {
      live = false;
    };
  }, [api, key]);
  return actors;
}
