import { describe, expect, it } from "vitest";
import { fetchProjectionAvailability } from "../client";
import { readyResponseFixture } from "../../fixtures/projection";

describe("fetchProjectionAvailability", () => {
  it("maps a transport failure to unreachable, not schema-mismatch", async () => {
    const result = await fetchProjectionAvailability({
      fetchImpl: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    expect(result.state).toBe("unreachable");
    if (result.state === "unreachable") {
      expect(result.detail).toContain("Failed to fetch");
    }
  });

  it("maps a non-JSON body to schema-mismatch", async () => {
    const result = await fetchProjectionAvailability({
      fetchImpl: async () => ({
        status: 200,
        json: async () => {
          throw new SyntaxError("Unexpected token <");
        },
      }),
    });
    expect(result.state).toBe("schema-mismatch");
  });

  it("classifies a valid 200 body through the deep guards", async () => {
    const result = await fetchProjectionAvailability({
      fetchImpl: async () => ({
        status: 200,
        json: async () => structuredClone(readyResponseFixture),
      }),
      now: () => Date.parse("2026-08-25T12:30:00Z"),
    });
    expect(result.state).toBe("ready");
  });
});
