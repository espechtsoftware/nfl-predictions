import { render, screen, within, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { classifyProjectionOutcome } from "../../api/guards";
import {
  FIXTURE_NOW_FRESH_MS,
  FIXTURE_NOW_STALE_MS,
  degradedStatusFixture,
  partialResponseFixture,
  readyResponseFixture,
} from "../../fixtures/projection";
import { syntheticGradeReportFixture } from "../../fixtures/gradeReport";
import { CorpusResearchPage, PaginatedTable } from "../CorpusResearch";

function readyAvailability() {
  return classifyProjectionOutcome({
    httpStatus: 200,
    body: readyResponseFixture,
    nowMs: FIXTURE_NOW_FRESH_MS,
  });
}

describe("CorpusResearchPage", () => {
  it("renders every view section with fixture-exact row counts", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    for (const [name, rows] of Object.entries(
      readyResponseFixture.projection.views,
    )) {
      const meta = screen.getByTestId(`view-meta-${name}`);
      expect(meta.textContent).toContain(`${rows.length} rows`);
    }
  });

  it("reconciles a specific comparison delta cell to the fixture", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const section = screen.getByTestId(
      "view-paired-heldout-fill-retrieval-comparison",
    );
    const rows =
      readyResponseFixture.projection.views[
        "paired-heldout-fill-retrieval-comparison"
      ]!;
    const lastDelta = rows[rows.length - 1]!.delta as number;
    expect(lastDelta).toBe(0.5);
    expect(within(section).getAllByText("0.5").length).toBeGreaterThan(0);
  });

  it("shows exact registry identity, counts, and authority flags", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    expect(screen.getByTestId("identity-registry").textContent).toBe(
      "corpus-strategy-registry-fixture-001",
    );
    expect(screen.getByTestId("identity-counts").textContent).toContain(
      "88 nodes",
    );
    expect(screen.getByTestId("identity-counts").textContent).toContain(
      "51 governed winners",
    );
    expect(screen.getAllByTestId("authority-flag")).toHaveLength(5);
    expect(screen.queryByText(/VIOLATED/)).toBeNull();
  });

  it("renders sanitized provenance without raw bucket links", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const release = screen.getByTestId("identity-source-release");
    expect(release.textContent).toContain("generation 1787000000000001");
    expect(document.querySelector("a[href^='gs://']")).toBeNull();
    expect(release.textContent).not.toContain("gs://");
  });

  it("derives evidence tiers per section instead of one page-wide badge", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.querySelector(".evidence-badge")).toBeNull();
    const presetSection = screen.getByTestId("view-preset-registry");
    const badges = within(presetSection).getAllByTestId("evidence-badge");
    expect(badges.map((badge) => badge.getAttribute("data-tier"))).toEqual([
      "retrospective-simulated",
    ]);
    const censusSection = screen.getByTestId("view-registry-firewall-census");
    expect(within(censusSection).queryByTestId("evidence-badge")).toBeNull();
  });

  it("renders stale and partial truth together when both hold", () => {
    const availability = classifyProjectionOutcome({
      httpStatus: 200,
      body: partialResponseFixture,
      nowMs: FIXTURE_NOW_STALE_MS,
    });
    render(<CorpusResearchPage availability={availability} />);
    expect(screen.getByTestId("stale-badge").textContent).toContain("9.0h");
    expect(screen.getByTestId("state-partial").textContent).toContain(
      "active-pointer-promotion-traversal",
    );
    expect(
      screen.getByTestId("view-empty-active-pointer-promotion-traversal")
        .textContent,
    ).toContain("empty, not zero");
  });

  it("renders the degraded state without any data sections", () => {
    render(
      <CorpusResearchPage
        availability={{ state: "degraded", status: degradedStatusFixture }}
      />,
    );
    expect(screen.getByTestId("state-degraded").textContent).toContain(
      "projection-not-configured",
    );
    expect(screen.queryByTestId("authority-banner")).toBeNull();
  });

  it("renders unauthorized, unreachable, and schema-mismatch distinctly", () => {
    const { rerender } = render(
      <CorpusResearchPage
        availability={{ state: "unauthorized", httpStatus: 403 }}
      />,
    );
    expect(screen.getByTestId("state-unauthorized")).toHaveAttribute(
      "role",
      "alert",
    );
    rerender(
      <CorpusResearchPage
        availability={{ state: "unreachable", detail: "connection refused" }}
      />,
    );
    expect(screen.getByTestId("state-unreachable").textContent).toContain(
      "transport failure",
    );
    rerender(
      <CorpusResearchPage
        availability={{ state: "schema-mismatch", detail: "bad payload" }}
      />,
    );
    expect(screen.getByTestId("state-schema-mismatch").textContent).toContain(
      "bad payload",
    );
  });
});

describe("PaginatedTable", () => {
  const manyRows = Array.from({ length: 120 }, (_, index) => ({
    ordinal: index,
    label: `row-${index}`,
  }));

  it("pages long tables instead of rendering every row", () => {
    render(
      <PaginatedTable label="many" columns={["ordinal", "label"]} rows={manyRows} />,
    );
    expect(screen.getAllByRole("row")).toHaveLength(51);
    expect(screen.getByTestId("pager-many").textContent).toContain(
      "showing 1–50 of 120",
    );
  });

  it("is keyboard-operable through real focusable buttons", () => {
    render(
      <PaginatedTable label="many" columns={["ordinal", "label"]} rows={manyRows} />,
    );
    const next = screen.getByRole("button", { name: "many: next page" });
    const prev = screen.getByRole("button", { name: "many: previous page" });
    expect(prev).toBeDisabled();
    next.focus();
    expect(next).toHaveFocus();
    fireEvent.click(next);
    expect(screen.getByTestId("pager-many").textContent).toContain(
      "showing 51–100 of 120",
    );
    expect(screen.getByRole("button", { name: "many: previous page" }))
      .toBeEnabled();
  });
});

describe("GradeReportPreview", () => {
  it("renders 36 absolute summaries and 15 paired summaries from the mirrored contract", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const report = syntheticGradeReportFixture.report;
    expect(report.absolute_strategy_budget_summaries).toHaveLength(36);
    expect(report.primary_paired_summaries).toHaveLength(15);
    const absolute = screen.getByTestId("grade-report-absolute-table");
    expect(absolute.querySelectorAll("tbody tr")).toHaveLength(36);
    const paired = screen.getByTestId("grade-report-paired-table");
    expect(paired.querySelectorAll("tbody tr")).toHaveLength(15);
  });

  it("keeps the governed and fixture evidence layers separate", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const evidence = screen.getByTestId("grade-report-evidence");
    expect(evidence.textContent).toContain("uses realized outcomes: true");
    expect(evidence.textContent).toContain(
      "fixture construction read outcomes: false",
    );
    const preview = screen.getByTestId("grade-report-preview");
    const badge = within(preview).getAllByTestId("evidence-badge")[0]!;
    expect(badge.getAttribute("data-tier")).toBe("synthetic-fixture");
  });

  it("reconciles paired summary arithmetic to its weekly contrasts", () => {
    const report = syntheticGradeReportFixture.report;
    const summary = report.primary_paired_summaries[0]!;
    const weekly = report.weekly_primary_contrasts.filter(
      (row) =>
        row.challenger_strategy_id === summary.challenger_strategy_id &&
        row.entry_budget === summary.entry_budget,
    );
    expect(weekly).toHaveLength(54);
    const deltaSum = weekly.reduce(
      (sum, row) => sum + row.weekly_maximum_delta.micro_dk,
      0,
    );
    expect(summary.overall.weekly_maximum_delta_sum.micro_dk).toBe(deltaSum);
    expect(summary.overall.slate_count).toBe(54);
    expect(
      summary.overall.challenger_better_slate_count +
        summary.overall.exact_tie_slate_count +
        summary.overall.challenger_worse_slate_count,
    ).toBe(54);
    expect(summary.leave_one_slate_sensitivity).toHaveLength(54);
    expect(summary.season_summaries).toHaveLength(6);
  });

  it("reconciles a book row's gap to the shared union ceiling", () => {
    const report = syntheticGradeReportFixture.report;
    const row = report.weekly_strategy_budget_rows[0]!;
    const union = report.shared_union_ceiling_rows[row.source_ordinal]!;
    expect(
      row.maximum.micro_dk + row.gap_to_shared_corpus_ceiling.micro_dk,
    ).toBe(union.shared_union_maximum.micro_dk);
    expect(report.weekly_strategy_budget_rows).toHaveLength(54 * 12 * 3);
    expect(report.weekly_primary_contrasts).toHaveLength(54 * 5 * 3);
  });

  it("renders contest metrics as unavailable and the five limitations", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    expect(screen.getByTestId("contest-unavailable").textContent).toContain(
      "unavailable",
    );
    expect(
      screen
        .getByTestId("grade-report-limitations")
        .querySelectorAll("li"),
    ).toHaveLength(5);
    expect(screen.getByTestId("grade-report-detail-note").textContent).toContain(
      "1,944",
    );
  });
});
