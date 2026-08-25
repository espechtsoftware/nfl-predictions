/** Deep runtime validation and availability classification.
 *
 * Every nested receipt, identity, view, and cross-object binding is checked
 * before anything renders; a payload that fails anywhere classifies as
 * schema-mismatch with the failing field named. The browser checks shapes
 * and bindings only — it performs no cryptographic hash verification and
 * must never imply that it did.
 */

import {
  Availability,
  ProjectionPayload,
  ProjectionResponse,
  QueryReceipt,
  REASON_CODES,
  ReasonCode,
  SourceProjectionReceipt,
  StatusPayload,
  VIEW_NAMES,
  ViewName,
} from "./types";

const UTC_SECOND = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const CANONICAL_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SHA256_HEX = /^[0-9a-f]{64}$/;

/** Payloads older than this render as stale (mirrors a 6h refresh cadence). */
export const STALE_AFTER_SECONDS = 6 * 60 * 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function firewallFault(value: Record<string, unknown>, at: string): string | null {
  if (value.read_only !== true) return `${at}.read_only is not true`;
  for (const field of [
    "graph_mutation",
    "automatic_promotion",
    "application_config_mutation",
    "production_policy_authority",
  ]) {
    if (value[field] !== false) return `${at}.${field} is not false`;
  }
  return null;
}

export function isReasonCode(value: unknown): value is ReasonCode {
  return (
    typeof value === "string" &&
    (REASON_CODES as readonly string[]).includes(value)
  );
}

/** Returns a fault description, or null when the payload is a valid status. */
export function statusFault(value: unknown): string | null {
  if (!isRecord(value)) return "status is not an object";
  if (value.schema_version !== "corpus-research-ui-status/v1") {
    return "status.schema_version differs";
  }
  if (typeof value.ready !== "boolean") return "status.ready is not boolean";
  if (!isReasonCode(value.reason_code)) return "status.reason_code unknown";
  if (typeof value.message !== "string") return "status.message is not string";
  const firewall = firewallFault(value, "status");
  if (firewall !== null) return firewall;
  if (
    value.registry_id !== undefined &&
    (typeof value.registry_id !== "string" ||
      !CANONICAL_ID.test(value.registry_id))
  ) {
    return "status.registry_id is not canonical";
  }
  if (
    value.generated_at_utc !== undefined &&
    (typeof value.generated_at_utc !== "string" ||
      !UTC_SECOND.test(value.generated_at_utc))
  ) {
    return "status.generated_at_utc is not second-precision UTC";
  }
  if (value.view_row_counts !== undefined) {
    if (!isRecord(value.view_row_counts)) {
      return "status.view_row_counts is not an object";
    }
    for (const [name, count] of Object.entries(value.view_row_counts)) {
      if (!isCount(count)) return `status.view_row_counts[${name}] invalid`;
    }
  }
  return null;
}

export function isStatusPayload(value: unknown): value is StatusPayload {
  return statusFault(value) === null;
}

export function sourceReceiptFault(value: unknown): string | null {
  const at = "source_projection_receipt";
  if (!isRecord(value)) return `${at} is not an object`;
  if (value.schema_version !== "corpus-strategy-registry-projection/v2") {
    return `${at}.schema_version differs`;
  }
  if (
    typeof value.registry_id !== "string" ||
    !CANONICAL_ID.test(value.registry_id)
  ) {
    return `${at}.registry_id is not canonical`;
  }
  if (value.registry_namespace !== "corpus-strategy-registry") {
    return `${at}.registry_namespace differs`;
  }
  if (value.publication_mode !== "create_once") {
    return `${at}.publication_mode differs`;
  }
  if (value.manifest_namespace_v2_authorized !== true) {
    return `${at}.manifest_namespace_v2_authorized is not true`;
  }
  const release = value.registry_release;
  if (!isRecord(release)) return `${at}.registry_release is not an object`;
  if (typeof release.uri !== "string" || !release.uri.startsWith("gs://")) {
    return `${at}.registry_release.uri is not a gs:// uri`;
  }
  if (
    typeof release.generation !== "string" ||
    !/^\d+$/.test(release.generation)
  ) {
    return `${at}.registry_release.generation is not digits`;
  }
  if (
    typeof release.sha256 !== "string" ||
    !SHA256_HEX.test(release.sha256)
  ) {
    return `${at}.registry_release.sha256 is not 64-hex`;
  }
  if (!isCount(release.bytes) || release.bytes <= 0) {
    return `${at}.registry_release.bytes is not positive`;
  }
  if (
    typeof value.plan_sha256 !== "string" ||
    !SHA256_HEX.test(value.plan_sha256)
  ) {
    return `${at}.plan_sha256 is not 64-hex`;
  }
  if (!isCount(value.registry_node_count) || value.registry_node_count <= 0) {
    return `${at}.registry_node_count is not positive`;
  }
  if (!isCount(value.registry_relationship_count)) {
    return `${at}.registry_relationship_count is not a count`;
  }
  if (typeof value.winner_imported !== "boolean") {
    return `${at}.winner_imported is not boolean`;
  }
  if (!isCount(value.winner_count)) {
    return `${at}.winner_count is not a count`;
  }
  if (value.winner_imported !== (value.winner_count === 51)) {
    return `${at} winner-import binding differs`;
  }
  const kinds = value.kind_counts;
  if (!isRecord(kinds) || Object.keys(kinds).length === 0) {
    return `${at}.kind_counts is empty or not an object`;
  }
  let kindSum = 0;
  for (const [kind, count] of Object.entries(kinds)) {
    if (!isCount(count)) return `${at}.kind_counts[${kind}] invalid`;
    kindSum += count;
  }
  if (kindSum !== value.registry_node_count) {
    return `${at}.kind_counts sum differs from registry_node_count`;
  }
  if (
    typeof value.projection_receipt_sha256 !== "string" ||
    !SHA256_HEX.test(value.projection_receipt_sha256)
  ) {
    return `${at}.projection_receipt_sha256 is not 64-hex`;
  }
  return firewallFault(value, at);
}

export function queryReceiptFault(value: unknown): string | null {
  const at = "query_receipt";
  if (!isRecord(value)) return `${at} is not an object`;
  if (value.schema_version !== "corpus-research-ui-query-receipt/v1") {
    return `${at}.schema_version differs`;
  }
  if (value.publication_mode !== "read_only_materialization") {
    return `${at}.publication_mode differs`;
  }
  if (
    typeof value.registry_id !== "string" ||
    !CANONICAL_ID.test(value.registry_id)
  ) {
    return `${at}.registry_id is not canonical`;
  }
  if (
    typeof value.database !== "string" ||
    !CANONICAL_ID.test(value.database)
  ) {
    return `${at}.database is not canonical`;
  }
  if (value.namespace !== "corpus-strategy-registry") {
    return `${at}.namespace differs`;
  }
  if (
    typeof value.source_projection_receipt_sha256 !== "string" ||
    !SHA256_HEX.test(value.source_projection_receipt_sha256)
  ) {
    return `${at}.source_projection_receipt_sha256 is not 64-hex`;
  }
  if (
    typeof value.generated_at_utc !== "string" ||
    !UTC_SECOND.test(value.generated_at_utc)
  ) {
    return `${at}.generated_at_utc is not second-precision UTC`;
  }
  if (!Array.isArray(value.queries) || value.queries.length === 0) {
    return `${at}.queries is not a nonempty array`;
  }
  const names = new Set<string>();
  for (const [index, query] of value.queries.entries()) {
    if (!isRecord(query)) return `${at}.queries[${index}] is not an object`;
    if (typeof query.name !== "string" || query.name.length === 0) {
      return `${at}.queries[${index}].name invalid`;
    }
    if (names.has(query.name)) {
      return `${at}.queries duplicate name ${query.name}`;
    }
    names.add(query.name);
    if (
      typeof query.cypher_sha256 !== "string" ||
      !SHA256_HEX.test(query.cypher_sha256)
    ) {
      return `${at}.queries[${index}].cypher_sha256 is not 64-hex`;
    }
    if (!isCount(query.row_count)) {
      return `${at}.queries[${index}].row_count is not a count`;
    }
    if (
      typeof query.rows_sha256 !== "string" ||
      !SHA256_HEX.test(query.rows_sha256)
    ) {
      return `${at}.queries[${index}].rows_sha256 is not 64-hex`;
    }
  }
  if (value.gcs_remains_authoritative !== true) {
    return `${at}.gcs_remains_authoritative is not true`;
  }
  if (value.world_matrices_stored_in_graph !== false) {
    return `${at}.world_matrices_stored_in_graph is not false`;
  }
  if (
    typeof value.query_receipt_sha256 !== "string" ||
    !SHA256_HEX.test(value.query_receipt_sha256)
  ) {
    return `${at}.query_receipt_sha256 is not 64-hex`;
  }
  return firewallFault(value, at);
}

/** Deep projection fault: nested receipts, views, and cross-bindings. */
export function projectionFault(value: unknown): string | null {
  if (!isRecord(value)) return "projection is not an object";
  if (value.schema_version !== "corpus-research-ui-projection/v1") {
    return "projection.schema_version differs";
  }
  if (
    typeof value.registry_id !== "string" ||
    !CANONICAL_ID.test(value.registry_id)
  ) {
    return "projection.registry_id is not canonical";
  }
  if (
    typeof value.database !== "string" ||
    !CANONICAL_ID.test(value.database)
  ) {
    return "projection.database is not canonical";
  }
  if (value.namespace !== "corpus-strategy-registry") {
    return "projection.namespace differs";
  }
  if (
    typeof value.generated_at_utc !== "string" ||
    !UTC_SECOND.test(value.generated_at_utc)
  ) {
    return "projection.generated_at_utc is not second-precision UTC";
  }
  if (
    typeof value.projection_sha256 !== "string" ||
    !SHA256_HEX.test(value.projection_sha256)
  ) {
    return "projection.projection_sha256 is not 64-hex";
  }
  const firewall = firewallFault(value, "projection");
  if (firewall !== null) return firewall;

  const sourceFaultDetail = sourceReceiptFault(value.source_projection_receipt);
  if (sourceFaultDetail !== null) return sourceFaultDetail;
  const queryFaultDetail = queryReceiptFault(value.query_receipt);
  if (queryFaultDetail !== null) return queryFaultDetail;
  const source = value.source_projection_receipt as SourceProjectionReceipt;
  const receipt = value.query_receipt as QueryReceipt;

  const views = value.views;
  if (!isRecord(views)) return "projection.views is not an object";
  for (const [name, rows] of Object.entries(views)) {
    if (!Array.isArray(rows)) return `views[${name}] is not an array`;
    for (const [index, row] of rows.entries()) {
      if (!isRecord(row)) return `views[${name}][${index}] is not an object`;
    }
  }
  for (const name of VIEW_NAMES) {
    if (!(name in views)) return `required view ${name} is absent`;
  }

  const queryNames = new Set(receipt.queries.map((query) => query.name));
  const viewNames = new Set(Object.keys(views));
  for (const name of viewNames) {
    if (!queryNames.has(name)) {
      return `view ${name} has no query receipt entry`;
    }
  }
  for (const query of receipt.queries) {
    const rows = views[query.name];
    if (!Array.isArray(rows)) {
      return `query receipt names absent view ${query.name}`;
    }
    if (rows.length !== query.row_count) {
      return `views[${query.name}] length differs from receipt row_count`;
    }
  }

  if (value.registry_id !== source.registry_id) {
    return "projection.registry_id differs from source receipt";
  }
  if (value.registry_id !== receipt.registry_id) {
    return "projection.registry_id differs from query receipt";
  }
  if (value.database !== receipt.database) {
    return "projection.database differs from query receipt";
  }
  if (value.generated_at_utc !== receipt.generated_at_utc) {
    return "projection.generated_at_utc differs from query receipt";
  }
  if (
    receipt.source_projection_receipt_sha256 !==
    source.projection_receipt_sha256
  ) {
    return "query receipt source-receipt sha binding differs";
  }
  return null;
}

export function isProjectionPayload(
  value: unknown,
): value is ProjectionPayload {
  return projectionFault(value) === null;
}

/** Fault for the full 200 {status, projection} body, with cross-bindings. */
export function projectionResponseFault(value: unknown): string | null {
  if (!isRecord(value)) return "response is not an object";
  const statusFaultDetail = statusFault(value.status);
  if (statusFaultDetail !== null) return statusFaultDetail;
  const projectionFaultDetail = projectionFault(value.projection);
  if (projectionFaultDetail !== null) return projectionFaultDetail;
  const status = value.status as StatusPayload;
  const projection = value.projection as ProjectionPayload;
  if (status.ready !== true || status.reason_code !== "ready") {
    return "200 response status is not ready";
  }
  if (status.registry_id !== projection.registry_id) {
    return "status.registry_id differs from projection";
  }
  if (status.projection_sha256 !== projection.projection_sha256) {
    return "status.projection_sha256 differs from projection";
  }
  if (status.view_row_counts !== undefined) {
    for (const [name, count] of Object.entries(status.view_row_counts)) {
      const rows = projection.views[name];
      if (!Array.isArray(rows) || rows.length !== count) {
        return `status.view_row_counts[${name}] differs from views`;
      }
    }
  }
  return null;
}

export function isProjectionResponse(
  value: unknown,
): value is ProjectionResponse {
  return projectionResponseFault(value) === null;
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
    const fault = statusFault(input.body);
    if (fault === null) {
      return { state: "degraded", status: input.body as StatusPayload };
    }
    return {
      state: "schema-mismatch",
      detail: `503 body invalid: ${fault}`,
    };
  }
  if (input.httpStatus !== 200) {
    return {
      state: "schema-mismatch",
      detail: `unexpected HTTP status ${input.httpStatus}`,
    };
  }
  const fault = projectionResponseFault(input.body);
  if (fault !== null) {
    return { state: "schema-mismatch", detail: fault };
  }
  const { status, projection } = input.body as ProjectionResponse;
  const age = ageSeconds(projection.generated_at_utc, input.nowMs);
  const empty = emptyViews(projection);
  if (empty.length === VIEW_NAMES.length) {
    return { state: "empty", status };
  }
  if (age > staleAfter) {
    return {
      state: "stale",
      status,
      projection,
      emptyViews: empty,
      ageSeconds: age,
    };
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
