import { Breadcrumb, Loading, Message, TopBar, type BreadcrumbItem } from "@tracex/ui";
import { useEffect, useState, type ReactNode } from "react";

import { useApp } from "../app-context";
import { useNav } from "../router";
import { FailureView } from "./FailureView";
import type { Loaded } from "../lib/useLoad";
import type { MessageKey } from "../i18n";

const WARN_BEFORE_MS = 2 * 60 * 1000;

/** "You will be signed out in 2 minutes." The 8 hour limit is fixed by the server, so there is no way to extend it. */
function SessionNotice() {
  const { session, tt } = useApp();
  const [near, setNear] = useState(false);
  useEffect(() => {
    const endsAt = session.state()?.endsAt;
    if (endsAt === undefined) return;
    const wait = endsAt - WARN_BEFORE_MS - Date.now();
    if (wait <= 0) {
      setNear(true);
      return;
    }
    const timer = setTimeout(() => setNear(true), wait);
    return () => clearTimeout(timer);
  }, [session]);
  return near ? <Message kind="info">{tt("state.sessionEnding")}</Message> : null;
}

/**
 * Header (Back, title, language switch) and the "My cases" trail on every screen after sign-in, so home is one
 * click from anywhere. `trail` lists the steps before the current one; the current title is added last.
 */
export function Screen({
  title,
  trail = [],
  showTrail = true,
  children,
}: {
  title: string;
  trail?: BreadcrumbItem[];
  showTrail?: boolean;
  children: ReactNode;
}) {
  const { tt, setLang } = useApp();
  const nav = useNav();
  const items: BreadcrumbItem[] = [{ label: tt("nav.myCases"), onClick: nav.home }, ...trail];
  return (
    <>
      <TopBar title={title} onBack={nav.back} onLanguageChange={setLang} />
      <main className="officer-page">
        {showTrail ? <Breadcrumb items={[...items, { label: title }]} /> : null}
        <SessionNotice />
        {children}
      </main>
    </>
  );
}

/**
 * The header title while a page loads or fails. "Loading..." only while the answer is pending; a 404 names
 * itself "Not found"; any other failure says there was a problem.
 */
export function titleFor<T>(
  loaded: Loaded<T>,
  tt: (key: MessageKey) => string,
  whenOk: (data: T) => string,
): string {
  if (loaded.status === "ok") return whenOk(loaded.data);
  if (loaded.status === "failed") {
    return tt(loaded.result.kind === "notFound" ? "state.notFoundTitle" : "state.problemTitle");
  }
  return tt("state.loading");
}

/** Loading, failure, or the screen body once the data is here. */
export function Await<T>({
  loaded,
  label,
  onRetry,
  children,
}: {
  loaded: Loaded<T>;
  label?: string;
  onRetry: () => void;
  children: (data: T) => ReactNode;
}) {
  if (loaded.status === "loading") return <Loading {...(label ? { label } : {})} />;
  if (loaded.status === "failed") return <FailureView result={loaded.result} onRetry={onRetry} />;
  return <>{children(loaded.data)}</>;
}
