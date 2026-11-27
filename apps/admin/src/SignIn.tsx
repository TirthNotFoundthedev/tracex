import { Button, Message, TextField } from "@tracex/ui";
import { useState, type FormEvent } from "react";

import type { Session } from "./api/session";
import { messageKeyFor } from "./api/resultKeys";
import { t, type AnyMessageKey, type Language } from "./i18n";

interface SignInProps {
  session: Session;
  lang: Language;
  /** True after the session ended on its own (expired or refused), so the page says so. */
  sessionEnded: boolean;
}

export function SignIn({ session, lang, sessionEnded }: SignInProps) {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const [working, setWorking] = useState(false);
  const [problem, setProblem] = useState<AnyMessageKey | undefined>(undefined);

  async function submit(event: FormEvent) {
    event.preventDefault();
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

  const notice: AnyMessageKey | undefined =
    problem ?? (sessionEnded ? "state.sessionEnded" : undefined);

  return (
    <main className="admin-signin">
      <h2>{t("signIn.title", lang)}</h2>
      <form onSubmit={(event) => void submit(event)} noValidate>
        {notice ? <Message kind="error">{t(notice, lang)}</Message> : null}
        <TextField
          label={t("signIn.userId", lang)}
          value={userId}
          autoComplete="username"
          onChange={setUserId}
        />
        <TextField
          label={t("signIn.password", lang)}
          type={shown ? "text" : "password"}
          value={password}
          autoComplete="current-password"
          onChange={setPassword}
        />
        <Button onClick={() => setShown((value) => !value)}>
          {t(shown ? "signIn.hide" : "signIn.show", lang)}
        </Button>
        <Button type="submit" variant="primary" disabled={working}>
          {t(working ? "signIn.working" : "signIn.submit", lang)}
        </Button>
        <p>{t("signIn.forgot", lang)}</p>
      </form>
    </main>
  );
}
