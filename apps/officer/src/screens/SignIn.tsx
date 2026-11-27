import { Button, Loading, Message, TextField, TopBar } from "@tracex/ui";
import { useState, type FormEvent } from "react";

import type { Session } from "../api/session";
import { messageKeyFor, textForKey, type FailureKey } from "../api/resultKeys";
import { t, type Language, type MessageKey } from "../i18n";

/** O1. On success the session publishes the user and the app shows the next screen. */
export function SignIn({
  session,
  lang,
  setLang,
  sessionEnded,
}: {
  session: Session;
  lang: Language;
  setLang: (lang: Language) => void;
  sessionEnded: boolean;
}) {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const [working, setWorking] = useState(false);
  const [problem, setProblem] = useState<FailureKey>();
  const tt = (key: MessageKey) => t(key, lang);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (working) return;
    if (userId.trim() === "" || password === "") {
      setProblem("signIn.missing");
      return;
    }
    setProblem(undefined);
    setWorking(true);
    const result = await session.signIn(userId.trim(), password);
    setWorking(false);
    if (result.kind === "ok") return;
    setPassword("");
    setProblem(result.kind === "badCredentials" ? "signIn.error" : messageKeyFor(result));
  }

  return (
    <>
      <TopBar title={tt("title")} onLanguageChange={setLang} />
      <main className="officer-page">
        <h2 className="officer-heading">{tt("signIn.title")}</h2>
        {sessionEnded && !problem ? (
          <Message kind="info">{tt("state.sessionEnded")}</Message>
        ) : null}
        {problem ? (
          <Message
            kind="error"
            action={
              <Button variant="secondary" onClick={() => setProblem(undefined)}>
                {tt("signIn.tryAgain")}
              </Button>
            }
          >
            {textForKey(problem, lang)}
          </Message>
        ) : null}
        <form className="officer-form" onSubmit={(event) => void submit(event)} noValidate>
          <TextField
            label={tt("signIn.userId")}
            value={userId}
            onChange={setUserId}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
          />
          <div className="officer-password">
            <TextField
              label={tt("signIn.password")}
              type={shown ? "text" : "password"}
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
            />
            <Button variant="secondary" onClick={() => setShown((value) => !value)}>
              {tt(shown ? "signIn.hide" : "signIn.show")}
            </Button>
          </div>
          {working ? <Loading label={tt("signIn.working")} /> : null}
          <Button type="submit" variant="primary" disabled={working}>
            {tt("signIn.submit")}
          </Button>
        </form>
        <p className="tx-body">{tt("signIn.forgot")}</p>
      </main>
    </>
  );
}
