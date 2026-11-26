import { Button, Message } from "@tracex/ui";

import { messageKeyFor, type FailureResult } from "../api/resultKeys";
import { useApp } from "../app-context";
import { useNav } from "../router";
import { NotFoundState } from "./NotFoundState";

/**
 * One place that shows a failed API call. The wording always comes from `messageKeyFor`; hiding or showing
 * a button in the screens is a convenience, this is where every refusal from the API reaches the officer.
 */
export function FailureView({ result, onRetry }: { result: FailureResult; onRetry?: () => void }) {
  const { lang, tt } = useApp();
  const nav = useNav();

  if (result.kind === "notFound") return <NotFoundState lang={lang} onBack={nav.home} />;

  const retryable =
    result.kind === "networkError" ||
    result.kind === "serverError" ||
    result.kind === "tryAgainShortly" ||
    result.kind === "safetyPause" ||
    result.kind === "conflict";

  let action = null;
  if (retryable && onRetry) {
    action = (
      <Button variant="primary" onClick={onRetry}>
        {tt("state.tryAgain")}
      </Button>
    );
  } else if (result.kind === "notAllowed") {
    action = (
      <Button variant="primary" onClick={nav.home}>
        {tt("state.backToCases")}
      </Button>
    );
  }

  return (
    <>
      <Message kind="error" action={action}>
        {tt(messageKeyFor(result))}
      </Message>
      {result.kind === "serverError" ? <p className="tx-body">{tt("state.serverHelp")}</p> : null}
    </>
  );
}
