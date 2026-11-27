import type { IconName } from "@tracex/ui";

import type { MessageKey } from "./i18n";
import type { components } from "./api/schema";

export type Role = components["schemas"]["Role"];

export type PageId =
  "upload" | "matching" | "reviewQueue" | "approvals" | "users" | "audit" | "thresholds" | "graph";

export interface NavEntry {
  id: PageId;
  path: string;
  labelKey: MessageKey;
  icon: IconName;
}

const ENTRIES: Record<PageId, NavEntry> = {
  upload: { id: "upload", path: "/upload", labelKey: "nav.upload", icon: "upload" },
  matching: { id: "matching", path: "/matching", labelKey: "nav.matching", icon: "alsoAppearsIn" },
  reviewQueue: { id: "reviewQueue", path: "/review", labelKey: "nav.reviewQueue", icon: "list" },
  approvals: { id: "approvals", path: "/approvals", labelKey: "nav.approvals", icon: "confirm" },
  users: { id: "users", path: "/users", labelKey: "nav.users", icon: "person" },
  audit: { id: "audit", path: "/audit", labelKey: "nav.audit", icon: "pending" },
  thresholds: { id: "thresholds", path: "/thresholds", labelKey: "nav.thresholds", icon: "strong" },
  graph: { id: "graph", path: "/graph", labelKey: "nav.graph", icon: "picture" },
};

/**
 * Which pages each role gets a menu item for. This only hides what the API would refuse anyway (access spec
 * section 3): the API stays the one place that decides, and every refusal is still handled on the page.
 * ADMIN has no review queue and no graph (the API answers 404, D29, D47). JUNIOR and INVESTIGATOR are not
 * part of the admin panel.
 */
const BY_ROLE: Record<Role, PageId[]> = {
  JUNIOR: [],
  INVESTIGATOR: [],
  SUPERVISOR: ["reviewQueue", "approvals", "audit", "graph"],
  SENIOR: ["reviewQueue", "approvals", "users", "audit", "thresholds", "graph"],
  ADMIN: ["upload", "matching", "approvals", "users", "audit", "thresholds"],
};

export function navFor(role: Role): NavEntry[] {
  return BY_ROLE[role].map((id) => ENTRIES[id]);
}

/** The menu entry whose section contains `path`, if this role has one. */
export function entryForPath(role: Role, path: string): NavEntry | undefined {
  return navFor(role).find((entry) => path === entry.path || path.startsWith(`${entry.path}/`));
}
