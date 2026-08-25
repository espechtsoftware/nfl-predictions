/** Core v1 grade-report contract preview (synthetic fixture).
 *
 * Renders the governed core-v1-human-readable-grade-report/v1 shape from a
 * deterministic fixture. Evidence labeling is two-layer and must not be
 * collapsed: the governed payload truthfully carries
 * `uses_realized_outcomes: true` (the real report reads one historical
 * outcome), while the fixture WRAPPER carries the synthetic-fixture tier
 * and the fact that fixture construction read nothing.
 */

import { GRADE_THRESHOLDS_DK } from "../api/types";
import { syntheticGradeReportFixture } from "../fixtures/gradeReport";
import { EvidenceBadge } from "../app/states";

function short(value: string): string {
  return `${value.slice(0, 12)}…`;
}

export function GradeReportPreview() {
  const { fixture_evidence, report } = syntheticGradeReportFixture;
  const summaryThreshold = (threshold: number) =>
    `slates ≥${threshold}`;
  return (
    <section className="grade-report" data-testid="grade-report-preview">
      <h2>
        Core v1 grade-report contract preview
        <EvidenceBadge tier={fixture_evidence.ui_evidence_tier} />
      </h2>
      <p className="view-meta" data-testid="grade-report-evidence">
        Governed payload: <code>{report.schema_version}</code> ·{" "}
        <strong>
          uses realized outcomes: {String(report.uses_realized_outcomes)}
        </strong>{" "}
        (the real report reads one historical outcome). Fixture wrapper:
        fixture construction read outcomes:{" "}
        <strong>
          {String(fixture_evidence.fixture_construction_read_outcomes)}
        </strong>
        . {fixture_evidence.note}
      </p>
      <dl className="identity-strip" data-testid="grade-report-identity">
        <div>
          <dt>grade run</dt>
          <dd>{report.grade_run_id}</dd>
        </div>
        <div>
          <dt>completion identity</dt>
          <dd>
            generation {report.grade_completion_identity.generation} · sha256{" "}
            <code>{short(report.grade_completion_identity.sha256)}</code> ·{" "}
            {report.grade_completion_identity.bytes.toLocaleString()} bytes
          </dd>
        </div>
        <div>
          <dt>root identity</dt>
          <dd>
            generation {report.grade_root_identity.generation} · sha256{" "}
            <code>{short(report.grade_root_identity.sha256)}</code>
          </dd>
        </div>
        <div>
          <dt>chain hashes (server-verified)</dt>
          <dd>
            grade <code>{short(report.realized_grade_sha256)}</code> · catalog{" "}
            <code>{short(report.catalog_sha256)}</code> · outcomes{" "}
            <code>{short(report.outcome_snapshot_sha256)}</code>
          </dd>
        </div>
        <div>
          <dt>coverage</dt>
          <dd data-testid="grade-report-coverage">
            {report.coverage.source_slate_count} slates ·{" "}
            {report.coverage.strategy_count} strategies ·{" "}
            {report.coverage.entry_budget_count} budgets ·{" "}
            {report.coverage.book_cell_count.toLocaleString()} book cells ·{" "}
            {report.coverage.contrast_summary_count} paired summaries
          </dd>
        </div>
      </dl>

      <h3>
        Absolute strategy/budget summaries (
        {report.absolute_strategy_budget_summaries.length})
      </h3>
      <div className="table-scroll">
        <table data-testid="grade-report-absolute-table">
          <caption className="visually-hidden">
            absolute strategy budget summaries
          </caption>
          <thead>
            <tr>
              <th scope="col">strategy</th>
              <th scope="col">budget</th>
              <th scope="col">best (DK)</th>
              <th scope="col">weekly max mean</th>
              <th scope="col">C−S gap mean</th>
              {GRADE_THRESHOLDS_DK.map((threshold) => (
                <th scope="col" key={threshold}>
                  {summaryThreshold(threshold)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.absolute_strategy_budget_summaries.map((summary) => (
              <tr key={`${summary.strategy_id}:${summary.entry_budget}`}>
                <td>{summary.strategy_id}</td>
                <td>{summary.entry_budget}</td>
                <td>{summary.overall_best_score.dk_points_display}</td>
                <td>{summary.weekly_maximum_mean.dk_points_display}</td>
                <td>
                  {summary.weekly_union_ceiling_gap_mean.dk_points_display}
                </td>
                {summary.thresholds.map((row) => (
                  <td key={row.threshold_dk}>
                    {row.slates_with_at_least_one_hit}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>
        Primary paired summaries vs {report.baseline_strategy_id} (
        {report.primary_paired_summaries.length})
      </h3>
      <div className="table-scroll">
        <table data-testid="grade-report-paired-table">
          <caption className="visually-hidden">primary paired summaries</caption>
          <thead>
            <tr>
              <th scope="col">challenger</th>
              <th scope="col">budget</th>
              <th scope="col">Δ weekly max mean</th>
              <th scope="col">W/T/L</th>
              <th scope="col">Δ≥230 hits</th>
              <th scope="col">Δ≥250 hits</th>
              <th scope="col">evidence class</th>
            </tr>
          </thead>
          <tbody>
            {report.primary_paired_summaries.map((summary) => {
              const d230 = summary.overall.threshold_delta_sums.find(
                (row) => row.threshold_dk === 230,
              );
              const d250 = summary.overall.threshold_delta_sums.find(
                (row) => row.threshold_dk === 250,
              );
              return (
                <tr key={summary.contrast_id}>
                  <td>{summary.challenger_strategy_id}</td>
                  <td>{summary.entry_budget}</td>
                  <td>
                    {summary.overall.weekly_maximum_delta_mean.dk_points_display}
                  </td>
                  <td>
                    {summary.overall.challenger_better_slate_count}/
                    {summary.overall.exact_tie_slate_count}/
                    {summary.overall.challenger_worse_slate_count}
                  </td>
                  <td>{d230?.count_delta_sum ?? "—"}</td>
                  <td>{d250?.count_delta_sum ?? "—"}</td>
                  <td>{summary.evidence_class}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="view-meta" data-testid="grade-report-detail-note">
        The payload additionally carries{" "}
        {report.weekly_strategy_budget_rows.length.toLocaleString()} weekly
        book rows, {report.weekly_primary_contrasts.length.toLocaleString()}{" "}
        weekly paired contrasts, and{" "}
        {report.shared_union_ceiling_rows.length} shared-union ceiling rows;
        weekly drill-down views arrive with the visualization phase.
      </p>

      <p className="contest-unavailable" data-testid="contest-unavailable">
        Contest metrics: <strong>{report.contest_metrics.availability}</strong>{" "}
        — {report.contest_metrics.reason}. Rank and ROI render as unavailable,
        never inferred and never shown as zero.
      </p>
      <ul className="limitations" data-testid="grade-report-limitations">
        {report.limitations.map((limitation) => (
          <li key={limitation}>{limitation}</li>
        ))}
      </ul>
    </section>
  );
}
