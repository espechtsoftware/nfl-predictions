import { describe, expect, it } from "vitest";
import { classifyProjectionOutcome, projectionResponseFault } from "../guards";
import { ProjectionResponse, VIEW_NAMES } from "../types";
import {
  FIXTURE_NOW_FRESH_MS,
  FIXTURE_NOW_STALE_MS,
  degradedStatusFixture,
  emptyResponseFixture,
  partialResponseFixture,
  readyResponseFixture,
  schemaMismatchBodyFixture,
} from "../../fixtures/projection";

type Mutable = { [key: string]: any };

function mutated(
  mutate: (clone: Mutable) => void,
): ProjectionResponse {
  const clone = structuredClone(readyResponseFixture) as unknown as Mutable;
  mutate(clone);
  return clone as unknown as ProjectionResponse;
}

function classify(body: unknown, nowMs = FIXTURE_NOW_FRESH_MS) {
  return classifyProjectionOutcome({ httpStatus: 200, body, nowMs });
}

describe("classifyProjectionOutcome", () => {
  it("classifies a fresh complete payload as ready", () => {
    const result = classify(readyResponseFixture);
    expect(result.state).toBe("ready");
    if (result.state === "ready") {
      expect(result.ageSeconds).toBe(1800);
      for (const name of VIEW_NAMES) {
        expect(result.projection.views[name]!.length).toBeGreaterThan(0);
      }
    }
  });

  it("classifies empty views as partial and names them", () => {
    const result = classify(partialResponseFixture);
    expect(result.state).toBe("partial");
    if (result.state === "partial") {
      expect(result.emptyViews).toEqual([
        "active-pointer-promotion-traversal",
        "lineup-player-team-game-traversal",
      ]);
    }
  });

  it("classifies an all-empty payload as empty", () => {
    expect(classify(emptyResponseFixture).state).toBe("empty");
  });

  it("keeps partial truth inside the stale state", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: partialResponseFixture,
      nowMs: FIXTURE_NOW_STALE_MS,
    });
    expect(result.state).toBe("stale");
    if (result.state === "stale") {
      expect(result.ageSeconds).toBe(9 * 3600);
      expect(result.emptyViews).toEqual([
        "active-pointer-promotion-traversal",
        "lineup-player-team-game-traversal",
      ]);
    }
  });

  it("classifies a 503 status body as degraded", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 503,
      body: degradedStatusFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("degraded");
    if (result.state === "degraded") {
      expect(result.status.reason_code).toBe("projection-not-configured");
    }
  });

  it("classifies 401 and 403 as unauthorized", () => {
    for (const httpStatus of [401, 403] as const) {
      const result = classifyProjectionOutcome({
        httpStatus,
        body: {},
        nowMs: FIXTURE_NOW_FRESH_MS,
      });
      expect(result).toEqual({ state: "unauthorized", httpStatus });
    }
  });

  it("rejects malformed 200 and 503 bodies as schema-mismatch", () => {
    expect(classify(schemaMismatchBodyFixture).state).toBe("schema-mismatch");
    expect(
      classifyProjectionOutcome({
        httpStatus: 503,
        body: { nonsense: true },
        nowMs: FIXTURE_NOW_FRESH_MS,
      }).state,
    ).toBe("schema-mismatch");
    expect(
      classifyProjectionOutcome({
        httpStatus: 500,
        body: readyResponseFixture,
        nowMs: FIXTURE_NOW_FRESH_MS,
      }).state,
    ).toBe("schema-mismatch");
  });
});

describe("adversarial nested mutations classify as schema-mismatch", () => {
  const cases: readonly [string, (clone: Mutable) => void, string][] = [
    [
      "missing nested source plan hash",
      (clone) => {
        delete clone.projection.source_projection_receipt.plan_sha256;
      },
      "plan_sha256",
    ],
    [
      "mistyped registry node count",
      (clone) => {
        clone.projection.source_projection_receipt.registry_node_count =
          "many";
      },
      "registry_node_count",
    ],
    [
      "winner binding violation",
      (clone) => {
        clone.projection.source_projection_receipt.winner_count = 50;
      },
      "winner-import binding",
    ],
    [
      "kind counts sum mismatch",
      (clone) => {
        clone.projection.source_projection_receipt.kind_counts.Lineup += 1;
      },
      "kind_counts sum",
    ],
    [
      "registry identity mismatch across receipts",
      (clone) => {
        clone.projection.query_receipt.registry_id = "other-registry";
      },
      "registry_id differs from query receipt",
    ],
    [
      "source receipt sha binding mismatch",
      (clone) => {
        clone.projection.query_receipt.source_projection_receipt_sha256 =
          "0".repeat(64);
      },
      "sha binding differs",
    ],
    [
      "view row_count mismatch",
      (clone) => {
        clone.projection.views["preset-registry"].pop();
      },
      "row_count",
    ],
    [
      "required view removed",
      (clone) => {
        delete clone.projection.views["strategy-lineage"];
      },
      "strategy-lineage",
    ],
    [
      "query receipt entry removed for a view",
      (clone) => {
        clone.projection.query_receipt.queries =
          clone.projection.query_receipt.queries.filter(
            (query: Mutable) => query.name !== "registry-firewall-census",
          );
      },
      "registry-firewall-census",
    ],
    [
      "malformed view row",
      (clone) => {
        clone.projection.views["preset-registry"][0] = "not-a-record";
        clone.projection.query_receipt.queries = clone.projection.query_receipt
          .queries;
      },
      "is not an object",
    ],
    [
      "firewall flip on the projection",
      (clone) => {
        clone.projection.read_only = false;
      },
      "read_only",
    ],
    [
      "status/projection hash binding mismatch",
      (clone) => {
        clone.status.projection_sha256 = "f".repeat(64);
      },
      "projection_sha256 differs",
    ],
    [
      "status row-count binding mismatch",
      (clone) => {
        clone.status.view_row_counts["preset-registry"] = 999;
      },
      "view_row_counts",
    ],
  ];
  for (const [name, mutate, expectedDetail] of cases) {
    it(name, () => {
      const body = mutated(mutate);
      const fault = projectionResponseFault(body);
      expect(fault).not.toBeNull();
      expect(fault).toContain(expectedDetail);
      const result = classify(body);
      expect(result.state).toBe("schema-mismatch");
    });
  }

  it("the unmutated fixture has no fault", () => {
    expect(projectionResponseFault(readyResponseFixture)).toBeNull();
  });
});
