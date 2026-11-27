import type { IconName, RestrictedItemType } from "@tracex/ui";

import type { components } from "../api/schema";
import type { MessageKey } from "../i18n";

export type EntityType = components["schemas"]["EntityType"];

/** An organisation is shown like a person: the officer app has no fifth group (design-flows O3). */
export const entityIcon: Record<EntityType, IconName> = {
  PERSON: "person",
  ORG: "person",
  PHONE: "phone",
  ACCOUNT: "bank",
  VEHICLE: "vehicle",
};

export const restrictedType: Record<EntityType, RestrictedItemType> = {
  PERSON: "person",
  ORG: "person",
  PHONE: "phone",
  ACCOUNT: "bank",
  VEHICLE: "vehicle",
};

export const typeInCaseKey: Record<EntityType, MessageKey> = {
  PERSON: "item.typeIn.person",
  ORG: "item.typeIn.person",
  PHONE: "item.typeIn.phone",
  ACCOUNT: "item.typeIn.account",
  VEHICLE: "item.typeIn.vehicle",
};

/** People and organisations are words, so they use the body font; numbers and IDs use mono. */
export const isName = (type: EntityType): boolean => type === "PERSON" || type === "ORG";
