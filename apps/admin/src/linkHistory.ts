import type { components } from "./api/schema";
import { t, type AnyMessageKey, type Language } from "./i18n";

type History = components["schemas"]["LinkDetail"]["history"];
type Entry = History[number];

export interface Decision {
  state: "REJECTED" | "UNDONE";
  at: string;
  actor: Actor | null;
  reason: string | undefined;
}

export interface Reopening {
  at: string;
  actor: Actor | null;
  /** The reject or undo that came before. */
  earlier: Decision | undefined;
}

/** The deciding person as the API gave them; null when the viewer may not know them (D70). */
const actorOf = (entry: Entry): Actor | null =>
  "actor" in entry && entry.actor
    ? { name: entry.actor.display_name, role: entry.actor.role }
    : null;
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
        actor: actorOf(entry),
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
    return { at: entry.at, actor: actorOf(entry), earlier: lastDecision(history, index) };
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
