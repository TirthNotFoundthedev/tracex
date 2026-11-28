import type { components } from "../api/schema";
import type { MessageKey } from "../i18n";

type EventType = components["schemas"]["AuditEventType"];
type TargetType = NonNullable<components["schemas"]["AuditRow"]["target_type"]>;

/**
 * Every event the log can hold, in words. The record is complete on purpose: a new event type in the
 * contract will not compile until it has words. The six words the design names (A6) keep their own keys.
 */
export const EVENT_WORDS: Record<EventType, MessageKey> = {
  AUDIT_CHAIN_STARTED: "audit.event.AUDIT_CHAIN_STARTED",
  AUTH_LOGIN_SUCCESS: "audit.event.AUTH_LOGIN_SUCCESS",
  AUTH_LOGIN_FAILED: "audit.event.AUTH_LOGIN_FAILED",
  AUTH_LOGOUT: "audit.event.AUTH_LOGOUT",
  AUTH_REFRESHED: "audit.event.AUTH_REFRESHED",
  AUTH_TOKEN_REJECTED: "audit.event.AUTH_TOKEN_REJECTED",
  AUTH_REFRESH_REUSED: "audit.event.AUTH_REFRESH_REUSED",
  CASE_LISTED: "audit.event.CASE_LISTED",
  CASE_ENTITIES_VIEWED: "audit.event.CASE_ENTITIES_VIEWED",
  ENTITY_VIEWED: "audit.event.ENTITY_VIEWED",
  LINK_VIEWED: "audit.action.viewed",
  STUB_VIEWED: "audit.event.STUB_VIEWED",
  GRAPH_VIEWED: "audit.event.GRAPH_VIEWED",
  REVIEW_QUEUE_VIEWED: "audit.event.REVIEW_QUEUE_VIEWED",
  EXPLANATION_VIEWED: "audit.event.EXPLANATION_VIEWED",
  SOURCE_LINES_VIEWED: "audit.event.SOURCE_LINES_VIEWED",
  SEARCH_RUN: "audit.event.SEARCH_RUN",
  ACCESS_DENIED: "audit.event.ACCESS_DENIED",
  LINKS_LISTED: "audit.event.LINKS_LISTED",
  LINK_AUTO_CREATED: "audit.event.LINK_AUTO_CREATED",
  LINK_SUGGESTED: "audit.event.LINK_SUGGESTED",
  LINK_DEMOTED: "audit.event.LINK_DEMOTED",
  LINK_CONFIRMED: "audit.action.confirmed",
  LINK_REJECTED: "audit.action.rejected",
  LINK_UNDONE: "audit.event.LINK_UNDONE",
  LINK_REOPENED: "audit.event.LINK_REOPENED",
  ACCESS_REQUEST_CREATED: "audit.action.requested",
  ACCESS_REQUEST_WITHDRAWN: "audit.event.ACCESS_REQUEST_WITHDRAWN",
  ACCESS_REQUEST_EXPIRED: "audit.event.ACCESS_REQUEST_EXPIRED",
  ACCESS_REQUEST_APPROVED: "audit.action.approved",
  ACCESS_REQUEST_REJECTED: "audit.event.ACCESS_REQUEST_REJECTED",
  ACCESS_GRANT_REVOKED: "audit.event.ACCESS_GRANT_REVOKED",
  ACCESS_GRANT_EXPIRED: "audit.event.ACCESS_GRANT_EXPIRED",
  ACCESS_GRANT_CLOSED: "audit.event.ACCESS_GRANT_CLOSED",
  DATA_UPLOADED: "audit.action.uploaded",
  MATCHING_RUN_STARTED: "audit.event.MATCHING_RUN_STARTED",
  MATCHING_RUN_COMPLETED: "audit.event.MATCHING_RUN_COMPLETED",
  CHANGE_PROPOSED: "audit.event.CHANGE_PROPOSED",
  CHANGE_APPROVED: "audit.event.CHANGE_APPROVED",
  CHANGE_DENIED: "audit.event.CHANGE_DENIED",
  ASSIGNMENT_CHANGED: "audit.event.ASSIGNMENT_CHANGED",
  USER_CREATED: "audit.event.USER_CREATED",
  USER_ENABLED: "audit.event.USER_ENABLED",
  USER_DISABLED: "audit.event.USER_DISABLED",
  AUDIT_VIEWED: "audit.event.AUDIT_VIEWED",
  AUDIT_VERIFY_RUN: "audit.event.AUDIT_VERIFY_RUN",
  LINK_PROMOTED: "audit.event.LINK_PROMOTED",
  LINK_WITHDRAWN: "audit.event.LINK_WITHDRAWN",
  ACCESS_REQUEST_VIEWED: "audit.event.ACCESS_REQUEST_VIEWED",
  GRANT_VIEWED: "audit.event.GRANT_VIEWED",
  CHANGE_VIEWED: "audit.event.CHANGE_VIEWED",
  ENGINE_DIVERGENCE_REVERTED: "audit.event.ENGINE_DIVERGENCE_REVERTED",
};

type Group = components["schemas"]["AuditEventGroup"];

/**
 * The six action words of the Activity log filter (design flows A6), each sent as `event_group`. The record is
 * complete on purpose: a new group in the contract will not compile until it has words.
 */
export const GROUP_WORDS: Record<Group, MessageKey> = {
  VIEWED: "audit.group.viewed",
  CONFIRMED: "audit.action.confirmed",
  REJECTED: "audit.action.rejected",
  REQUESTED: "audit.action.requested",
  APPROVED: "audit.action.approved",
  UPLOADED: "audit.action.uploaded",
};

export const GROUPS = Object.keys(GROUP_WORDS) as Group[];

/** The thing an event is about, in words. Ids are never shown. */
export const TARGET_WORDS: Record<TargetType, MessageKey> = {
  CASE: "audit.target.CASE",
  ENTITY: "audit.target.ENTITY",
  LINK: "audit.target.LINK",
  STUB: "audit.target.STUB",
  DOCUMENT: "audit.target.DOCUMENT",
  USER: "audit.target.USER",
  ACCESS_REQUEST: "audit.target.ACCESS_REQUEST",
  GRANT: "audit.target.GRANT",
  BATCH: "audit.target.BATCH",
  RUN: "audit.target.RUN",
  SETTING: "audit.target.SETTING",
  CHANGE: "audit.target.CHANGE",
  AUDIT: "audit.target.AUDIT",
  UNRESOLVED: "audit.target.UNRESOLVED",
};
