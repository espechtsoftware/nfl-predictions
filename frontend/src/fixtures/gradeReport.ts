/** Synthetic, internally consistent core-v1 grade-report fixture.
 *
 * Mirrors the governed producer scripts/report_core_v1_grade.py exactly:
 * the real 12-strategy catalog (7 r194 fill arms + 5 t230 retrieval
 * strategies), budgets 4/14/80 (36 absolute summaries), thresholds
 * 180–250, the 5×3 primary paired family against r194:incumbent over 54
 * slates, exact integer micro-DK and reduced-rational values with
 * ROUND_HALF_UP three-decimal display strings, the fixed contest-metrics
 * and limitations blocks, and the governed authority fields — including
 * `uses_realized_outcomes: true`, because the real report reads one
 * historical outcome. Only the WRAPPER carries the synthetic-fixture tier:
 * every number below is deterministic arithmetic; fixture construction
 * read no outcome, no artifact, and no cloud resource.
 */

import {
  ABSOLUTE_STRATEGY_IDS,
  AbsoluteStrategyBudgetSummary,
  BASELINE_STRATEGY_ID,
  BookWeekRow,
  DeltaSummaryProjection,
  ENTRY_BUDGETS,
  EXPECTED_SOURCE_SLATE_COUNT,
  EntryBudget,
  ExactRational,
  GRADE_REPORT_LIMITATIONS,
  GRADE_THRESHOLDS_DK,
  GradeReportV1,
  MICRO_DK_PER_POINT,
  MicroWithDisplay,
  PrimaryPairedSummary,
  RationalDk,
  SOURCE_STRATEGY_IDS,
  SharedUnionCeilingRow,
  SyntheticGradeReportFixture,
  T230_STRATEGY_IDS,
  WeeklyPrimaryContrast,
} from "../api/types";

const SEASONS = [2019, 2021, 2022, 2023, 2024, 2025] as const;
const SLATES_PER_SEASON = EXPECTED_SOURCE_SLATE_COUNT / SEASONS.length;

function gcd(a: number, b: number): number {
  let x = Math.abs(a);
  let y = b;
  while (y !== 0) {
    const next = x % y;
    x = y;
    y = next;
  }
  return x === 0 ? 1 : x;
}

function rational(
  numerator: number,
  denominator: number,
  unit: string,
): ExactRational {
  const common = gcd(numerator, denominator);
  return {
    numerator: numerator / common,
    denominator: denominator / common,
    unit,
  };
}

/** Integer-exact micro-DK → "x.yyy" DK display with ROUND_HALF_UP ties. */
function dkDisplay(numerator: number, denominator: number): string {
  const negative = numerator < 0;
  const magnitude = Math.abs(numerator) * 1000;
  const scale = denominator * MICRO_DK_PER_POINT;
  const milli = Math.floor((2 * magnitude + scale) / (2 * scale));
  const whole = Math.floor(milli / 1000);
  const frac = String(milli % 1000).padStart(3, "0");
  return `${negative && milli !== 0 ? "-" : ""}${whole}.${frac}`;
}

function rationalDk(numerator: number, denominator: number): RationalDk {
  const reduced = rational(numerator, denominator, "micro_dk");
  return {
    ...(reduced as RationalDk),
    unit: "micro_dk",
    dk_points_display: dkDisplay(numerator, denominator),
  };
}

function microDisplay(value: number): MicroWithDisplay {
  return { micro_dk: value, dk_points_display: dkDisplay(value, 1) };
}

interface BookCell {
  readonly sourceOrdinal: number;
  readonly season: number;
  readonly week: number;
  readonly slateId: string;
  readonly strategyId: string;
  readonly budget: EntryBudget;
  readonly baseDk: number;
  readonly maxMicro: number;
  readonly sumMicro: number;
  readonly hits: readonly number[];
}

function season(sourceOrdinal: number): number {
  return SEASONS[Math.floor(sourceOrdinal / SLATES_PER_SEASON)]!;
}

function week(sourceOrdinal: number): number {
  return (sourceOrdinal % SLATES_PER_SEASON) + 1;
}

function slateId(sourceOrdinal: number): string {
  return `slate:${season(sourceOrdinal)}-w${week(sourceOrdinal)}`;
}

/** Arithmetic-sequence book: scores baseDk, baseDk+1, … (in DK points). */
function bookCell(
  sourceOrdinal: number,
  strategyIndex: number,
  budgetIndex: number,
): BookCell {
  const budget = ENTRY_BUDGETS[budgetIndex]!;
  const baseDk =
    140 + strategyIndex * 3 + (sourceOrdinal % 7) * 2 + budgetIndex * 5;
  const base = baseDk * MICRO_DK_PER_POINT;
  const maxMicro = base + (budget - 1) * MICRO_DK_PER_POINT;
  const sumMicro =
    budget * base + MICRO_DK_PER_POINT * ((budget * (budget - 1)) / 2);
  const hits = GRADE_THRESHOLDS_DK.map((threshold) =>
    Math.min(budget, Math.max(0, budget - Math.max(0, threshold - baseDk))),
  );
  return {
    sourceOrdinal,
    season: season(sourceOrdinal),
    week: week(sourceOrdinal),
    slateId: slateId(sourceOrdinal),
    strategyId: ABSOLUTE_STRATEGY_IDS[strategyIndex]!,
    budget,
    baseDk,
    maxMicro,
    sumMicro,
    hits,
  };
}

function bookWeekRow(cell: BookCell, unionMaxMicro: number): BookWeekRow {
  const budget = cell.budget;
  const meanNumerator = cell.sumMicro;
  const topThree = 3 * (cell.maxMicro - MICRO_DK_PER_POINT);
  return {
    source_ordinal: cell.sourceOrdinal,
    season: cell.season,
    week: cell.week,
    slate_id: cell.slateId,
    strategy_id: cell.strategyId,
    entry_budget: budget,
    maximum: microDisplay(cell.maxMicro),
    mean: rationalDk(meanNumerator, budget),
    median: rationalDk(meanNumerator, budget),
    top_three_mean: rationalDk(topThree, 3),
    gap_to_shared_corpus_ceiling: microDisplay(unionMaxMicro - cell.maxMicro),
    thresholds: GRADE_THRESHOLDS_DK.map((threshold, index) => ({
      threshold_dk: threshold,
      selected_lineup_hit_count: cell.hits[index]!,
      produced_at_least_one_hit: cell.hits[index]! > 0,
    })),
  };
}

interface WeeklyDeltaInput {
  readonly sourceOrdinal: number;
  readonly season: number;
  readonly deltaMicro: number;
  readonly countDeltas: readonly number[];
  readonly conversionDeltas: readonly number[];
}

function summarize(rows: readonly WeeklyDeltaInput[]): DeltaSummaryProjection {
  const deltaSum = rows.reduce((sum, row) => sum + row.deltaMicro, 0);
  const countSums = GRADE_THRESHOLDS_DK.map((_, index) =>
    rows.reduce((sum, row) => sum + row.countDeltas[index]!, 0),
  );
  const conversionSums = GRADE_THRESHOLDS_DK.map((_, index) =>
    rows.reduce((sum, row) => sum + row.conversionDeltas[index]!, 0),
  );
  return {
    slate_count: rows.length,
    weekly_maximum_delta_mean: rationalDk(deltaSum, rows.length),
    weekly_maximum_delta_sum: microDisplay(deltaSum),
    challenger_better_slate_count: rows.filter((row) => row.deltaMicro > 0)
      .length,
    exact_tie_slate_count: rows.filter((row) => row.deltaMicro === 0).length,
    challenger_worse_slate_count: rows.filter((row) => row.deltaMicro < 0)
      .length,
    threshold_delta_sums: GRADE_THRESHOLDS_DK.map((threshold, index) => ({
      threshold_dk: threshold,
      count_delta_sum: countSums[index]!,
      hit_conversion_delta_sum: conversionSums[index]!,
    })),
  };
}

function buildReport(): GradeReportV1 {
  const cells = new Map<string, BookCell>();
  const unionMaxBySlate: number[] = [];
  const unionCountBySlate: number[] = [];
  for (
    let sourceOrdinal = 0;
    sourceOrdinal < EXPECTED_SOURCE_SLATE_COUNT;
    sourceOrdinal += 1
  ) {
    let slateMax = 0;
    for (let s = 0; s < ABSOLUTE_STRATEGY_IDS.length; s += 1) {
      for (let b = 0; b < ENTRY_BUDGETS.length; b += 1) {
        const cell = bookCell(sourceOrdinal, s, b);
        cells.set(
          `${sourceOrdinal}:${cell.strategyId}:${cell.budget}`,
          cell,
        );
        slateMax = Math.max(slateMax, cell.maxMicro);
      }
    }
    unionMaxBySlate.push(slateMax + 5 * MICRO_DK_PER_POINT);
    unionCountBySlate.push(400 + sourceOrdinal);
  }

  const weeklyRows: BookWeekRow[] = [];
  for (
    let sourceOrdinal = 0;
    sourceOrdinal < EXPECTED_SOURCE_SLATE_COUNT;
    sourceOrdinal += 1
  ) {
    for (const strategyId of ABSOLUTE_STRATEGY_IDS) {
      for (const budget of ENTRY_BUDGETS) {
        const cell = cells.get(`${sourceOrdinal}:${strategyId}:${budget}`)!;
        weeklyRows.push(bookWeekRow(cell, unionMaxBySlate[sourceOrdinal]!));
      }
    }
  }

  const absoluteSummaries: AbsoluteStrategyBudgetSummary[] = [];
  for (const budget of ENTRY_BUDGETS) {
    for (const strategyId of ABSOLUTE_STRATEGY_IDS) {
      const retained = Array.from(
        { length: EXPECTED_SOURCE_SLATE_COUNT },
        (_, sourceOrdinal) =>
          cells.get(`${sourceOrdinal}:${strategyId}:${budget}`)!,
      );
      const maxima = retained.map((cell) => cell.maxMicro);
      const gaps = retained.map(
        (cell) => unionMaxBySlate[cell.sourceOrdinal]! - cell.maxMicro,
      );
      const allScoreSum = retained.reduce((sum, cell) => sum + cell.sumMicro, 0);
      const membership = retained.length * budget;
      const sortedMaxima = [...maxima].sort((a, b) => a - b);
      const mid = sortedMaxima.length / 2;
      absoluteSummaries.push({
        strategy_id: strategyId,
        entry_budget: budget,
        slate_count: retained.length,
        selected_lineup_membership_count: membership,
        overall_best_score: microDisplay(Math.max(...maxima)),
        weekly_maximum_mean: rationalDk(
          maxima.reduce((a, b) => a + b, 0),
          maxima.length,
        ),
        weekly_maximum_median: rationalDk(
          sortedMaxima[mid - 1]! + sortedMaxima[mid]!,
          2,
        ),
        selected_lineup_score_mean: rationalDk(allScoreSum, membership),
        weekly_union_ceiling_gap_mean: rationalDk(
          gaps.reduce((a, b) => a + b, 0),
          gaps.length,
        ),
        thresholds: GRADE_THRESHOLDS_DK.map((threshold, index) => {
          const hitCount = retained.reduce(
            (sum, cell) => sum + cell.hits[index]!,
            0,
          );
          const slateHits = retained.filter(
            (cell) => cell.hits[index]! > 0,
          ).length;
          return {
            threshold_dk: threshold,
            selected_lineup_hit_count: hitCount,
            selected_lineup_hit_fraction: rational(
              hitCount,
              membership,
              "lineups",
            ),
            slates_with_at_least_one_hit: slateHits,
            slate_hit_fraction: rational(
              slateHits,
              retained.length,
              "slates",
            ),
          };
        }),
      });
    }
  }

  const weeklyContrasts: WeeklyPrimaryContrast[] = [];
  const deltaInputs = new Map<string, WeeklyDeltaInput[]>();
  for (
    let sourceOrdinal = 0;
    sourceOrdinal < EXPECTED_SOURCE_SLATE_COUNT;
    sourceOrdinal += 1
  ) {
    for (const challenger of T230_STRATEGY_IDS) {
      for (const budget of ENTRY_BUDGETS) {
        const challengerCell = cells.get(
          `${sourceOrdinal}:${challenger}:${budget}`,
        )!;
        const baselineCell = cells.get(
          `${sourceOrdinal}:${BASELINE_STRATEGY_ID}:${budget}`,
        )!;
        const delta = challengerCell.maxMicro - baselineCell.maxMicro;
        const countDeltas = GRADE_THRESHOLDS_DK.map(
          (_, index) => challengerCell.hits[index]! - baselineCell.hits[index]!,
        );
        const conversionDeltas = GRADE_THRESHOLDS_DK.map(
          (_, index) =>
            Number(challengerCell.hits[index]! > 0) -
            Number(baselineCell.hits[index]! > 0),
        );
        weeklyContrasts.push({
          source_ordinal: sourceOrdinal,
          season: challengerCell.season,
          week: challengerCell.week,
          slate_id: challengerCell.slateId,
          challenger_strategy_id: challenger,
          comparator_strategy_id: BASELINE_STRATEGY_ID,
          entry_budget: budget,
          challenger_maximum: microDisplay(challengerCell.maxMicro),
          comparator_maximum: microDisplay(baselineCell.maxMicro),
          weekly_maximum_delta: microDisplay(delta),
          weekly_mean_delta: rationalDk(
            challengerCell.sumMicro - baselineCell.sumMicro,
            budget,
          ),
          threshold_deltas: GRADE_THRESHOLDS_DK.map((threshold, index) => ({
            threshold_dk: threshold,
            at_or_above_count_delta: countDeltas[index]!,
            at_least_one_hit_conversion_delta: conversionDeltas[index]!,
          })),
        });
        const key = `${challenger}:${budget}`;
        const list = deltaInputs.get(key) ?? [];
        list.push({
          sourceOrdinal,
          season: challengerCell.season,
          deltaMicro: delta,
          countDeltas,
          conversionDeltas,
        });
        deltaInputs.set(key, list);
      }
    }
  }
  weeklyContrasts.sort(
    (a, b) =>
      a.source_ordinal - b.source_ordinal ||
      a.challenger_strategy_id.localeCompare(b.challenger_strategy_id) ||
      a.entry_budget - b.entry_budget,
  );

  const pairedSummaries: PrimaryPairedSummary[] = [];
  for (const budget of ENTRY_BUDGETS) {
    for (const challenger of [...T230_STRATEGY_IDS].sort()) {
      const rows = deltaInputs.get(`${challenger}:${budget}`)!;
      pairedSummaries.push({
        contrast_id: `contrast:${challenger}:${budget}`,
        challenger_strategy_id: challenger,
        comparator_strategy_id: BASELINE_STRATEGY_ID,
        entry_budget: budget,
        overall: summarize(rows),
        season_summaries: SEASONS.map((value) => ({
          season: value,
          ...summarize(rows.filter((row) => row.season === value)),
        })),
        leave_one_slate_sensitivity: Array.from(
          { length: EXPECTED_SOURCE_SLATE_COUNT },
          (_, omitted) => ({
            omitted_source_ordinal: omitted,
            ...summarize(
              rows.filter((row) => row.sourceOrdinal !== omitted),
            ),
          }),
        ),
        leave_one_season_sensitivity: SEASONS.map((value) => ({
          omitted_season: value,
          ...summarize(rows.filter((row) => row.season !== value)),
        })),
        multiplicity_label: "primary-headline-family",
        evidence_class: "core-v1-prespecified",
        report_regardless_of_sign: true,
      });
    }
  }

  const unionRows: SharedUnionCeilingRow[] = Array.from(
    { length: EXPECTED_SOURCE_SLATE_COUNT },
    (_, sourceOrdinal) => ({
      source_ordinal: sourceOrdinal,
      season: season(sourceOrdinal),
      week: week(sourceOrdinal),
      slate_id: slateId(sourceOrdinal),
      shared_union_roster_count: unionCountBySlate[sourceOrdinal]!,
      shared_union_maximum: microDisplay(unionMaxBySlate[sourceOrdinal]!),
      thresholds: GRADE_THRESHOLDS_DK.map((threshold) => ({
        threshold_dk: threshold,
        shared_union_lineup_hit_count: Math.max(
          0,
          unionCountBySlate[sourceOrdinal]! - (threshold - 140) * 4,
        ),
      })),
    }),
  );

  const unionMembership = unionCountBySlate.reduce((a, b) => a + b, 0);
  const runId = "core-v1-grade-fixture-0001";
  const prefix = `gs://fixture-core-v1/grades/${runId}/`;
  return {
    schema_version: "core-v1-human-readable-grade-report/v1",
    status: "CORE_V1_HISTORICAL_SCORE_REPORT_READY",
    grade_run_id: runId,
    grade_completion_identity: {
      uri: `${prefix}grade-completion.json`,
      generation: "1788000000000101",
      sha256: "1a".repeat(32),
      bytes: 18_431,
    },
    grade_root_identity: {
      uri: `${prefix}grade-root.json`,
      generation: "1788000000000102",
      sha256: "2b".repeat(32),
      bytes: 96_412,
    },
    realized_grade_sha256: "3c".repeat(32),
    catalog_sha256: "4d".repeat(32),
    outcome_snapshot_sha256: "5e".repeat(32),
    score_unit: "micro_dk",
    micro_dk_per_point: MICRO_DK_PER_POINT,
    baseline_strategy_id: BASELINE_STRATEGY_ID,
    absolute_strategy_ids: [...ABSOLUTE_STRATEGY_IDS],
    source_fill_strategy_ids: [...SOURCE_STRATEGY_IDS],
    t230_strategy_ids: [...T230_STRATEGY_IDS],
    entry_budgets: [...ENTRY_BUDGETS],
    thresholds_dk: [...GRADE_THRESHOLDS_DK],
    coverage: {
      source_slate_count: EXPECTED_SOURCE_SLATE_COUNT,
      strategy_count: ABSOLUTE_STRATEGY_IDS.length,
      entry_budget_count: ENTRY_BUDGETS.length,
      book_cell_count: weeklyRows.length,
      contrast_definition_count: pairedSummaries.length,
      weekly_contrast_cell_count: weeklyContrasts.length,
      contrast_summary_count: pairedSummaries.length,
      unique_union_roster_membership_count: unionMembership,
      union_roster_sum_operation_count: unionMembership,
      actual_player_outcome_row_count: 5_000,
      every_unique_union_roster_scored_exactly_once_per_slate: true,
    },
    absolute_strategy_budget_summaries: absoluteSummaries,
    weekly_strategy_budget_rows: weeklyRows,
    primary_paired_summaries: pairedSummaries,
    weekly_primary_contrasts: weeklyContrasts,
    shared_union_ceiling_rows: unionRows,
    contest_metrics: {
      availability: "unavailable",
      reason: "full_field_standings_and_payout_ladder_not_supplied",
      full_field_standings_identity: null,
      payout_ladder_identity: null,
      rank: null,
      roi_micro_usd: null,
    },
    limitations: [...GRADE_REPORT_LIMITATIONS],
    full_predecessor_root_and_shard_chain_exactly_reopened: true,
    known_name_then_generation_pinned_reads_only: true,
    object_listing_used: false,
    one_historical_outcome_read_reused: true,
    uses_realized_outcomes: true,
    historical_retune_licensed: false,
    historical_retry_licensed: false,
    graph_mutation_licensed: false,
    production_change_licensed: false,
    decision_authority: false,
  };
}

export const syntheticGradeReportFixture: SyntheticGradeReportFixture = {
  fixture_evidence: {
    ui_evidence_tier: "synthetic-fixture",
    fixture_construction_read_outcomes: false,
    note:
      "Deterministic arithmetic fixture mirroring the governed report " +
      "contract; fixture construction did not read outcomes, artifacts, " +
      "or cloud state. The governed payload's own authority fields are " +
      "preserved unchanged, including uses_realized_outcomes: true.",
  },
  report: buildReport(),
};
