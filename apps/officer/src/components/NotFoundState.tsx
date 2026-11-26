import { Button } from "@tracex/ui";

import { t, type Language } from "../i18n";

/** Shown for every 404. It never says why: an unknown, hidden or removed item looks the same (D43). */
export function NotFoundState({ lang = "en", onBack }: { lang?: Language; onBack: () => void }) {
  return (
    <div role="status">
      <p>{t("state.notFound", lang)}</p>
      <Button variant="primary" onClick={onBack}>
        {t("state.backToCases", lang)}
      </Button>
    </div>
  );
}
