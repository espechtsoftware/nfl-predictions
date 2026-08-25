# Observatory workstream — Phase 2 checkpoint corrective commit evidence

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-25
**Responds to:**
`reports/2026-08-25-observatory-phase2-lead-checkpoint-review.md`
(APPROVE WITH REQUIRED FIXES)
**Branch:** `feature/neo4j-react-observatory`

## P1 correction 1 — real Core grade-report contract (done)

`frontend/src/api/types.ts` and `frontend/src/fixtures/gradeReport.ts` now
mirror `scripts/report_core_v1_grade.py` exactly:

- the real 12-strategy catalog (`r194:` incumbent + six relaxation arms;
  `t230:` four retrieval strategies + support-switched policy), budgets
  4/14/80 → **36 absolute strategy/budget summaries**, thresholds
  180–250;
- exact integer micro-DK and reduced-rational numerator/denominator
  values with integer-exact ROUND_HALF_UP three-decimal display strings;
- full weekly censuses carried in the payload: 1,944 weekly book rows
  (54×12×3), 810 weekly primary contrasts (54×5×3), 15 primary paired
  summaries (5 challengers × 3 budgets vs `r194:incumbent`) each with
  season summaries, 54 leave-one-slate and 6 leave-one-season delta
  projections; 54 shared-union ceiling rows;
- completion/root object identities, realized-grade/catalog/outcome
  hashes, coverage census, the producer's fixed contest-metrics block and
  five exact limitations, and the authority fields:
  `uses_realized_outcomes: true` preserved INSIDE the payload with the
  five false license fields;
- the synthetic tier lives only in the separate UI wrapper
  (`SyntheticGradeReportFixture.fixture_evidence`), which states that
  fixture construction read no outcomes. The governed payload never
  claims outcome blindness.
- Internal consistency is tested: paired-summary delta sums replay from
  their weekly contrasts; book gaps replay against union ceilings; W/T/L
  partitions sum to 54.

## P1 correction 2 — deep, adversarial projection guards (done)

`frontend/src/api/guards.ts` now validates every nested object and
cross-binding before anything renders, returning the failing field in the
schema-mismatch detail:

- full v2 source receipt (identity patterns, gs:// release identity,
  digits generation, 64-hex hashes, positive counts, winner binding
  `winner_imported === (winner_count == 51)`, kind-count sum law,
  firewall);
- full query receipt (schema, publication mode, canonical identities,
  per-query name/cypher/rows hashes and counts, duplicate-name
  rejection, gcs/world-matrix flags, firewall);
- projection: view maps of record rows only, required views present,
  view-keys ↔ query-names bijection, `row_count` bound to view length;
- cross-object bindings: projection ↔ source ↔ query-receipt registry
  identity, database, generation time, and source-receipt sha binding;
  200-body bindings: status ready/reason, status ↔ projection
  registry/sha/view-row-counts.
- 13 adversarial mutation tests (missing/mistyped nested fields, winner
  and kind-count violations, identity and hash-binding mismatches,
  row-count drift, removed views/queries, malformed rows, firewall flips,
  status-binding drift) all classify as schema-mismatch before render.
- The UI labels server-verified hashes as such and performs no
  cryptographic verification.

## Wording and scope corrections (done)

- Page retitled **“Corpus Research — foundation slice”**; the Phase 1–2
  report's parity claims are corrected here: the legacy page still owns
  heatmap, paired chart, scatter, promotion timeline, lineage/network
  controls, and named scenarios until the visualization and route-parity
  gates. The legacy route is untouched.
- Transport failure is a distinct **unreachable** state (client maps
  thrown fetches to it); schema-mismatch is reserved for payloads that
  arrived and failed validation.
- **Stale and partial coexist**: the stale state carries the empty-view
  list and the page renders the stale badge and the partial notice
  together (tested).
- Evidence tiers are **derived per section** from row data; the
  page-wide hard-coded badge is removed (tested: census section shows no
  badge; preset section derives its tier).
- The `/corpus-research/next` route snippet is corrected (explicit
  `pathlib.Path` import) in the Phase 1–2 report and remains NOT applied;
  it stays deferred until nested wheel assets are packaged and tested.
- **Pagination** (50 rows/page) guards all generic view tables; long
  tables never render fully into the DOM (tested at 120 rows: 50 rendered,
  keyboard-operable pager buttons with aria labels and focus-visible
  styling).
- Claims are now matched by tests: build base-path/outDir/deterministic
  asset names are pinned by a config test; keyboard operability is
  tested; unverified responsive/browser-smoke claims are withdrawn until
  their tests exist (Phase 7 scope).

## Required validations (run serially, exact results)

1. `npm run typecheck` — clean.
2. `npm test` — **44/44** across 5 files.
3. `npm run build` — `assets/app.js` 219.65 kB (68.18 kB gzip),
   `assets/index.css` 3.11 kB; absolute `/static/app/` asset URLs.
4. `rm -rf node_modules && npm ci && npm run check` — 164 packages from
   the committed lock; typecheck + 44/44 + build reproduce.
5. `pytest tests/test_corpus_research_ui.py` (PYTHONPATH pinned to this
   worktree) — 8 passed.
6. `git diff --check` — clean.

No new dependency was added (`vite/client` types ship with the existing
vite dependency). No live graph, cloud, outcome, IAM, or deployment
action occurred.
