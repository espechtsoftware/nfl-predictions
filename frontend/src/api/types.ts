/** Strict contracts for the corpus-research read-only API.
 *
 * Mirrors src/nfl_dfs/app/corpus_research.py exactly. The browser renders
 * hashes and firewall flags; it never claims to verify them — cryptographic
 * validation is server-side only.
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

/** UI availability model.
 *
 * Nine states. Transport failure ("unreachable") is distinct from a payload
 * that arrived but failed schema validation ("schema-mismatch"). Staleness
 * and partial view coverage can coexist: the stale state carries the empty
 * view list so stale never hides missing views.
 */
export type Availability =
  | { readonly state: "loading" }
  | {
      readonly state: "ready";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly ageSeconds: number;
    }
  | {
      /** Fresh payload with at least one empty view. */
      readonly state: "partial";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly emptyViews: readonly ViewName[];
      readonly ageSeconds: number;
    }
  | {
      /** Valid but older than the staleness threshold; may also be partial. */
      readonly state: "stale";
      readonly status: StatusPayload;
      readonly projection: ProjectionPayload;
      readonly emptyViews: readonly ViewName[];
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
      /** The transport failed: network error, DNS, refused connection. */
      readonly state: "unreachable";
      readonly detail: string;
    }
  | {
      /** A payload arrived but did not match the contract. */
      readonly state: "schema-mismatch";
      readonly detail: string;
    };

/* ------------------------------------------------------------------ *
 * Core v1 grade report — exact mirror of the governed producer
 * scripts/report_core_v1_grade.py (schema
 * core-v1-human-readable-grade-report/v1). The real report reads one
 * historical outcome, so `uses_realized_outcomes` is `true` INSIDE the
 * payload. Synthetic fixtures wrap the payload in a separate UI evidence
 * wrapper (see fixtures/gradeReport.ts); they never flip governed fields.
 * ------------------------------------------------------------------ */

export const GRADE_THRESHOLDS_DK = [
  180, 194, 200, 210, 220, 230, 240, 250,
] as const;
export type GradeThresholdDk = (typeof GRADE_THRESHOLDS_DK)[number];

export const ENTRY_BUDGETS = [4, 14, 80] as const;
export type EntryBudget = (typeof ENTRY_BUDGETS)[number];

export const BASELINE_STRATEGY_ID = "r194:incumbent" as const;

export const SOURCE_STRATEGY_IDS = [
  "r194:incumbent",
  "r194:remove-salary-floor",
  "r194:remove-qb-stack",
  "r194:remove-bring-back",
  "r194:allow-rb-vs-dst",
  "r194:allow-two-rb",
  "r194:remove-all-five-shared-constraints",
] as const;

export const T230_STRATEGY_IDS = [
  "t230:coverage-ge-230-v1",
  "t230:bounded-tail-ladder-ge-210-250-v1",
  "t230:block-robust-bounded-tail-ge-210-250-v1",
  "t230:individual-ge-230-rank-v1",
  "t230:support-switched-policy-v1",
] as const;

export const ABSOLUTE_STRATEGY_IDS = [
  ...SOURCE_STRATEGY_IDS,
  ...T230_STRATEGY_IDS,
] as const;

export const MICRO_DK_PER_POINT = 1_000_000 as const;
export const EXPECTED_SOURCE_SLATE_COUNT = 54 as const;

/** gs:// object identity as normalized by the batch transport. */
export interface ObjectIdentity {
  readonly uri: string;
  readonly generation: string;
  readonly sha256: string;
  readonly bytes: number;
}

/** Exact rational numerator/denominator pair; decimals are display-only. */
export interface ExactRational {
  readonly numerator: number;
  readonly denominator: number;
  readonly unit: string;
}

export interface RationalDk extends ExactRational {
  readonly unit: "micro_dk";
  readonly dk_points_display: string;
}

export interface MicroWithDisplay {
  readonly micro_dk: number;
  readonly dk_points_display: string;
}

export interface BookThresholdRow {
  readonly threshold_dk: GradeThresholdDk;
  readonly selected_lineup_hit_count: number;
  readonly produced_at_least_one_hit: boolean;
}

export interface BookWeekRow {
  readonly source_ordinal: number;
  readonly season: number;
  readonly week: number;
  readonly slate_id: string;
  readonly strategy_id: string;
  readonly entry_budget: EntryBudget;
  readonly maximum: MicroWithDisplay;
  readonly mean: RationalDk;
  readonly median: RationalDk;
  readonly top_three_mean: RationalDk;
  readonly gap_to_shared_corpus_ceiling: MicroWithDisplay;
  readonly thresholds: readonly BookThresholdRow[];
}

export interface AbsoluteSummaryThresholdRow {
  readonly threshold_dk: GradeThresholdDk;
  readonly selected_lineup_hit_count: number;
  readonly selected_lineup_hit_fraction: ExactRational;
  readonly slates_with_at_least_one_hit: number;
  readonly slate_hit_fraction: ExactRational;
}

export interface AbsoluteStrategyBudgetSummary {
  readonly strategy_id: string;
  readonly entry_budget: EntryBudget;
  readonly slate_count: number;
  readonly selected_lineup_membership_count: number;
  readonly overall_best_score: MicroWithDisplay;
  readonly weekly_maximum_mean: RationalDk;
  readonly weekly_maximum_median: RationalDk;
  readonly selected_lineup_score_mean: RationalDk;
  readonly weekly_union_ceiling_gap_mean: RationalDk;
  readonly thresholds: readonly AbsoluteSummaryThresholdRow[];
}

export interface WeeklyThresholdDelta {
  readonly threshold_dk: GradeThresholdDk;
  readonly at_or_above_count_delta: number;
  readonly at_least_one_hit_conversion_delta: number;
}

export interface WeeklyPrimaryContrast {
  readonly source_ordinal: number;
  readonly season: number;
  readonly week: number;
  readonly slate_id: string;
  readonly challenger_strategy_id: string;
  readonly comparator_strategy_id: typeof BASELINE_STRATEGY_ID;
  readonly entry_budget: EntryBudget;
  readonly challenger_maximum: MicroWithDisplay;
  readonly comparator_maximum: MicroWithDisplay;
  readonly weekly_maximum_delta: MicroWithDisplay;
  readonly weekly_mean_delta: RationalDk;
  readonly threshold_deltas: readonly WeeklyThresholdDelta[];
}

export interface ThresholdDeltaSum {
  readonly threshold_dk: GradeThresholdDk;
  readonly count_delta_sum: number;
  readonly hit_conversion_delta_sum: number;
}

export interface DeltaSummaryProjection {
  readonly slate_count: number;
  readonly weekly_maximum_delta_mean: RationalDk;
  readonly weekly_maximum_delta_sum: MicroWithDisplay;
  readonly challenger_better_slate_count: number;
  readonly exact_tie_slate_count: number;
  readonly challenger_worse_slate_count: number;
  readonly threshold_delta_sums: readonly ThresholdDeltaSum[];
}

export interface PrimaryPairedSummary {
  readonly contrast_id: string;
  readonly challenger_strategy_id: string;
  readonly comparator_strategy_id: typeof BASELINE_STRATEGY_ID;
  readonly entry_budget: EntryBudget;
  readonly overall: DeltaSummaryProjection;
  readonly season_summaries: readonly ({
    readonly season: number;
  } & DeltaSummaryProjection)[];
  readonly leave_one_slate_sensitivity: readonly ({
    readonly omitted_source_ordinal: number;
  } & DeltaSummaryProjection)[];
  readonly leave_one_season_sensitivity: readonly ({
    readonly omitted_season: number;
  } & DeltaSummaryProjection)[];
  readonly multiplicity_label: string;
  readonly evidence_class: string;
  readonly report_regardless_of_sign: boolean;
}

export interface UnionCeilingThresholdRow {
  readonly threshold_dk: GradeThresholdDk;
  readonly shared_union_lineup_hit_count: number;
}

export interface SharedUnionCeilingRow {
  readonly source_ordinal: number;
  readonly season: number;
  readonly week: number;
  readonly slate_id: string;
  readonly shared_union_roster_count: number;
  readonly shared_union_maximum: MicroWithDisplay;
  readonly thresholds: readonly UnionCeilingThresholdRow[];
}

export interface GradeReportCoverage {
  readonly source_slate_count: number;
  readonly strategy_count: number;
  readonly entry_budget_count: number;
  readonly book_cell_count: number;
  readonly contrast_definition_count: number;
  readonly weekly_contrast_cell_count: number;
  readonly contrast_summary_count: number;
  readonly unique_union_roster_membership_count: number;
  readonly union_roster_sum_operation_count: number;
  readonly actual_player_outcome_row_count: number;
  readonly every_unique_union_roster_scored_exactly_once_per_slate: boolean;
}

/** Fixed contest-metrics block — the producer refuses any other content. */
export interface GradeReportContestMetrics {
  readonly availability: "unavailable";
  readonly reason: "full_field_standings_and_payout_ladder_not_supplied";
  readonly full_field_standings_identity: null;
  readonly payout_ladder_identity: null;
  readonly rank: null;
  readonly roi_micro_usd: null;
}

export const GRADE_REPORT_LIMITATIONS = [
  "contest_rank_unavailable_without_full_field_standings",
  "contest_roi_unavailable_without_payout_ladder_and_tie_settlement",
  "final_fit_books_only_cross_fit_books_excluded",
  "descriptive_historical_report_not_production_or_retune_authority",
  "threshold_187_not_prespecified_in_core_v1",
] as const;

export interface GradeReportV1 {
  readonly schema_version: "core-v1-human-readable-grade-report/v1";
  readonly status: "CORE_V1_HISTORICAL_SCORE_REPORT_READY";
  readonly grade_run_id: string;
  readonly grade_completion_identity: ObjectIdentity;
  readonly grade_root_identity: ObjectIdentity;
  readonly realized_grade_sha256: string;
  readonly catalog_sha256: string;
  readonly outcome_snapshot_sha256: string;
  readonly score_unit: "micro_dk";
  readonly micro_dk_per_point: typeof MICRO_DK_PER_POINT;
  readonly baseline_strategy_id: typeof BASELINE_STRATEGY_ID;
  readonly absolute_strategy_ids: readonly string[];
  readonly source_fill_strategy_ids: readonly string[];
  readonly t230_strategy_ids: readonly string[];
  readonly entry_budgets: readonly EntryBudget[];
  readonly thresholds_dk: readonly GradeThresholdDk[];
  readonly coverage: GradeReportCoverage;
  readonly absolute_strategy_budget_summaries: readonly AbsoluteStrategyBudgetSummary[];
  readonly weekly_strategy_budget_rows: readonly BookWeekRow[];
  readonly primary_paired_summaries: readonly PrimaryPairedSummary[];
  readonly weekly_primary_contrasts: readonly WeeklyPrimaryContrast[];
  readonly shared_union_ceiling_rows: readonly SharedUnionCeilingRow[];
  readonly contest_metrics: GradeReportContestMetrics;
  readonly limitations: readonly string[];
  readonly full_predecessor_root_and_shard_chain_exactly_reopened: true;
  readonly known_name_then_generation_pinned_reads_only: true;
  readonly object_listing_used: false;
  readonly one_historical_outcome_read_reused: true;
  /** The governed report reads one historical outcome — this is TRUE. */
  readonly uses_realized_outcomes: true;
  readonly historical_retune_licensed: false;
  readonly historical_retry_licensed: false;
  readonly graph_mutation_licensed: false;
  readonly production_change_licensed: false;
  readonly decision_authority: false;
}

/** UI-side wrapper for synthetic fixtures.
 *
 * The wrapper — not the governed payload — carries the fixture evidence
 * tier. The payload keeps `uses_realized_outcomes: true` because the REAL
 * report it mirrors reads outcomes; what is synthetic here is the fixture's
 * construction, which read nothing.
 */
export interface SyntheticGradeReportFixture {
  readonly fixture_evidence: {
    readonly ui_evidence_tier: "synthetic-fixture";
    readonly fixture_construction_read_outcomes: false;
    readonly note: string;
  };
  readonly report: GradeReportV1;
}
