/** Shared honest-state components.
 *
 * Every page renders availability through these so loading, empty, partial,
 * stale, degraded, unauthorized, and schema-mismatch states are visually
 * distinct and cannot be mistaken for negative results. Missing renders as
 * missing — never as zero.
 */

import { ReactNode } from "react";
import { Availability, StatusPayload } from "../api/types";

export function EvidenceBadge({ tier }: { tier: string }) {
  return (
    <span className="evidence-badge" data-testid="evidence-badge" data-tier={tier}>
      {tier}
    </span>
  );
}

export function StaleBadge({ ageSeconds }: { ageSeconds: number }) {
  const hours = (ageSeconds / 3600).toFixed(1);
  return (
    <span className="stale-badge" data-testid="stale-badge" role="status">
      stale — last verified {hours}h ago
    </span>
  );
}

export function LoadingState() {
  return (
    <p className="state state-loading" data-testid="state-loading" role="status">
      Loading projection…
    </p>
  );
}

export function EmptyState({ status }: { status: StatusPayload }) {
  return (
    <div className="state state-empty" data-testid="state-empty">
      <p>The projection is valid but contains no rows yet.</p>
      <p className="state-detail">
        registry {status.registry_id ?? "—"} · generated{" "}
        {status.generated_at_utc ?? "—"}
      </p>
    </div>
  );
}

export function DegradedState({ status }: { status: StatusPayload }) {
  return (
    <div
      className="state state-degraded"
      data-testid="state-degraded"
      role="alert"
    >
      <p>
        Projection unavailable — the application is healthy but degraded.
      </p>
      <p className="state-detail">
        reason: <code>{status.reason_code}</code> — {status.message}
      </p>
    </div>
  );
}

export function UnauthorizedState({ httpStatus }: { httpStatus: 401 | 403 }) {
  return (
    <div
      className="state state-unauthorized"
      data-testid="state-unauthorized"
      role="alert"
    >
      <p>Not authorized to read the research projection (HTTP {httpStatus}).</p>
    </div>
  );
}

export function UnreachableState({ detail }: { detail: string }) {
  return (
    <div
      className="state state-unreachable"
      data-testid="state-unreachable"
      role="alert"
    >
      <p>
        The projection service could not be reached (transport failure, not
        a schema problem).
      </p>
      <p className="state-detail">{detail}</p>
    </div>
  );
}

export function SchemaMismatchState({ detail }: { detail: string }) {
  return (
    <div
      className="state state-schema-mismatch"
      data-testid="state-schema-mismatch"
      role="alert"
    >
      <p>The projection payload did not match the expected schema.</p>
      <p className="state-detail">{detail}</p>
      <p className="state-detail">
        Nothing is rendered from an unvalidated payload.
      </p>
    </div>
  );
}

export function PartialNotice({ emptyViews }: { emptyViews: readonly string[] }) {
  return (
    <div className="state state-partial" data-testid="state-partial" role="status">
      <p>
        Partial projection — {emptyViews.length} view
        {emptyViews.length === 1 ? "" : "s"} returned no rows:{" "}
        {emptyViews.join(", ")}. Empty is shown as empty, not as zero.
      </p>
    </div>
  );
}

/** Renders the non-ready states; returns null when content should render. */
export function AvailabilityGate({
  availability,
  children,
}: {
  availability: Availability;
  children: (
    content: Extract<Availability, { state: "ready" | "partial" | "stale" }>,
  ) => ReactNode;
}) {
  switch (availability.state) {
    case "loading":
      return <LoadingState />;
    case "empty":
      return <EmptyState status={availability.status} />;
    case "degraded":
      return <DegradedState status={availability.status} />;
    case "unauthorized":
      return <UnauthorizedState httpStatus={availability.httpStatus} />;
    case "unreachable":
      return <UnreachableState detail={availability.detail} />;
    case "schema-mismatch":
      return <SchemaMismatchState detail={availability.detail} />;
    case "ready":
    case "partial":
    case "stale":
      return <>{children(availability)}</>;
  }
}
