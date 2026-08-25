/** Synthetic grade-report contract preview.
 *
 * Demonstrates the core-v1-human-readable-grade-report/v1 product shape with
 * a clearly badged synthetic fixture. Contest metrics render as explicitly
 * unavailable — never inferred, never shown as zero.
 */

import { GRADE_THRESHOLDS } from "../api/types";
import { gradeReportFixture } from "../fixtures/gradeReport";
import { EvidenceBadge } from "../app/states";

export function GradeReportPreview() {
  const report = gradeReportFixture;
  return (
    <section className="grade-report" data-testid="grade-report-preview">
      <h2>
        Grade report contract preview <EvidenceBadge tier={report.evidence_tier} />
      </h2>
      <p className="view-meta">
        {report.panel.accepted_slates} accepted slates · seasons{" "}
        {report.panel.seasons.join(", ")} · uses realized outcomes:{" "}
        <strong>{String(report.uses_realized_outcomes)}</strong>
      </p>
      <p className="view-meta">{report.panel.denominator_note}</p>
      <div className="table-scroll">
        <table>
          <caption className="visually-hidden">
            synthetic grade report strategies
          </caption>
          <thead>
            <tr>
              <th scope="col">strategy</th>
              <th scope="col">budget</th>
              <th scope="col">book max / mean / median</th>
              {GRADE_THRESHOLDS.map((threshold) => (
                <th scope="col" key={threshold}>
                  ≥{threshold}
                </th>
              ))}
              <th scope="col">C − S</th>
              <th scope="col">paired Δ (W/T/L)</th>
            </tr>
          </thead>
          <tbody>
            {report.strategies.map((strategy) => (
              <tr key={strategy.strategy_id}>
                <td>{strategy.strategy_id}</td>
                <td>{strategy.entry_budget}</td>
                <td>
                  {strategy.book.max} / {strategy.book.mean} /{" "}
                  {strategy.book.median}
                </td>
                {GRADE_THRESHOLDS.map((threshold) => (
                  <td key={threshold}>
                    {strategy.threshold_hits[`${threshold}`]}
                  </td>
                ))}
                <td>{strategy.conversion.gap_c_minus_s}</td>
                <td>
                  {strategy.paired_weekly_delta.mean.toFixed(2)} (
                  {strategy.paired_weekly_delta.wins}/
                  {strategy.paired_weekly_delta.ties}/
                  {strategy.paired_weekly_delta.losses})
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="contest-unavailable" data-testid="contest-unavailable">
        Contest rank, duplication, payout, ROI:{" "}
        <strong>unavailable</strong> — {report.contest_metrics_note}
      </p>
    </section>
  );
}
