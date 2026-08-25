import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { classifyProjectionOutcome } from "../../api/guards";
import {
  FIXTURE_NOW_FRESH_MS,
  FIXTURE_NOW_STALE_MS,
  degradedStatusFixture,
  partialResponseFixture,
  readyResponseFixture,
} from "../../fixtures/projection";
import { gradeReportFixture } from "../../fixtures/gradeReport";
import { CorpusResearchPage } from "../CorpusResearch";

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

  it("marks stale payloads with the stale badge and exact age", () => {
    const availability = classifyProjectionOutcome({
      httpStatus: 200,
      body: readyResponseFixture,
      nowMs: FIXTURE_NOW_STALE_MS,
    });
    render(<CorpusResearchPage availability={availability} />);
    expect(screen.getByTestId("stale-badge").textContent).toContain("9.0h");
  });

  it("names empty views in the partial state and renders them as empty", () => {
    const availability = classifyProjectionOutcome({
      httpStatus: 200,
      body: partialResponseFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    render(<CorpusResearchPage availability={availability} />);
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

  it("renders unauthorized and schema-mismatch states as alerts", () => {
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
        availability={{ state: "schema-mismatch", detail: "bad payload" }}
      />,
    );
    expect(screen.getByTestId("state-schema-mismatch").textContent).toContain(
      "bad payload",
    );
  });

  it("previews the synthetic grade report with all 12 strategies and explicit unavailable contest metrics", () => {
    render(<CorpusResearchPage availability={readyAvailability()} />);
    const preview = screen.getByTestId("grade-report-preview");
    const bodyRows = preview.querySelectorAll("tbody tr");
    expect(bodyRows).toHaveLength(gradeReportFixture.strategies.length);
    expect(gradeReportFixture.strategies).toHaveLength(12);
    expect(screen.getByTestId("contest-unavailable").textContent).toContain(
      "unavailable",
    );
    expect(preview.textContent).toContain("uses realized outcomes: false");
  });
});
