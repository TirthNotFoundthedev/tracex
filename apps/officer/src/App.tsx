import { UiProvider } from "@tracex/ui";
import { useEffect, useMemo, useRef, useState } from "react";

import { createClient } from "./api/client";
import type { FetchLike } from "./api/http";
import { createSession, type Session, type SessionState } from "./api/session";
import { AppContext, makeTt, useApp } from "./app-context";
import { FailureView } from "./components/FailureView";
import { Screen } from "./components/Screen";
import type { Language } from "./i18n";
import { NavProvider, useNav } from "./router";
import { AskForAccess, RequestSent } from "./screens/Access";
import { AlsoAppears } from "./screens/AlsoAppears";
import { Case } from "./screens/Case";
import { Cases } from "./screens/Cases";
import { Item } from "./screens/Item";
import { SignIn } from "./screens/SignIn";
import { WhyLinked } from "./screens/WhyLinked";

const LANG_KEY = "tracex.officer.lang";

/** The language is the only thing kept in browser storage, and only for this tab's session. Tokens never are (D64). */
function storedLanguage(): Language | undefined {
  try {
    const value = window.sessionStorage.getItem(LANG_KEY);
    return value === "en" || value === "hi" ? value : undefined;
  } catch {
    return undefined;
  }
}

export interface AppProps {
  /** API origin; empty means the page's own origin. */
  baseUrl?: string;
  fetchImpl?: FetchLike;
  initialLang?: Language;
}

function Routes() {
  const { route } = useNav();
  switch (route.name) {
    case "home":
      return <Cases />;
    case "case":
      return <Case caseId={route.caseId} />;
    case "item":
      return <Item entityId={route.entityId} />;
    case "also":
      return <AlsoAppears entityId={route.entityId} />;
    case "link":
      return <WhyLinked linkId={route.linkId} from={route.from} />;
    case "ask":
      return <AskForAccess stubId={route.stubId} from={route.from} />;
    case "sent":
      return <RequestSent from={route.from} />;
    default:
      return <UnknownPage />;
  }
}

function UnknownPage() {
  const { tt } = useApp();
  return (
    <Screen title={tt("title")}>
      <FailureView result={{ kind: "notFound" }} />
    </Screen>
  );
}

function Signed({
  session,
  lang,
  setLang,
  state,
  sessionEnded,
  client,
  onLeave,
}: {
  session: Session;
  lang: Language;
  setLang: (lang: Language) => void;
  state: SessionState | undefined;
  sessionEnded: boolean;
  client: ReturnType<typeof createClient>;
  onLeave: () => void;
}) {
  const nav = useNav();
  if (!state) {
    return <SignIn session={session} lang={lang} setLang={setLang} sessionEnded={sessionEnded} />;
  }
  return (
    <AppContext.Provider
      value={{
        client,
        session,
        user: state.user,
        lang,
        setLang,
        tt: makeTt(lang),
        signOut: () => {
          onLeave();
          void session.signOut();
          nav.replace("/");
        },
      }}
    >
      <Routes />
    </AppContext.Provider>
  );
}

export function App({ baseUrl = "", fetchImpl, initialLang }: AppProps) {
  const fetchOption = fetchImpl ? { fetch: fetchImpl } : {};
  const session = useMemo(() => createSession({ baseUrl, ...fetchOption }), []); // eslint-disable-line react-hooks/exhaustive-deps
  const client = useMemo(() => createClient({ baseUrl, session, ...fetchOption }), [session]); // eslint-disable-line react-hooks/exhaustive-deps
  const [state, setState] = useState<SessionState | undefined>(session.state());
  const [sessionEnded, setSessionEnded] = useState(false);
  const wasSignedIn = useRef(false);
  const leaving = useRef(false);
  const [lang, setLangState] = useState<Language>(initialLang ?? storedLanguage() ?? "en");

  useEffect(() => {
    return session.subscribe((next) => {
      if (next) {
        wasSignedIn.current = true;
        setSessionEnded(false);
      } else if (wasSignedIn.current) {
        // Signing out by choice also lands here; only an end the officer did not ask for gets the message.
        setSessionEnded(!leaving.current);
        leaving.current = false;
      }
      setState(next);
    });
  }, [session]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (next: Language) => {
    setLangState(next);
    try {
      window.sessionStorage.setItem(LANG_KEY, next);
    } catch {
      // Storage can be blocked; the choice then lasts until the page is reloaded.
    }
  };

  return (
    <UiProvider lang={lang} app="officer">
      <NavProvider>
        <Signed
          session={session}
          client={client}
          lang={lang}
          setLang={setLang}
          state={state}
          sessionEnded={sessionEnded}
          onLeave={() => {
            leaving.current = true;
          }}
        />
      </NavProvider>
    </UiProvider>
  );
}
