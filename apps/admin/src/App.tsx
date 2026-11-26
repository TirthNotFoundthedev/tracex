import { TopBar, UiProvider } from "@tracex/ui";
import { useEffect, useRef, useState } from "react";

import "./app.css";
import { createApi, type AdminApi } from "./api";
import { SignIn } from "./SignIn";
import { Shell } from "./Shell";
import { t, type Language } from "./i18n";
import type { SessionState } from "./api/session";

interface AppProps {
  /** Tests pass a session over a fake `fetch`; the real app builds its own from `VITE_API_URL`. */
  api?: AdminApi;
  lang?: Language;
}

export function App({ api: given, lang: initialLang = "en" }: AppProps) {
  const [api] = useState(() => given ?? createApi());
  const [lang, setLang] = useState<Language>(initialLang);
  const [state, setState] = useState<SessionState | undefined>(() => api.session.state());
  const everSignedIn = useRef(false);
  const [sessionEnded, setSessionEnded] = useState(false);

  useEffect(() => api.session.subscribe(setState), [api]);

  useEffect(() => {
    if (state) everSignedIn.current = true;
    // Signed out after being signed in, and not by the sign-out button: say the session ended.
    else if (everSignedIn.current) setSessionEnded(true);
  }, [state]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <UiProvider app="admin" lang={lang}>
      {state ? (
        <Shell api={api} lang={lang} onLanguageChange={setLang} />
      ) : (
        <>
          <TopBar title={t("title", lang)} onLanguageChange={setLang} />
          <SignIn session={api.session} lang={lang} sessionEnded={sessionEnded} />
        </>
      )}
    </UiProvider>
  );
}
