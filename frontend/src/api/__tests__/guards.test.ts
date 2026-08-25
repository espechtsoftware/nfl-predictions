import { describe, expect, it } from "vitest";
import { classifyProjectionOutcome } from "../guards";
import { VIEW_NAMES } from "../types";
import {
  FIXTURE_NOW_FRESH_MS,
  FIXTURE_NOW_STALE_MS,
  degradedStatusFixture,
  emptyResponseFixture,
  partialResponseFixture,
  readyResponseFixture,
  schemaMismatchBodyFixture,
} from "../../fixtures/projection";

describe("classifyProjectionOutcome", () => {
  it("classifies a fresh complete payload as ready", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: readyResponseFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("ready");
    if (result.state === "ready") {
      expect(result.ageSeconds).toBe(1800);
      for (const name of VIEW_NAMES) {
        expect(result.projection.views[name]!.length).toBeGreaterThan(0);
      }
    }
  });

  it("classifies empty views as partial and names them", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: partialResponseFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("partial");
    if (result.state === "partial") {
      expect(result.emptyViews).toEqual([
        "active-pointer-promotion-traversal",
        "lineup-player-team-game-traversal",
      ]);
    }
  });

  it("classifies an all-empty payload as empty", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: emptyResponseFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("empty");
  });

  it("classifies an old payload as stale with its exact age", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: readyResponseFixture,
      nowMs: FIXTURE_NOW_STALE_MS,
    });
    expect(result.state).toBe("stale");
    if (result.state === "stale") {
      expect(result.ageSeconds).toBe(9 * 3600);
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

  it("rejects a malformed 200 body as schema-mismatch", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 200,
      body: schemaMismatchBodyFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("schema-mismatch");
  });

  it("rejects a malformed 503 body as schema-mismatch", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 503,
      body: { nonsense: true },
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("schema-mismatch");
  });

  it("never treats an unexpected status as renderable data", () => {
    const result = classifyProjectionOutcome({
      httpStatus: 500,
      body: readyResponseFixture,
      nowMs: FIXTURE_NOW_FRESH_MS,
    });
    expect(result.state).toBe("schema-mismatch");
  });
});
