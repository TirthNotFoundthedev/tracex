import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * A small router over the browser history, written here because the app has 11 routes and no nested layouts:
 * a router package would add a dependency for no gain. Each entry carries its position (`idx`) in
 * `history.state`, so the header Back button can tell "there is a page before this one" from "this is the first".
 */
export type Route =
  | { name: "home" }
  | { name: "case"; caseId: string }
  | { name: "item"; entityId: string }
  | { name: "also"; entityId: string }
  | { name: "link"; linkId: string; from: string | undefined }
  | { name: "ask"; stubId: string; from: string | undefined }
  | { name: "sent"; stubId: string; from: string | undefined }
  | { name: "unknown" };

export function parseRoute(pathname: string, search: string): Route {
  const parts = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const from = new URLSearchParams(search).get("from") ?? undefined;
  const [a, b, c] = parts;
  if (parts.length === 0 || (a === "cases" && parts.length === 1)) return { name: "home" };
  if (a === "cases" && b && parts.length === 2) return { name: "case", caseId: b };
  if (a === "items" && b && parts.length === 2) return { name: "item", entityId: b };
  if (a === "items" && b && c === "also" && parts.length === 3)
    return { name: "also", entityId: b };
  if (a === "links" && b && parts.length === 2) return { name: "link", linkId: b, from };
  if (a === "stubs" && b && c === "ask" && parts.length === 3)
    return { name: "ask", stubId: b, from };
  if (a === "stubs" && b && c === "sent" && parts.length === 3)
    return { name: "sent", stubId: b, from };
  return { name: "unknown" };
}

export interface Nav {
  route: Route;
  /** Add a history entry. */
  go: (path: string) => void;
  /** Replace the current entry (no new Back step). */
  replace: (path: string) => void;
  /** One step back, or the case list when this is the first page of the visit. */
  back: () => void;
  home: () => void;
}

const NavContext = createContext<Nav | undefined>(undefined);

function currentIndex(): number {
  const state: unknown = window.history.state;
  if (typeof state === "object" && state !== null && "idx" in state) {
    const idx = (state as { idx: unknown }).idx;
    if (typeof idx === "number") return idx;
  }
  return 0;
}

function read(): Route {
  return parseRoute(window.location.pathname, window.location.search);
}

export function NavProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(read);

  useEffect(() => {
    if (window.history.state === null) window.history.replaceState({ idx: 0 }, "");
    const onPop = () => setRoute(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((path: string) => {
    window.history.pushState({ idx: currentIndex() + 1 }, "", path);
    setRoute(read());
  }, []);
  const replace = useCallback((path: string) => {
    window.history.replaceState({ idx: currentIndex() }, "", path);
    setRoute(read());
  }, []);
  const back = useCallback(() => {
    if (currentIndex() > 0) window.history.back();
    else replace("/cases");
  }, [replace]);
  const home = useCallback(() => go("/cases"), [go]);

  const value = useMemo<Nav>(
    () => ({ route, go, replace, back, home }),
    [route, go, replace, back, home],
  );
  return <NavContext.Provider value={value}>{children}</NavContext.Provider>;
}

export function useNav(): Nav {
  const nav = useContext(NavContext);
  if (!nav) throw new Error("useNav needs a NavProvider");
  return nav;
}

const withFrom = (from?: string) => (from ? `?from=${encodeURIComponent(from)}` : "");

export const paths = {
  cases: "/cases",
  case: (caseId: string) => `/cases/${encodeURIComponent(caseId)}`,
  item: (entityId: string) => `/items/${encodeURIComponent(entityId)}`,
  also: (entityId: string) => `/items/${encodeURIComponent(entityId)}/also`,
  link: (linkId: string, from?: string) => `/links/${encodeURIComponent(linkId)}${withFrom(from)}`,
  ask: (stubId: string, from?: string) =>
    `/stubs/${encodeURIComponent(stubId)}/ask${withFrom(from)}`,
  sent: (stubId: string, from?: string) =>
    `/stubs/${encodeURIComponent(stubId)}/sent${withFrom(from)}`,
};
