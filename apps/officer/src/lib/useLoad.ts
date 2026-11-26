import { useCallback, useEffect, useState } from "react";

import type { ApiResult } from "../api/http";
import type { FailureResult } from "../api/resultKeys";

export type Loaded<T> =
  { status: "loading" } | { status: "ok"; data: T } | { status: "failed"; result: FailureResult };

/** Runs `load` when `key` changes (and on `reload`). A late answer for an old key is dropped. */
export function useLoad<T>(
  load: () => Promise<ApiResult<T>>,
  key: string,
): [Loaded<T>, () => void] {
  const [state, setState] = useState<Loaded<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    setState({ status: "loading" });
    void load().then((result) => {
      if (!current) return;
      setState(
        result.kind === "ok" ? { status: "ok", data: result.data } : { status: "failed", result },
      );
    });
    return () => {
      current = false;
    };
    // `load` is rebuilt on every render; `key` names what it loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return [state, reload];
}
