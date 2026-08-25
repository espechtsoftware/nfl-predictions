/** Runtime schema guards and availability classification.
 *
 * Anything that fails these guards is a schema mismatch — rendered as such,
 * never silently coerced. Missing values stay missing; nothing becomes zero.
 */

import {
  Availability,
  ProjectionPayload,
  ProjectionResponse,
  REASON_CODES,
  ReasonCode,
  StatusPayload,
  VIEW_NAMES,
  ViewName,
} from "./types";

const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

/** Payloads older than this render as stale (mirrors a 6h refresh cadence). */
export const STALE_AFTER_SECONDS = 6 * 60 * 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasFirewall(value: Record<string, unknown>): boolean {
  return (
    value.read_only === true &&
    value.graph_mutation === false &&
    value.automatic_promotion === false &&
    value.application_config_mutation === false &&
    value.production_policy_authority === false
  );
}

export function isReasonCode(value: unknown): value is ReasonCode {
  return (
    typeof value === "string" && (REASON_CODES as readonly string[]).includes(value)
  );
}

export function isStatusPayload(value: unknown): value is StatusPayload {
  if (!isRecord(value)) return false;
  return (
    value.schema_version === "corpus-research-ui-status/v1" &&
    typeof value.ready === "boolean" &&
    isReasonCode(value.reason_code) &&
    typeof value.message === "string" &&
    hasFirewall(value)
  );
}

export function isProjectionPayload(value: unknown): value is ProjectionPayload {
  if (!isRecord(value)) return false;
  if (value.schema_version !== "corpus-research-ui-projection/v1") return false;
  if (typeof value.registry_id !== "string") return false;
  if (typeof value.database !== "string") return false;
  if (value.namespace !== "corpus-strategy-registry") return false;
  if (
    typeof value.generated_at_utc !== "string" ||
    !UTC_SECOND.test(value.generated_at_utc)
  ) {
    return false;
  }
  if (typeof value.projection_sha256 !== "string") return false;
  if (!hasFirewall(value)) return false;
  const views = value.views;
  if (!isRecord(views)) return false;
  for (const name of VIEW_NAMES) {
    if (!Array.isArray(views[name])) return false;
  }
  return isRecord(value.source_projection_receipt) && isRecord(value.query_receipt);
}

export function isProjectionResponse(
  value: unknown,
): value is ProjectionResponse {
  return (
    isRecord(value) &&
    isStatusPayload(value.status) &&
    isProjectionPayload(value.projection)
  );
}

export function ageSeconds(generatedAtUtc: string, nowMs: number): number {
  const generated = Date.parse(generatedAtUtc);
  if (Number.isNaN(generated)) return Number.POSITIVE_INFINITY;
  return Math.max(0, Math.round((nowMs - generated) / 1000));
}

export function emptyViews(projection: ProjectionPayload): ViewName[] {
  return VIEW_NAMES.filter((name) => projection.views[name]?.length === 0);
}

/** Classify a projection-endpoint outcome into the availability model. */
export function classifyProjectionOutcome(input: {
  readonly httpStatus: number;
  readonly body: unknown;
  readonly nowMs: number;
  readonly staleAfterSeconds?: number;
}): Availability {
  const staleAfter = input.staleAfterSeconds ?? STALE_AFTER_SECONDS;
  if (input.httpStatus === 401 || input.httpStatus === 403) {
    return { state: "unauthorized", httpStatus: input.httpStatus };
  }
  if (input.httpStatus === 503) {
    if (isStatusPayload(input.body)) {
      return { state: "degraded", status: input.body };
    }
    return {
      state: "schema-mismatch",
      detail: "503 body is not a corpus-research-ui-status/v1 payload",
    };
  }
  if (input.httpStatus !== 200) {
    return {
      state: "schema-mismatch",
      detail: `unexpected HTTP status ${input.httpStatus}`,
    };
  }
  if (!isProjectionResponse(input.body)) {
    return {
      state: "schema-mismatch",
      detail: "200 body is not a {status, projection} response",
    };
  }
  const { status, projection } = input.body;
  const age = ageSeconds(projection.generated_at_utc, input.nowMs);
  const empty = emptyViews(projection);
  if (empty.length === VIEW_NAMES.length) {
    return { state: "empty", status };
  }
  if (age > staleAfter) {
    return { state: "stale", status, projection, ageSeconds: age };
  }
  if (empty.length > 0) {
    return {
      state: "partial",
      status,
      projection,
      emptyViews: empty,
      ageSeconds: age,
    };
  }
  return { state: "ready", status, projection, ageSeconds: age };
}
