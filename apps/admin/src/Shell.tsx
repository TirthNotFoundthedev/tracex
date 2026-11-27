import { Button, Loading, Message, SideNav, TopBar } from "@tracex/ui";
import { useCallback, useEffect, useState } from "react";

import type { AdminApi } from "./api";
import { messageKeyFor, type FailureResult } from "./api/resultKeys";
import type { components } from "./api/schema";
import { t, type Language } from "./i18n";
import { entryForPath, graphEntryForPath, navFor } from "./nav";
import { usePath } from "./router";

import { ApprovalsPage } from "./pages/ApprovalsPage";
import { AuditPage } from "./pages/AuditPage";
import { GraphPage } from "./pages/GraphPage";
import { MatchingPage } from "./pages/MatchingPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { ThresholdsPage } from "./pages/ThresholdsPage";
import { UsersPage } from "./pages/UsersPage";
import { UploadPage } from "./pages/UploadPage";

type User = components["schemas"]["User"];

type Me =
  | { state: "loading" }
  | { state: "ready"; user: User; areaName: string | undefined }
  | { state: "failed"; result: FailureResult };

interface ShellProps {
  api: AdminApi;
  lang: Language;
  onLanguageChange: (lang: Language) => void;
  /** Called before the session ends because the person chose Sign out. */
  onSignOutChosen?: () => void;
}

/**
 * Signed-in frame: header, role-based left navigation and the page area. The role comes from GET /me, not
 * from the sign-in answer. Hiding a menu item is a convenience only; each page still handles the API saying no.
 */
export function Shell({ api, lang, onLanguageChange, onSignOutChosen }: ShellProps) {
  const { path, search, navigate, replace } = usePath();
  const [me, setMe] = useState<Me>({ state: "loading" });

  const load = useCallback(async () => {
    setMe({ state: "loading" });
    const result = await api.client.getMe();
    if (result.kind !== "ok") {
      // A dead session already moved the app back to sign-in; the rest show their message here.
      setMe({ state: "failed", result });
      return;
    }
    const user = result.data;
    let areaName: string | undefined;
    if (user.district_id) {
      const places = await api.client.listJurisdictions();
      if (places.kind === "ok") {
        areaName = places.data.items
          .flatMap((state) => state.districts)
          .find((district) => district.district_id === user.district_id)?.name;
      }
    }
    setMe({ state: "ready", user, areaName });
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const user = me.state === "ready" ? me.user : undefined;
  const entries = user ? navFor(user.role) : [];
  // An administrator who opens the graph address gets a plain "not available" page, not a silent redirect.
  const current = user
    ? (entryForPath(user.role, path) ?? graphEntryForPath(user.role, path))
    : undefined;
  const first = entries[0];

  // A path this role has no menu item for goes to its first page.
  useEffect(() => {
    if (first && !current) replace(first.path);
  }, [first, current, replace]);

  const signOut = () => {
    onSignOutChosen?.();
    void api.session.signOut();
  };

  if (me.state !== "ready") {
    return (
      <>
        <TopBar title={t("title", lang)} onLanguageChange={onLanguageChange} onSignOut={signOut} />
        <main className="admin-main">
          {me.state === "loading" ? (
            <Loading label={t("shell.loadingUser", lang)} />
          ) : (
            <Message
              kind="error"
              action={<Button onClick={() => void load()}>{t("state.tryAgain", lang)}</Button>}
            >
              {t(messageKeyFor(me.result), lang)}
            </Message>
          )}
        </main>
      </>
    );
  }

  const area = me.areaName ?? (me.user.district_id ? undefined : t("shell.noArea", lang));
  const header = {
    userName: me.user.display_name,
    ...(area ? { jurisdiction: area } : {}),
    onSignOut: signOut,
  };

  if (entries.length === 0 || !current) {
    return (
      <>
        <TopBar title={t("title", lang)} onLanguageChange={onLanguageChange} {...header} />
        <main className="admin-main">
          {entries.length === 0 ? (
            <Message kind="info">{t("shell.notForRole", lang)}</Message>
          ) : null}
        </main>
      </>
    );
  }

  return (
    <>
      <TopBar title={t(current.labelKey, lang)} onLanguageChange={onLanguageChange} {...header} />
      <div className="admin-frame">
        <SideNav
          items={entries.map((entry) => ({
            id: entry.id,
            label: t(entry.labelKey, lang),
            icon: entry.icon,
          }))}
          currentId={current.id}
          onSelect={(id) => {
            const target = entries.find((entry) => entry.id === id);
            if (target) navigate(target.path);
          }}
        />
        <main className="admin-main" data-page={current.id}>
          {current.id === "upload" ? <UploadPage api={api} lang={lang} /> : null}
          {current.id === "matching" ? <MatchingPage api={api} lang={lang} /> : null}
          {current.id === "reviewQueue" ? (
            <ReviewQueuePage
              api={api}
              lang={lang}
              path={path}
              search={search}
              navigate={navigate}
            />
          ) : null}
          {current.id === "approvals" ? (
            <ApprovalsPage api={api} lang={lang} role={me.user.role} userId={me.user.user_id} />
          ) : null}
          {current.id === "thresholds" ? (
            <ThresholdsPage api={api} lang={lang} role={me.user.role} />
          ) : null}
          {current.id === "users" ? <UsersPage api={api} lang={lang} role={me.user.role} /> : null}
          {current.id === "audit" ? <AuditPage api={api} lang={lang} role={me.user.role} /> : null}
          {current.id === "graph" ? <GraphPage api={api} lang={lang} role={me.user.role} /> : null}
        </main>
      </div>
    </>
  );
}
