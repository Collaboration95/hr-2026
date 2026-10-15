import { useEffect, useState } from "react";
import { loadDecisionSummary, type DecisionSummary } from "../decision-data";
import type { Demo } from "../types";

export type DecisionStatus = "loading" | "ready" | "unavailable";
export type DecisionState = { status: DecisionStatus; summary: DecisionSummary | null; error?: string };
const LOADING: DecisionState = { status: "loading", summary: null };

/**
 * Optional decision-layer summary. It loads once the main export is present and reloads with it
 * ("Reload local evidence"). A missing, malformed or HTML-fallback file becomes `unavailable`: the
 * Proof and map views simply omit the decision sections. A previously accepted summary stays visible
 * while a reload is in flight.
 */
export function useDecisionSummary(data: Demo | null): DecisionState {
  const [state, setState] = useState<DecisionState>(LOADING);

  useEffect(() => {
    if (!data) return;
    const controller = new AbortController();
    loadDecisionSummary(controller.signal)
      .then((summary) => {
        if (!controller.signal.aborted) setState({ status: "ready", summary });
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setState({
          status: "unavailable",
          summary: null,
          error: reason instanceof Error ? reason.message : "Decision summary unavailable.",
        });
      });
    return () => controller.abort();
  }, [data]);

  return state;
}
