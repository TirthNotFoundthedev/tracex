import { createContext, useContext, type ReactNode } from "react";

import { format, tShared, type Language, type SharedMessageKey } from "../i18n";

export type AppVariant = "officer" | "admin";

interface UiSettings {
  lang: Language;
  app: AppVariant;
}

const UiContext = createContext<UiSettings>({ lang: "en", app: "officer" });

interface UiProviderProps extends Partial<UiSettings> {
  children: ReactNode;
}

/**
 * Sets language and app variant for every component below it. The wrapper carries
 * `data-app` so tokens.css switches target size and text size (DESIGN_RULES section 3),
 * and `lang` so Devanagari line height applies (section 13).
 */
export function UiProvider({ lang = "en", app = "officer", children }: UiProviderProps) {
  return (
    <UiContext.Provider value={{ lang, app }}>
      <div className="tx-root" data-app={app} lang={lang}>
        {children}
      </div>
    </UiContext.Provider>
  );
}

export function useUi() {
  const { lang, app } = useContext(UiContext);
  const t = (key: SharedMessageKey, values?: Record<string, string | number>) => {
    const text = tShared(key, lang);
    return values ? format(text, values) : text;
  };
  return { lang, app, t };
}
