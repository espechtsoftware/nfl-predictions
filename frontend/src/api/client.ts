/** Read-only typed client for the corpus-research projection API.
 *
 * The client only GETs. There is no write path, and none may be added: the
 * observatory is a read model, never a control plane.
 */

import { classifyProjectionOutcome } from "./guards";
import { Availability } from "./types";

export interface FetchLike {
  (input: string, init?: { headers?: Record<string, string> }): Promise<{
    readonly status: number;
    json(): Promise<unknown>;
  }>;
}

export interface ClientOptions {
  readonly fetchImpl?: FetchLike;
  readonly now?: () => number;
  readonly staleAfterSeconds?: number;
}

export const PROJECTION_URL = "/api/corpus-research/projection";
export const STATUS_URL = "/api/corpus-research/status";

export async function fetchProjectionAvailability(
  options: ClientOptions = {},
): Promise<Availability> {
  const fetchImpl: FetchLike =
    options.fetchImpl ?? (globalThis.fetch as unknown as FetchLike);
  const now = options.now ?? Date.now;
  let httpStatus: number;
  let body: unknown;
  let response: Awaited<ReturnType<FetchLike>>;
  try {
    response = await fetchImpl(PROJECTION_URL, {
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    return {
      state: "unreachable",
      detail: `projection transport failed: ${String(error)}`,
    };
  }
  httpStatus = response.status;
  try {
    body = await response.json();
  } catch {
    return {
      state: "schema-mismatch",
      detail: `HTTP ${httpStatus} body is not JSON`,
    };
  }
  return classifyProjectionOutcome({
    httpStatus,
    body,
    nowMs: now(),
    staleAfterSeconds: options.staleAfterSeconds,
  });
}
