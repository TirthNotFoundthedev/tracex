import type { AnyMessageKey } from "../i18n";
import type { ApiResult } from "./http";

export type FailureResult = Exclude<ApiResult<unknown>, { kind: "ok" }>;
type FailureKind = FailureResult["kind"];

/**
 * The one place that turns a failed API result into a string key. Screens call `messageKeyFor` and never
 * pick keys by hand. The record is complete on purpose: a new result kind will not compile until it has a
 * key. A 404 is a plain not-found, never access wording (D65). The busy-system and safety-pause texts are
 * the shared strings from packages/ui.
 */
export const failureKeys: Record<FailureKind, AnyMessageKey> = {
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

export function messageKeyFor(result: FailureResult): AnyMessageKey {
  return failureKeys[result.kind];
}
