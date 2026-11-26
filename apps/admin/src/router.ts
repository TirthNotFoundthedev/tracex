import { useCallback, useEffect, useState } from "react";

/**
 * Minimal browser-history router: the path is the whole route. `navigate` pushes an entry so Back and
 * Forward work; `replace` swaps the current entry (used to leave a page the role may not open).
 */
export function usePath(): {
  path: string;
  navigate: (to: string) => void;
  replace: (to: string) => void;
} {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to: string) => {
    if (to === window.location.pathname) return;
    window.history.pushState(null, "", to);
    setPath(to);
  }, []);

  const replace = useCallback((to: string) => {
    window.history.replaceState(null, "", to);
    setPath(to);
  }, []);

  return { path, navigate, replace };
}
