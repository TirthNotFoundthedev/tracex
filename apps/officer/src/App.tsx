import { t, type Language } from "./i18n";

export function App({ lang = "en" }: { lang?: Language }) {
  return <h1>{t("title", lang)}</h1>;
}
