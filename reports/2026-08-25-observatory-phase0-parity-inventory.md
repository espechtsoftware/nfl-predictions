# Observatory workstream — Phase 0 parity and contract inventory

**Workstream:** Neo4j/React observatory (delegated lane per
`reports/2026-08-25-parallel-neo4j-react-observatory-workstream-plan.md`)
**Date:** 2026-08-25
**Base commit:** `37b5f4817dab4310ade69a3027e13599ede0d157` (origin/main tip,
recorded at worktree creation)
**Branch:** `feature/neo4j-react-observatory`
**Worktree:** `/home/erich/projects/nfl-predictions-observatory` (isolated;
the lead's live worktree is untouched)
**Toolchain observed:** node v22.22.1, npm 9.2.0 (these exact versions will
produce the committed lockfile)

Nothing in this phase changes production code. Every capability row cites the
artifact that proves it; absence of a citation means the capability is
UNPROVEN, not assumed.

## 1. Route/action inventory (current application)

Server-rendered pages (all in `src/nfl_dfs/app/main.py` unless noted):

| Page | Route | Kind | Notes |
|---|---|---|---|
| Season | `GET /` | HTML dashboard | title "Season"; entry page |
| Lineups | `GET /lineups/view` | HTML | lineup review UI |
| Defense | `GET /defense` | HTML | plus `GET /defense/points-against`, `GET /defense/trends` JSON |
| Market | `GET /market` | HTML | market dashboard |
| Watchlist | `GET /watchlist` | HTML | plus `/api/watchlist` GET, `POST /api/watchlist/{id}/convert`, `DELETE /api/watchlist/{id}` |
| About | `GET /explainer` | HTML | explainer page |
| Corpus Research | `GET /corpus-research` | HTML shell + React 18 UMD/HTM | `src/nfl_dfs/app/corpus_research.py:706` |

Construction/action endpoints (Classic/Showdown/downloads):

- Classic: `GET /classic/slates`, `POST /lineups`, `POST /lineups/record`,
  `POST /lineups/core`, `POST /lineups.csv`
- Showdown: `GET /showdown/slates`, `POST /showdown/lineups`,
  `POST /showdown/lineups.csv`, `POST /showdown/lineups/entries.csv`
- Entries/exports: `POST /lineups/entries.csv`,
  `POST /lineups/entries/validated.csv`, `POST /lineups/entries/diff`,
  `POST /lineups/entries/recourse/preview`,
  `POST /lineups/entries/recourse/rehearsal`
- Results: `GET/POST /results`, `GET /results/lineups`,
  `GET /results/exports`, `DELETE /results/lineups`, `POST /results/score`,
  `POST /results/import`
- Misc JSON APIs: `/api/line-movement`, `/api/market-disagreement`,
  `/api/note-conflicts`, `/api/market-tails`, `/api/accuracy`,
  `/api/external-diff`, `/api/cfb-export-links`, `/api/system-status`,
  `/api/contest-compare` (POST), `/api/external-projections` (POST),
  `/health`, `/chat` (POST), `/prefs` (GET/POST/DELETE),
  `/players/search`, `/entries/swap` (POST), `/slates`, `/projections`,
  `/contests`
- Static: `app.mount("/static", ...)` (`main.py:44`); `/docs` remains
  FastAPI's OpenAPI route.

Parity implication: Phase 7 will need slices for 7 pages + the
Classic/Showdown action set + CSV downloads + navigation/deep-refresh. None
of this is touched before the Phase 2 checkpoint.

## 2. Corpus-research API/projection schema inventory

Proven by `src/nfl_dfs/app/corpus_research.py` and
`tests/test_corpus_research_ui.py` (focused suite, offline):

- `GET /api/corpus-research/status` → `corpus-research-ui-status/v1`:
  `ready`, `reason_code`, `message`, firewall booleans (`read_only`,
  `graph_mutation`, `automatic_promotion`, `application_config_mutation`,
  `production_policy_authority`), and when ready: `registry_id`, `database`,
  `generated_at_utc`, `projection_sha256`,
  `view_row_counts{view: count}`. `Cache-Control: no-store`.
- Reason codes (complete set, from `FileCorpusResearchProjectionReader` and
  `ReadOnlyQueryProjectionReader`): `ready`, `projection-not-configured`,
  `projection-invalid-or-unavailable`, `graph-query-projection-failed`,
  `projection-validation-failed`.
- `GET /api/corpus-research/projection` → 200 `{status, projection}` when
  ready; **503 with the status payload** otherwise (degraded contract).
- Projection body `corpus-research-ui-projection/v1`: `registry_id`,
  `database`, `namespace="corpus-strategy-registry"`, `generated_at_utc`
  (second-precision UTC), `source_projection_receipt`
  (`corpus-strategy-registry-projection/v2`), `query_receipt`
  (`corpus-research-ui-query-receipt/v1` with per-query
  `name/cypher_sha256/row_count/rows_sha256`), `views`, firewall booleans,
  `projection_sha256` (self-hash).
- Required views (exactly these six names must be present):
  `preset-registry`, `strategy-lineage`,
  `paired-heldout-fill-retrieval-comparison`,
  `active-pointer-promotion-traversal`,
  `lineup-player-team-game-traversal`, `registry-firewall-census`.
  Combined row cap `MAX_QUERY_ROWS = 100_000`.
- Source receipt v2 field law (for fixture accuracy):
  `registry_release{uri gs://…, generation digits, sha256, bytes>0}`,
  `plan_sha256`, `registry_node_count>0`, `registry_relationship_count>=0`,
  `winner_imported === (winner_count == 51)`, `kind_counts` summing to
  `registry_node_count`, `publication_mode="create_once"`,
  `manifest_namespace_v2_authorized=true`, firewall booleans,
  `projection_receipt_sha256`.
- Cypher firewall: catalogued queries only; regex rejects
  CREATE/MERGE/DELETE/SET/CALL/etc. (`_FORBIDDEN_CYPHER`).

Frontend note: sha256 self-hashes are validated SERVER-side; the browser
renders but never claims to verify them. Fixtures use schema-valid shapes
with clearly illustrative hex strings.

## 3. Neo4j node/relationship/query inventory (current)

- Storage layer is deliberately generic: nodes `:CorpusRetrievalEntity` with
  a `kind` property; relationships `:CORPUS_RELATION` with
  `relationship_type` and `edge_key`
  (`cypher/corpus_retrieval_neo4j_schema.cypher`).
- Analysis catalog: `cypher/corpus_retrieval_analysis_queries.cypher`.
- Modules: `corpus_retrieval_neo4j.py` (loader/plan),
  `corpus_neo4j_transport.py` (governed transport: exact-generation reads,
  TLS/principals, allowlisted namespaces, idempotent receipts, terminal
  census), `corpus_neo4j_extensions.py` (guarded
  `append_population_phenotypes` builder — NOT wired into manifest, plan,
  receipts, CLI, query catalog, or UI), `corpus_strategy_registry.py`
  (v12-era: seven fill presets, one exact-80 retrieval, three-lineup
  samples; no `AdmissionPreset`, `ExperimentManifest`, `ExperimentCell`,
  `Evaluation`, `StrategyBundle`, `SelectedBook`, `Fold` entities yet).
- Proof level: offline focused-green only
  (`tests/test_corpus_retrieval_neo4j.py`,
  `tests/test_corpus_neo4j_transport.py`,
  `tests/test_corpus_research_ui_bridge.py`). **No live Neo4j endpoint,
  secret, complete release load, capacity receipt, or production graph
  pointer exists** — per the foundation report
  `reports/2026-08-21-corpus-research-neo4j-foundation.md`.

## 4. Data classification (fixture-only / accepted / absent / gated)

- **Fixture-only:** everything the new React foundation renders in Phases
  1–2 (all eight availability states; the synthetic
  `core-v1-human-readable-grade-report/v1` product fixture). No fixture
  encodes governed outcomes.
- **Accepted (exists, NOT consumable by this lane yet):** v12 54-slate
  panel artifacts and the combined panel index owned by the lead/custodian.
  This lane consumes them only as custodian-supplied terminal identities,
  after the Phase 2 checkpoint, per plan §7 Phase 4.
- **Absent:** winner-cohort UI data products, trait/cohort releases,
  experiment/evaluation registry objects (vNext), any `/api/v1/foundry`
  surface.
- **Gated:** realized outcomes (historical-outcome lease; Core grades),
  contest rank/duplication/payout/ROI (no complete historical field data —
  must render explicitly "unavailable", never inferred).

## 5. Packaging/deployment seams

- **Package-data gap (confirmed):** `pyproject.toml` ships
  `"nfl_dfs.app" = ["static/*", "static/vendor/*"]` — flat globs. Vite
  emits NESTED `static/app/assets/*`; a built wheel would currently DROP
  the compiled app. Fix belongs to the packaging phase (Phase 8), with a
  wheel/container inventory test; recorded here as a known seam, not
  changed now.
- Vite config (`frontend/vite.config.ts`): base `/static/app/`, outDir
  `../src/nfl_dfs/app/static/app`, `emptyOutDir: true`, deterministic asset
  names (`assets/app.js` etc.), vitest configured with
  `./src/test/setup.ts` (file to be created in Phase 1).
- No application Dockerfile has a frontend build stage; `Dockerfile` copies
  `src/` only. Foundry images (`Dockerfile.foundry-t230`,
  `Dockerfile.corpus-research-expansion`) are OUT OF SCOPE for this lane.
- `/frontend/node_modules/` is already root-anchored in `.gitignore`
  (line 26). No `package-lock.json` exists yet — Phase 1 creates it.
- The compatibility page renders into a server-generated shell
  (`CORPUS_RESEARCH_HTML`) with React 18 UMD + HTM from
  `/static/vendor/` — it stays untouched as the fallback.

## 6. Decision record (frontend routing and charting)

**Routing — decision: no new routing dependency before the checkpoint.**
Phases 1–2 mount one React page (Corpus Research parity) served by its
existing FastAPI route; an internal typed view-switch module
(`src/app/routes.ts`) isolates navigation so a real router (react-router v7
is the shortlisted candidate) can be adopted at Phase 7 without rewriting
pages. Rationale: plan §14 treats unreviewed dependency additions as a stop
condition; deep-route refresh semantics depend on Phase 7 server-route
decisions that are explicitly deferred.

**Charting — decision: defer the charting dependency; ship structure and
tables first** (explicitly permitted by plan §7 Phase 1). The existing
compatibility page hand-renders into `<svg>` nodes, so parity does not
require a library. Phase 2 uses small typed inline-SVG primitives with
table fallbacks. Shortlist for the lead-reviewed Phase 6 follow-up:
1. keep hand-rolled SVG primitives (zero deps, full control, precedent in
   the compat page);
2. visx (modular, React-19 compatible, tree-shakeable);
3. recharts (fastest to build, heaviest bundle).
Recommendation at Phase 6 time: (1) unless interaction complexity demands
(2).

## 7. Proof map (what is demonstrated by what)

| Capability | Proof artifact |
|---|---|
| Projection/status contract | `tests/test_corpus_research_ui.py` (offline) |
| Registry → UI bridge | `tests/test_corpus_research_ui_bridge.py` (offline) |
| Graph loader/plan | `tests/test_corpus_retrieval_neo4j.py` (offline) |
| Governed transport laws | `tests/test_corpus_neo4j_transport.py` (offline) |
| React 19 build reproducibility | NOT YET PROVEN — Phase 1 exit criterion |
| Wheel inclusion of compiled app | NOT PROVEN — known gap (§5), Phase 8 |
| Live graph anything | DOES NOT EXIST — gated behind §8 of the plan |

## 8. Files intentionally not touched in this phase

All production code; the lead's live worktree and dirty files; every entry
on the plan §6.4 no-touch list (T230/G0/Core/R6 paths, Foundry envs,
transports, cloudbuild/Dockerfiles, IAM/secrets/BigQuery/GCS).
