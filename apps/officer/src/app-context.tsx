import { createContext, useContext } from "react";

import type { OfficerClient } from "./api/client";
import type { Session, User } from "./api/session";
import { t, type Language, type MessageKey } from "./i18n";

export interface AppContextValue {
  client: OfficerClient;
  session: Session;
  user: User;
  lang: Language;
  setLang: (lang: Language) => void;
  /** Officer string in the current language. */
  tt: (key: MessageKey, params?: Record<string, string | number>) => string;
  signOut: () => void;
}

export const AppContext = createContext<AppContextValue | undefined>(undefined);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp needs the signed-in app");
  return value;
}

export function makeTt(lang: Language): AppContextValue["tt"] {
  return (key, params) => t(key, lang, params);
}
