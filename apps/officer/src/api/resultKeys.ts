import { en as sharedEn, tShared, type SharedMessageKey } from "@tracex/ui";

import { isMessageKey, t, type Language, type MessageKey } from "../i18n";
import type { ApiResult } from "./http";

export type FailureResult = Exclude<ApiResult<unknown>, { kind: "ok" }>;
type FailureKind = FailureResult["kind"];

/**
 * The one place that turns a failed API result into an officer string key. Screens call `messageKeyFor`
 * and never pick keys by hand. The record is complete on purpose: a new result kind will not compile
 * until it has a key. Stubs are not here: they arrive as an "ok" result and use the `restricted.*` keys.
 */
export type FailureKey = MessageKey | SharedMessageKey;

export const failureKeys: Record<FailureKind, FailureKey> = {
  sessionExpired: "state.sessionEnded",
  notFound: "state.notFound",
  notAllowed: "state.notAllowed",
  tryAgainShortly: "error.runInProgress",
  conflict: "state.changedMeanwhile",
  invalid: "state.somethingMissing",
  tooManyAttempts: "signIn.tooManyTries",
  networkError: "state.noConnection",
  safetyPause: "error.safetyPause",
  serverError: "state.serverProblem",
};

export function messageKeyFor(result: FailureResult): FailureKey {
  return failureKeys[result.kind];
}

/** Text for a key from either catalog: the officer one, or the shared one for run-in-progress and safety pause. */
export function textForKey(key: FailureKey, lang: Language): string {
  if (isMessageKey(key)) return t(key, lang);
  if (key in sharedEn) return tShared(key, lang);
  return key;
}
