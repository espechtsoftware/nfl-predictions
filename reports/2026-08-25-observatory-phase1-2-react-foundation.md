# Observatory workstream — Phases 1–2 evidence and integration proposal

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-25
**Base commit:** `37b5f4817dab4310ade69a3027e13599ede0d157`
**Branch:** `feature/neo4j-react-observatory`
**Commits:** `b0a3df05` (Phase 0 inventory), `cab173df` (Phases 1–2)
**Toolchain:** node v22.22.1, npm 9.2.0 (lockfileVersion 3)

## Phase 1 — reproducible React foundation (complete)

Created under `frontend/src/`:

- `api/types.ts` — strict contracts mirroring
  `src/nfl_dfs/app/corpus_research.py`: status/projection/source-receipt/
  query-receipt schemas, the six required view names, the five reason codes,
  the authority-firewall booleans, the eight-state `Availability`
  discriminated union, and the synthetic
  `core-v1-human-readable-grade-report/v1` contract (12 strategies, budgets
  4/14/80, thresholds 180–250, book max/mean/median, threshold hits, C−S
  conversion, paired weekly/season deltas, leave-one-out share,
  `uses_realized_outcomes: false` pinned).
- `api/guards.ts` — runtime schema guards; `classifyProjectionOutcome`
  maps HTTP outcome → availability (200→ready/partial/stale/empty by view
  emptiness and a 6h staleness threshold; 503+status→degraded; 401/403→
  unauthorized; anything malformed→schema-mismatch). Missing never becomes
  zero; unvalidated payloads never render.
- `api/client.ts` — GET-only typed client; no write path exists.
- `fixtures/projection.ts` — deterministic fixtures for every state
  (fixed `2026-08-25T12:00:00Z` generation time; fresh and stale "now"
  constants; schema-valid synthetic receipts with illustrative hashes;
  winner binding `winner_imported === (winner_count == 51)` respected).
- `fixtures/gradeReport.ts` — the synthetic grade-report fixture; contest
  rank/duplication/payout/ROI carried as explicitly unavailable.
- `app/` — `App.tsx` shell (injectable loader), `ErrorBoundary`,
  `states.tsx` (loading/empty/degraded/unauthorized/schema-mismatch/
  partial/stale + evidence badge components), `routes.ts` (typed view
  registry isolating the deferred router decision), `app.css`.
- `test/setup.ts` — jest-dom + explicit RTL cleanup (vitest runs without
  globals, so auto-cleanup must be wired; this was caught by a real
  duplicate-node failure and fixed).

## Phase 2 — Corpus Research parity slice (complete, fixture-backed)

`pages/CorpusResearch.tsx` + `pages/GradeReportPreview.tsx` render:

- readiness/current-authority banner (five firewall chips; a violated flag
  renders loudly as `VIOLATED`);
- exact identity strip: registry, database·namespace, generation time +
  age, projection sha prefix, source release (generation · sha256 prefix ·
  bytes — sanitized identity metadata, **no raw `gs://` links**; a test
  asserts none render), node/relationship/winner counts;
- all six required views as generic column-stable tables with per-view
  row counts and query/rows hash prefixes from the query receipt;
- stale badge with exact age; partial notice naming empty views; empty
  views labeled "empty, not zero";
- the synthetic grade-report contract preview under a `synthetic-fixture`
  evidence badge with explicit unavailable contest metrics.

The legacy React 18 UMD/HTM page and its `/corpus-research` route are
untouched; no FastAPI file changed.

## Validation (each command run alone, in order)

| Command | Level | Result |
|---|---|---|
| `npm install` (lockfile generation) | offline/registry | 164 packages, lockfileVersion 3 committed |
| `npm run typecheck` | offline | clean |
| `npm test` | fixture | 20/20 across 3 files |
| `npm run build` | offline | `/static/app/assets/app.js` 200.91 kB (63.32 kB gzip), css 2.68 kB |
| built `index.html` base-path check | offline | both assets reference `/static/app/assets/...` absolute paths |
| `rm -rf node_modules && npm ci && npm run check` | offline/registry | reproduces byte-identical build from the committed lock |
| `pytest tests/test_corpus_research_ui.py` (PYTHONPATH pinned to this worktree; `nfl_dfs.__file__` verified) | offline | 8 passed |

No parallel heavy commands ran; the lane was checked idle before each.

## Proposed reversible integration (NOT applied — for lead review)

Step 1 (additive, zero-risk): serve the compiled page on a NEW route,
leaving `/corpus-research` (legacy) untouched:

```python
# src/nfl_dfs/app/corpus_research.py  — proposed diff, not applied
@router.get("/corpus-research/next", response_class=HTMLResponse)
def corpus_research_next_page() -> HTMLResponse:
    index = _Path(__file__).parent / "static" / "app" / "index.html"
    return HTMLResponse(
        index.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )
```

Rollback = delete the route. Step 2 (optional, after review): an
env-flagged switch (`CORPUS_RESEARCH_UI=react|legacy`, default `legacy`)
choosing which HTML `/corpus-research` returns; the legacy branch stays the
default and the compatibility assets are not deleted at any step (deletion
is a Phase 7+ decision behind the plan's gate).

## Known gaps carried forward (deliberate, documented)

- Wheel packaging still excludes nested `static/app/**`
  (`pyproject.toml` flat globs) — Phase 8 scope with an inventory test.
- No charting dependency — structure/tables first per the Phase 0
  decision record; shortlist recorded for Phase 6 review.
- No router dependency — single-view shell; adoption deferred to Phase 7.
- `/api/v1/foundry`, graph vNext contracts, capacity work: gated behind
  this checkpoint (Phases 3–5).

## Stop point

Stopped at the mandatory Phase 2 checkpoint per plan §7. No backend
contract changed; no live infrastructure touched; no outcome or governed
artifact read.
