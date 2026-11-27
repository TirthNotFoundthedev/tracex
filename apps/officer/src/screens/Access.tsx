import { Button, Loading, Message, TextField } from "@tracex/ui";
import { useState } from "react";

import { isValidReason, REASON_MAX, REASON_MIN, type OfficerClient } from "../api/client";
import type { FailureResult } from "../api/resultKeys";
import { useApp } from "../app-context";
import { FailureView } from "../components/FailureView";
import { Screen } from "../components/Screen";
import type { MessageKey } from "../i18n";
import { paths, useNav, type Nav } from "../router";

function reasonProblem(trimmed: string): MessageKey | undefined {
  if (trimmed.length === 0) return "access.errorEmpty";
  if (trimmed.length < REASON_MIN) return "access.errorShort";
  if (trimmed.length > REASON_MAX) return "access.errorLong";
  return undefined;
}

/** Back to the case the officer came from, or to My cases when that is unknown or gone. */
async function backToCase(
  client: OfficerClient,
  from: string | undefined,
  nav: Nav,
): Promise<void> {
  if (from) {
    const result = await client.getEntity(from);
    if (result.kind === "ok") {
      nav.go(paths.case(result.data.case.case_id));
      return;
    }
  }
  nav.home();
}

/** O10: the reason is 10 to 500 characters. The API checks it again; this only saves a round trip. */
export function AskForAccess({ stubId, from }: { stubId: string; from: string | undefined }) {
  const { client, tt } = useApp();
  const nav = useNav();
  const [reason, setReason] = useState("");
  const [fieldError, setFieldError] = useState<MessageKey>();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<FailureResult>();

  async function send() {
    const trimmed = reason.trim();
    const problem = reasonProblem(trimmed);
    setFieldError(problem);
    if (problem || !isValidReason(trimmed)) return;
    setFailure(undefined);
    setBusy(true);
    const result = await client.createAccessRequest({ stub_id: stubId, reason: trimmed });
    setBusy(false);
    if (result.kind === "ok") nav.replace(paths.sent(stubId, from));
    else setFailure(result);
  }

  const cooldown =
    failure?.kind === "conflict" && failure.code === "REQUEST_COOLDOWN"
      ? "restricted.cooldown"
      : failure?.kind === "conflict" && failure.code === "REQUEST_LIMIT"
        ? "restricted.tooManyWaiting"
        : undefined;

  // The stub is gone or was never theirs (404): there is nothing to ask for, so no form.
  if (failure?.kind === "notFound") {
    return (
      <Screen title={tt("access.title")}>
        <FailureView result={failure} />
      </Screen>
    );
  }

  return (
    <Screen title={tt("access.title")}>
      <p className="tx-body">{tt("access.intro")}</p>
      {cooldown ? (
        <Message
          kind="error"
          action={
            <Button variant="primary" onClick={() => void backToCase(client, from, nav)}>
              {tt("sent.back")}
            </Button>
          }
        >
          {tt(cooldown)}
        </Message>
      ) : failure ? (
        <FailureView result={failure} />
      ) : null}
      <TextField
        label={tt("access.reasonLabel")}
        hint={tt("access.reasonHint")}
        multiline
        value={reason}
        {...(fieldError ? { error: tt(fieldError) } : {})}
        onChange={(value) => {
          setReason(value);
          setFieldError(undefined);
        }}
      />
      {busy ? <Loading label={tt("access.sending")} /> : null}
      <div className="tx-actions">
        <Button variant="primary" disabled={busy} onClick={() => void send()}>
          {tt("access.send")}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={nav.back}>
          {tt("access.cancel")}
        </Button>
      </div>
    </Screen>
  );
}

/** O11 */
export function RequestSent({ from }: { from: string | undefined }) {
  const { client, tt } = useApp();
  const nav = useNav();

  return (
    <Screen title={tt("access.title")}>
      <Message kind="success">{tt("sent.message")}</Message>
      <div className="tx-actions">
        <Button variant="primary" onClick={() => void backToCase(client, from, nav)}>
          {tt("sent.back")}
        </Button>
      </div>
    </Screen>
  );
}
