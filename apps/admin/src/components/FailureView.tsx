import { Button, Message } from "@tracex/ui";

import { messageKeyFor, type FailureResult } from "../api/resultKeys";
import { t, type Language } from "../i18n";

interface FailureViewProps {
  result: FailureResult;
  lang: Language;
  /** Offers "Try again" when given. */
  onRetry?: () => void;
}

/**
 * Every failed call on every page renders here, so the status mapping (404 plain not-found, 403 not allowed,
 * 409 run in progress, any 503 the safety pause, 429, 422) lives in `resultKeys` only.
 */
export function FailureView({ result, lang, onRetry }: FailureViewProps) {
  return (
    <Message
      kind="error"
      {...(onRetry
        ? { action: <Button onClick={onRetry}>{t("state.tryAgain", lang)}</Button> }
        : {})}
    >
      {t(messageKeyFor(result), lang)}
    </Message>
  );
}
