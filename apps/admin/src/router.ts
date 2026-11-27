import { useCallback, useEffect, useState } from "react";

/**
 * Minimal browser-history router: the path and the query string are the whole route. `navigate` pushes an
 * entry so Back and Forward work; `replace` swaps the current entry (used to leave a page the role may not
 * open). `to` may carry a query string ("/review?show=rejected"); `search` is the current one.
 */
export function usePath(): {
  path: string;
  search: string;
  navigate: (to: string) => void;
  replace: (to: string) => void;
} {
  const [place, setPlace] = useState(() => ({
    path: window.location.pathname,
    search: window.location.search,
  }));

  useEffect(() => {
    const onPop = () =>
      setPlace({ path: window.location.pathname, search: window.location.search });
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: string) => {
    if (to === window.location.pathname + window.location.search) return;
    window.history.pushState(null, "", to);
    setPlace({ path: window.location.pathname, search: window.location.search });
  }, []);

  const replace = useCallback((to: string) => {
    window.history.replaceState(null, "", to);
    setPlace({ path: window.location.pathname, search: window.location.search });
  }, []);

  return { path: place.path, search: place.search, navigate, replace };
}
