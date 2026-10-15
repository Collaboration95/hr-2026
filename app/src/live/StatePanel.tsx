import type * as React from "react";
import { Icon } from "../components/Primitives";

/** Every lifecycle state except "completed" (which renders the validated answer). */
export type Phase =
  | "idle"
  | "connecting"
  | "running"
  | "cancelled"
  | "rejected"
  | "unavailable"
  | "snapshot"
  | "invalid";

export const phaseLabel: Record<Phase | "completed", string> = {
  idle: "Waiting for a region",
  connecting: "Connecting",
  running: "Running",
  cancelled: "Cancelled",
  rejected: "Rejected",
  unavailable: "Unavailable",
  snapshot: "Snapshot changed",
  invalid: "Invalid response",
  completed: "Completed",
};

function Pipeline({ active }: { active?: 0 | 1 | 2 }) {
  const steps = ["Region", "Original ↔ Compact", "Bound receipt"];
  return (
    <ol className="live-pipeline" aria-hidden="true">
      {steps.map((step, i) => (
        <li key={step} className={active === i ? "is-active" : undefined}>
          {step}
        </li>
      ))}
    </ol>
  );
}

function Frame({
  phase,
  tone,
  icon,
  title,
  children,
  action,
}: {
  phase: Phase;
  tone: "neutral" | "review" | "error" | "unknown" | "busy";
  icon: React.ReactNode;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className={`live-state live-state--${tone}`} data-phase={phase}>
      <span className="live-state__mark" aria-hidden="true">
        {icon}
      </span>
      <div className="live-state__body">
        <h4>{title}</h4>
        {children}
        {action && <div className="live-state__action">{action}</div>}
      </div>
    </div>
  );
}

/**
 * One styled state per lifecycle phase. `reason` is the exact message shown in
 * the status line; it is repeated here only for states that failed.
 */
export default function StatePanel({
  phase,
  reason,
  notSent,
  onRetry,
}: {
  phase: Phase;
  reason: string;
  notSent: boolean;
  onRetry: () => void;
}) {
  switch (phase) {
    case "connecting":
      return (
        <Frame
          phase={phase}
          tone="busy"
          icon={<span className="pl-spinner" />}
          title="Checking the local snapshot"
        >
          <p>
            Looking for the read-only service and the identity of the data it
            loaded. Nothing can run until this succeeds.
          </p>
          <Pipeline active={0} />
        </Frame>
      );
    case "running":
      return (
        <Frame
          phase={phase}
          tone="busy"
          icon={<span className="pl-spinner" />}
          title="Reading the same region twice"
        >
          <p>
            The original source and the compact copy answer one submitted
            geometry on one snapshot. No answer is shown until the response is
            validated. Editing the region or using Cancel query discards this
            request, even if a reply arrives later.
          </p>
          <Pipeline active={1} />
        </Frame>
      );
    case "cancelled":
      return (
        <Frame
          phase={phase}
          tone="neutral"
          icon={<Icon name="close" size={20} />}
          title="Query cancelled"
        >
          <p>
            No result is displayed. If the service still replies, that late
            response is ignored.
          </p>
        </Frame>
      );
    case "rejected":
      return (
        <Frame
          phase={phase}
          tone="review"
          icon={<Icon name="alert" size={20} />}
          title={
            notSent
              ? "Rejected before sending"
              : "Rejected: no answer was computed"
          }
        >
          <p className="live-state__reason">{reason}</p>
          <p className="pl-fine">
            {notSent
              ? "Nothing was sent to the service."
              : "Larger or malformed regions are rejected, not clipped or sampled."}{" "}
            Adjust the region and run it again.
          </p>
        </Frame>
      );
    case "unavailable":
      return (
        <Frame
          phase={phase}
          tone="unknown"
          icon={<Icon name="bolt" size={20} />}
          title="Local query service unavailable"
          action={
            <button type="button" className="pl-btn" onClick={onRetry}>
              Retry connection
            </button>
          }
        >
          {reason && <p className="live-state__reason">{reason}</p>}
          <p className="pl-fine">
            Start the loopback service with{" "}
            <code>npm run dev:local --prefix app</code>, then retry. The Map,
            Cohort and Proof views stay available; no result is faked.
          </p>
        </Frame>
      );
    case "snapshot":
      return (
        <Frame
          phase={phase}
          tone="error"
          icon={<Icon name="alert" size={20} />}
          title="The service snapshot changed"
          action={
            <button type="button" className="pl-btn" onClick={onRetry}>
              Reconnect to the service
            </button>
          }
        >
          {reason && <p className="live-state__reason">{reason}</p>}
          <p className="pl-fine">
            The service restarted or loaded different data. Reconnect to
            identify the new snapshot before running again. The old answer was
            discarded.
          </p>
        </Frame>
      );
    case "invalid":
      return (
        <Frame
          phase={phase}
          tone="error"
          icon={<Icon name="alert" size={20} />}
          title="The response failed validation"
        >
          <p className="live-state__reason">{reason}</p>
          <p className="pl-fine">
            The reply did not match the request, snapshot or its own hashes, so
            no answer is shown. This is a technical discrepancy, not a finding
            about any supplier.
          </p>
        </Frame>
      );
    default:
      return (
        <Frame
          phase="idle"
          tone="neutral"
          icon={<Icon name="layers" size={20} />}
          title="Your next question stays separate"
        >
          <p>
            The original source and the retained compact copy will answer the
            same submitted geometry on one identified local snapshot. No answer
            is shown until validation succeeds.
          </p>
          <Pipeline />
        </Frame>
      );
  }
}
