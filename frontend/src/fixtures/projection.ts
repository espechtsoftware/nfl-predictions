/** Deterministic, schema-accurate fixtures for every availability state.
 *
 * All identifiers, hashes, and numbers are synthetic. Hash strings are
 * shape-valid hex but illustrative — the browser never verifies hashes.
 * No fixture encodes a governed outcome; realized/contest data stay absent.
 */

import {
  AuthorityFirewall,
  ProjectionPayload,
  ProjectionResponse,
  QueryReceipt,
  SourceProjectionReceipt,
  StatusPayload,
  VIEW_NAMES,
  ViewRow,
} from "../api/types";

export const FIXTURE_GENERATED_AT = "2026-08-25T12:00:00Z";
/** A "now" 30 minutes after generation — fresh. */
export const FIXTURE_NOW_FRESH_MS = Date.parse("2026-08-25T12:30:00Z");
/** A "now" 9 hours after generation — past the 6h staleness threshold. */
export const FIXTURE_NOW_STALE_MS = Date.parse("2026-08-25T21:00:00Z");

const FIREWALL: AuthorityFirewall = {
  read_only: true,
  graph_mutation: false,
  automatic_promotion: false,
  application_config_mutation: false,
  production_policy_authority: false,
};

function hex64(seed: number): string {
  const unit = ((seed * 2654435761) >>> 0).toString(16).padStart(8, "0");
  return unit.repeat(8);
}

const KIND_COUNTS: Record<string, number> = {
  FillPreset: 7,
  RetrievalPreset: 1,
  ExperimentRun: 1,
  CorpusSnapshot: 7,
  Lineup: 21,
  Winner: 51,
};

const NODE_COUNT = Object.values(KIND_COUNTS).reduce((a, b) => a + b, 0);

export const sourceReceiptFixture: SourceProjectionReceipt = {
  schema_version: "corpus-strategy-registry-projection/v2",
  registry_id: "corpus-strategy-registry-fixture-001",
  registry_namespace: "corpus-strategy-registry",
  publication_mode: "create_once",
  manifest_namespace_v2_authorized: true,
  registry_release: {
    uri: "gs://fixture-bucket/corpus-strategy-registry/release-001.json",
    generation: "1787000000000001",
    sha256: hex64(11),
    bytes: 48_211,
  },
  plan_sha256: hex64(12),
  registry_node_count: NODE_COUNT,
  registry_relationship_count: 96,
  winner_imported: true,
  winner_count: 51,
  kind_counts: KIND_COUNTS,
  projection_receipt_sha256: hex64(13),
  ...FIREWALL,
};

const FILLS = [
  "f0-incumbent",
  "f1-lev",
  "f2-boom",
  "f3-dark",
  "f4-anchor",
  "f5-stack",
  "f6-relaxed",
] as const;

function presetRows(): ViewRow[] {
  const rows: ViewRow[] = FILLS.map((name, index) => ({
    kind: "FillPreset",
    preset_id: `fillpreset:${name}`,
    version: "v12",
    solve_budget: 40 + index,
    evidence_tier: "retrospective-simulated",
  }));
  rows.push({
    kind: "RetrievalPreset",
    preset_id: "retrievalpreset:exact-80-line194",
    version: "v12",
    entry_budget: 80,
    evidence_tier: "retrospective-simulated",
  });
  return rows;
}

function lineageRows(): ViewRow[] {
  return FILLS.slice(0, 3).map((name, index) => ({
    strategy: `strategy:${name}+exact-80`,
    fill_preset: `fillpreset:${name}`,
    retrieval_preset: "retrievalpreset:exact-80-line194",
    corpus_snapshot: `snapshot:v12-${name}`,
    selected_book: `book:v12-${name}-080`,
    experiment: "experiment:v12-panel",
    slate_count: 54 - index,
  }));
}

function comparisonRows(): ViewRow[] {
  return FILLS.slice(0, 3).map((name, index) => ({
    metric: "heldout-expected-max",
    baseline: "fillpreset:f0-incumbent",
    challenger: `fillpreset:${name}`,
    fold: `R${index}`,
    baseline_value: 168.5 + index,
    challenger_value: 168.5 + index + (index === 0 ? 0 : 0.25 * index),
    delta: index === 0 ? 0 : 0.25 * index,
    evidence_tier: "retrospective-simulated",
  }));
}

function promotionRows(): ViewRow[] {
  return [
    {
      pointer: "active-production-strategy",
      strategy: "strategy:f0-incumbent+exact-80",
      promotion_state: "incumbent",
      decided_by: "operator-receipt",
      receipt_sha256: hex64(21),
    },
  ];
}

function structureRows(): ViewRow[] {
  return [0, 1, 2].map((index) => ({
    lineup: `lineup:${hex64(30 + index).slice(0, 12)}`,
    player: `player:00-003${index}`,
    team: ["KC", "BUF", "DET"][index],
    game: ["KC@BUF", "KC@BUF", "DET@GB"][index],
    slot: ["QB", "WR1", "RB1"][index],
  }));
}

function censusRows(): ViewRow[] {
  return [
    { check: "graph_mutation", value: "false" },
    { check: "automatic_promotion", value: "false" },
    { check: "world_matrices_stored_in_graph", value: "false" },
    { check: "namespace", value: "corpus-strategy-registry" },
  ];
}

function buildViews(): Record<string, ViewRow[]> {
  return {
    "preset-registry": presetRows(),
    "strategy-lineage": lineageRows(),
    "paired-heldout-fill-retrieval-comparison": comparisonRows(),
    "active-pointer-promotion-traversal": promotionRows(),
    "lineup-player-team-game-traversal": structureRows(),
    "registry-firewall-census": censusRows(),
  };
}

function queryReceiptFor(
  views: Record<string, ViewRow[]>,
): QueryReceipt {
  return {
    schema_version: "corpus-research-ui-query-receipt/v1",
    publication_mode: "read_only_materialization",
    registry_id: sourceReceiptFixture.registry_id,
    database: "corpusresearch",
    namespace: "corpus-strategy-registry",
    source_projection_receipt_sha256:
      sourceReceiptFixture.projection_receipt_sha256,
    generated_at_utc: FIXTURE_GENERATED_AT,
    queries: VIEW_NAMES.map((name, index) => ({
      name,
      cypher_sha256: hex64(40 + index),
      row_count: views[name]?.length ?? 0,
      rows_sha256: hex64(50 + index),
    })),
    gcs_remains_authoritative: true,
    world_matrices_stored_in_graph: false,
    query_receipt_sha256: hex64(60),
    ...FIREWALL,
  };
}

function buildProjection(
  views: Record<string, ViewRow[]>,
): ProjectionPayload {
  return {
    schema_version: "corpus-research-ui-projection/v1",
    registry_id: sourceReceiptFixture.registry_id,
    database: "corpusresearch",
    namespace: "corpus-strategy-registry",
    generated_at_utc: FIXTURE_GENERATED_AT,
    source_projection_receipt: sourceReceiptFixture,
    query_receipt: queryReceiptFor(views),
    views,
    projection_sha256: hex64(61),
    ...FIREWALL,
  };
}

function statusFor(
  projection: ProjectionPayload | null,
  reason: StatusPayload["reason_code"],
  message: string,
): StatusPayload {
  const base: StatusPayload = {
    schema_version: "corpus-research-ui-status/v1",
    ready: reason === "ready",
    reason_code: reason,
    message,
    ...FIREWALL,
  };
  if (projection === null) return base;
  return {
    ...base,
    registry_id: projection.registry_id,
    database: projection.database,
    generated_at_utc: projection.generated_at_utc,
    projection_sha256: projection.projection_sha256,
    view_row_counts: Object.fromEntries(
      Object.entries(projection.views).map(([name, rows]) => [
        name,
        rows.length,
      ]),
    ),
  };
}

export const readyProjectionFixture: ProjectionPayload = buildProjection(
  buildViews(),
);

export const readyResponseFixture: ProjectionResponse = {
  status: statusFor(readyProjectionFixture, "ready", "projection materialized"),
  projection: readyProjectionFixture,
};

/** Two views empty — classified as partial. */
export const partialProjectionFixture: ProjectionPayload = buildProjection({
  ...buildViews(),
  "active-pointer-promotion-traversal": [],
  "lineup-player-team-game-traversal": [],
});

export const partialResponseFixture: ProjectionResponse = {
  status: statusFor(
    partialProjectionFixture,
    "ready",
    "projection materialized with empty views",
  ),
  projection: partialProjectionFixture,
};

/** Every view empty — classified as empty. */
export const emptyProjectionFixture: ProjectionPayload = buildProjection(
  Object.fromEntries(VIEW_NAMES.map((name) => [name, []])),
);

export const emptyResponseFixture: ProjectionResponse = {
  status: statusFor(emptyProjectionFixture, "ready", "no rows materialized"),
  projection: emptyProjectionFixture,
};

/** 503 status body — projection not configured (degraded). */
export const degradedStatusFixture: StatusPayload = statusFor(
  null,
  "projection-not-configured",
  "CORPUS_RESEARCH_UI_PROJECTION_PATH is not configured",
);

/** 503 status body — validation failed (degraded). */
export const validationFailedStatusFixture: StatusPayload = statusFor(
  null,
  "projection-validation-failed",
  "materialized projection failed validation",
);

/** A structurally wrong payload for the schema-mismatch state. */
export const schemaMismatchBodyFixture: unknown = {
  schema_version: "corpus-research-ui-projection/v999",
  views: "not-a-mapping",
};
