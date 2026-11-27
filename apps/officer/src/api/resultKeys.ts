import type { MessageKey } from "../i18n";
import type { ApiResult } from "./http";

export type FailureResult = Exclude<ApiResult<unknown>, { kind: "ok" }>;
type FailureKind = FailureResult["kind"];

/**
 * The one place that turns a failed API result into an officer string key. Screens call `messageKeyFor`
 * and never pick keys by hand. The record is complete on purpose: a new result kind will not compile
 * until it has a key. Stubs are not here: they arrive as an "ok" result and use the `restricted.*` keys.
 */
export const failureKeys: Record<FailureKind, MessageKey> = {
  sessionExpired: "state.sessionEnded",
  notFound: "state.notFound",
  notAllowed: "state.notAllowed",
  tryAgainShortly: "state.runInProgress",
  conflict: "state.changedMeanwhile",
  invalid: "state.somethingMissing",
  tooManyAttempts: "signIn.tooManyTries",
  networkError: "state.noConnection",
  safetyPause: "state.safetyPause",
  serverError: "state.serverProblem",
};

export function messageKeyFor(result: FailureResult): MessageKey {
  return failureKeys[result.kind];
}
