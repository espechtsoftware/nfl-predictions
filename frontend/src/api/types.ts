/** Strict contracts for the corpus-research read-only API.
 *
 * Mirrors src/nfl_dfs/app/corpus_research.py exactly. The browser renders
 * hashes and firewall flags; it never claims to verify them — validation is
 * server-side.
 */

export const VIEW_NAMES = [
  "preset-registry",
  "strategy-lineage",
  "paired-heldout-fill-retrieval-comparison",
  "active-pointer-promotion-traversal",
  "lineup-player-team-game-traversal",
  "registry-firewall-census",
] as const;
export type ViewName = (typeof VIEW_NAMES)[number];

export const REASON_CODES = [
  "ready",
  "projection-not-configured",
  "projection-invalid-or-unavailable",
  "graph-query-projection-failed",
  "projection-validation-failed",
] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

/** Firewall booleans present on every payload the API emits. */
export interface AuthorityFirewall {
  readonly read_only: true;
  readonly graph_mutation: false;
  readonly automatic_promotion: false;
  readonly application_config_mutation: false;
  readonly production_policy_authority: false;
}

export interface StatusPayload extends AuthorityFirewall {
  readonly schema_version: "corpus-research-ui-status/v1";
  readonly ready: boolean;
  readonly reason_code: ReasonCode;
  readonly message: string;
  readonly registry_id?: string;
  readonly database?: string;
  readonly generated_at_utc?: string;
  readonly projection_sha256?: string;
  readonly view_row_counts?: Readonly<Record<string, number>>;
}

export interface RegistryRelease {
  readonly uri: string;
  readonly generation: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface SourceProjectionReceipt extends AuthorityFirewall {
  readonly schema_version: "corpus-strategy-registry-projection/v2";
  readonly registry_id: string;
  readonly registry_namespace: "corpus-strategy-registry";
  readonly publication_mode: "create_once";
  readonly manifest_namespace_v2_authorized: true;
  readonly registry_release: RegistryRelease;
  readonly plan_sha256: string;
  readonly registry_node_count: number;
  readonly registry_relationship_count: number;
  readonly winner_imported: boolean;
  readonly winner_count: number;
  readonly kind_counts: Readonly<Record<string, number>>;
  readonly projection_receipt_sha256: string;
}

export interface QueryResultReceipt {
  readonly name: string;
  readonly cypher_sha256: string;
  readonly row_count: number;
  readonly rows_sha256: string;
}

export interface QueryReceipt extends AuthorityFirewall {
  readonly schema_version: "corpus-research-ui-query-receipt/v1";
  readonly publication_mode: "read_only_materialization";
  readonly registry_id: string;
  readonly database: string;
  readonly namespace: "corpus-strategy-registry";
  readonly source_projection_receipt_sha256: string;
  readonly generated_at_utc: string;
  readonly queries: readonly QueryResultReceipt[];
  readonly gcs_remains_authoritative: true;
  readonly world_matrices_stored_in_graph: false;
  readonly query_receipt_sha256: string;
}

export type ViewRow = Readonly<Record<string, unknown>>;

export interface ProjectionPayload extends AuthorityFirewall {
  readonly schema_version: "corpus-research-ui-projection/v1";
  readonly registry_id: string;
  readonly database: string;
  readonly namespace: "corpus-strategy-registry";
  readonly generated_at_utc: string;
  readonly source_projection_receipt: SourceProjectionReceipt;
  readonly query_receipt: QueryReceipt;
  readonly views: Readonly<Record<string, readonly ViewRow[]>>;
  readonly projection_sha256: string;
}

export interface ProjectionResponse {
  readonly status: StatusPayload;
  readonly projection: ProjectionPayload;
}

/** UI availability model — the eight states every page must render. */
export type Availability =
  | { readonly state: "loading" }
  | {
      readonly state: "ready";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly ageSeconds: number;
    }
  | {
      /** Ready payload whose views include at least one empty view. */
      readonly state: "partial";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly emptyViews: readonly ViewName[];
      readonly ageSeconds: number;
    }
  | {
      /** Valid but older than the staleness threshold. */
      readonly state: "stale";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly ageSeconds: number;
    }
  | {
      /** Projection endpoint answered 503 with a status body. */
      readonly state: "degraded";
      readonly status: StatusPayload;
    }
  | { readonly state: "empty"; readonly status: StatusPayload }
  | { readonly state: "unauthorized"; readonly httpStatus: 401 | 403 }
  | {
      readonly state: "schema-mismatch";
      readonly detail: string;
    };

/** Synthetic product-input contract for the eventual Core grade report.
 *
 * Fixture-only in this lane: `uses_realized_outcomes` is pinned false and
 * the evidence tier names it a fixture. The real product later consumes a
 * custodian-supplied terminal accepted identity; this lane never reads a
 * grade work directory or outcome source.
 */
export const GRADE_THRESHOLDS = [
  180, 194, 200, 210, 220, 230, 240, 250,
] as const;
export type GradeThreshold = (typeof GRADE_THRESHOLDS)[number];
export type EntryBudget = 4 | 14 | 80;

export interface GradeReportStrategy {
  readonly strategy_id: string;
  readonly fill_preset: string;
  readonly admission_preset: string;
  readonly retrieval_preset: string;
  readonly entry_budget: EntryBudget;
  readonly book: {
    readonly max: number;
    readonly mean: number;
    readonly median: number;
  };
  readonly threshold_hits: Readonly<Record<`${GradeThreshold}`, number>>;
  readonly conversion: {
    readonly corpus_ceiling_c: number;
    readonly selected_max_s: number;
    readonly gap_c_minus_s: number;
  };
  readonly paired_weekly_delta: {
    readonly baseline_strategy_id: string;
    readonly mean: number;
    readonly median: number;
    readonly wins: number;
    readonly ties: number;
    readonly losses: number;
  };
  readonly season_deltas: Readonly<Record<string, number>>;
  readonly leave_one_out_max_gain_share: number;
  readonly missing_slates: number;
}

export interface GradeReportV1 {
  readonly schema_version: "core-v1-human-readable-grade-report/v1";
  readonly evidence_tier: "synthetic-fixture";
  readonly uses_realized_outcomes: false;
  readonly panel: {
    readonly accepted_slates: number;
    readonly seasons: readonly string[];
    readonly denominator_note: string;
  };
  readonly strategies: readonly GradeReportStrategy[];
  readonly contest_metrics_available: false;
  readonly contest_metrics_note: string;
}
