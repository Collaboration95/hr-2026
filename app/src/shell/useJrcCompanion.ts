import { useCallback, useEffect, useRef, useState } from "react";
import { loadJrc, type JrcArtifact } from "../jrc-data";
import type { Demo } from "../types";

export type JrcStatus = "idle" | "loading" | "ready" | "error";
type State = { status: JrcStatus; jrc: JrcArtifact | null; error?: string };
const IDLE: State = { status: "idle", jrc: null };

/**
 * Lazy, separate JRC companion. It loads only when something asks for it, aborts
 * when the main export changes or the shell unmounts, and its failure is local:
 * Hansen review never depends on it. `load()` is also the retry after an error.
 */
export function useJrcCompanion(data: Demo | null) {
  const [state, setState] = useState<State>(IDLE);
  const status = useRef<JrcStatus>("idle");
  const request = useRef<AbortController | null>(null);

  const commit = useCallback((next: State) => {
    status.current = next.status;
    setState(next);
  }, []);

  useEffect(() => {
    request.current?.abort();
    commit(IDLE);
    return () => request.current?.abort();
  }, [data, commit]);

  const load = useCallback(() => {
    if (!data || status.current === "loading" || status.current === "ready") return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    commit({ status: "loading", jrc: null });
    loadJrc(data, controller.signal)
      .then((jrc) => {
        if (!controller.signal.aborted) commit({ status: "ready", jrc });
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        commit({
          status: "error",
          jrc: null,
          error: reason instanceof Error ? reason.message : "JRC companion unavailable.",
        });
      });
  }, [data, commit]);

  return { ...state, load };
}
