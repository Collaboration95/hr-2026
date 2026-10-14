import { useCallback, useEffect, useRef, useState } from "react";
import { loadDemo } from "../data";
import type { Demo } from "../types";

/**
 * Loads the frozen export. A failed reload keeps the last accepted artifact and
 * exposes `error` so the shell can show a retry banner; it never invents data.
 */
export function useDemo() {
  const [data, setData] = useState<Demo | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setError("");
    setLoading(true);
    loadDemo(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : "Evidence loading failed.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    return () => request.current?.abort();
  }, [load]);

  return { data, error, loading, load };
}
