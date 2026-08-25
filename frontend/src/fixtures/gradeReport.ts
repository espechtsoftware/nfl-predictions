/** Synthetic core-v1-human-readable-grade-report/v1 fixture.
 *
 * Twelve strategies (four fill families × entry budgets 4/14/80) with
 * deterministic arithmetic values. `uses_realized_outcomes` is pinned false:
 * this lane never reads outcomes; the real product later consumes only a
 * custodian-supplied terminal accepted report identity.
 */

import {
  EntryBudget,
  GRADE_THRESHOLDS,
  GradeReportStrategy,
  GradeReportV1,
} from "../api/types";

const SEASONS = ["2019", "2021", "2022", "2023", "2024", "2025"] as const;
const FILLS = ["f0-incumbent", "f1-lev", "f2-boom", "f3-dark"] as const;
const BUDGETS: readonly EntryBudget[] = [4, 14, 80];

function strategy(
  fillIndex: number,
  budgetIndex: number,
): GradeReportStrategy {
  const fill = FILLS[fillIndex];
  const budget = BUDGETS[budgetIndex];
  const base = 150 + fillIndex * 4 + budgetIndex * 9;
  const ceiling = base + 32;
  const selectedMax = base + 24 + fillIndex;
  const hits = Object.fromEntries(
    GRADE_THRESHOLDS.map((threshold, index) => [
      `${threshold}`,
      Math.max(0, 54 - index * 7 - fillIndex * 2 - (2 - budgetIndex) * 4),
    ]),
  ) as GradeReportStrategy["threshold_hits"];
  const wins = 20 + fillIndex - budgetIndex;
  const losses = 18 - fillIndex + budgetIndex;
  return {
    strategy_id: `strategy:${fill}+exact-${budget}`,
    fill_preset: `fillpreset:${fill}`,
    admission_preset: "admissionpreset:full-union",
    retrieval_preset: `retrievalpreset:exact-${budget}-line194`,
    entry_budget: budget,
    book: {
      max: selectedMax,
      mean: base - 12 + budgetIndex,
      median: base - 14 + budgetIndex,
    },
    threshold_hits: hits,
    conversion: {
      corpus_ceiling_c: ceiling,
      selected_max_s: selectedMax,
      gap_c_minus_s: ceiling - selectedMax,
    },
    paired_weekly_delta: {
      baseline_strategy_id: `strategy:f0-incumbent+exact-${budget}`,
      mean: fillIndex === 0 ? 0 : 0.4 * fillIndex - 0.2 * budgetIndex,
      median: fillIndex === 0 ? 0 : 0.25 * fillIndex,
      wins,
      ties: 54 - wins - losses,
      losses,
    },
    season_deltas: Object.fromEntries(
      SEASONS.map((season, index) => [
        season,
        fillIndex === 0 ? 0 : (index % 3) - 1 + 0.1 * fillIndex,
      ]),
    ),
    leave_one_out_max_gain_share: 0.18 + 0.05 * fillIndex,
    missing_slates: 0,
  };
}

export const gradeReportFixture: GradeReportV1 = {
  schema_version: "core-v1-human-readable-grade-report/v1",
  evidence_tier: "synthetic-fixture",
  uses_realized_outcomes: false,
  panel: {
    accepted_slates: 54,
    seasons: [...SEASONS],
    denominator_note:
      "54-slate accepted v12 panel; every metric denominates over accepted slates only",
  },
  strategies: FILLS.flatMap((_, fillIndex) =>
    BUDGETS.map((_, budgetIndex) => strategy(fillIndex, budgetIndex)),
  ),
  contest_metrics_available: false,
  contest_metrics_note:
    "contest rank, duplication, payout, and ROI are unavailable until complete field/payout evidence exists — rendered as unavailable, never inferred",
};
