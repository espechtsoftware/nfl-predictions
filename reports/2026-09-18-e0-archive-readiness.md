# Existing D800 archive: structural readiness for an outcome-disabled pilot

September 18, 2026. Read-only structural inspection following synthetic E0. No NFL result values read.

The previously identified prelock D800 archive contains 800 candidate rows, 397 frame rows and two
float32 score arrays, each shaped (397, 10000). Parquet object hashes, GCS generations/checksums,
full schemas and NPY headers are recorded in `reviews/evidence/2026-09-18-e0-archive-schema.json`.
The inspection script is beside it. Parquet bytes were downloaded into memory solely to read structural
metadata; no row values were decoded. NPY reads were limited to the first 512 bytes for the headers.
Book JSON/CSV, exposure ledger and receipt payloads were not opened.

Important: `frame.parquet` includes an `actual` column. Future reads must select an explicit allowlist
of prelock input columns and never decode `actual`. Candidate columns include selection/audit summary
estimates; those must likewise be excluded from the initial identity/roster census. Existing column names
such as `aud_mean` do not establish an independent evaluation bank.

## What this supports

A real fixed-pool mechanics pilot appears structurally feasible without regenerating candidates:
800 delivered rows and dimensionally compatible player matrices are retained. This is stronger than a
filename-only existence check. It is not proof of unique/legal candidates, correct player ordering,
prelock feature provenance, exact replay, or independence of the archived banks.

## Remaining prerequisites, in order

1. Read only candidate identity/roster columns and frame identity columns under a frozen allowlist.
   Establish unique candidate counts, legal roster shape, player mapping and array-row order from writer
   code plus retained identities. Matching row counts alone do not establish ordering.
2. Inspect the archive writer and an allowlisted receipt subset for generating code/config and source
   timestamps. Never assume incumbent versus corrected_hsim means independent random banks; these names
   imply different laws, which is a different contrast from same-law independent evaluation.
3. Determine a reproducible independent-audit construction, with a small cost cap, before selection.
   A held-out split of an old score bank is at most a conditional pilot: candidates may have been generated
   using those same worlds, and the split does not remove generation dependence retrospectively.
4. Freeze a separate pilot protocol for precision and selection stability under the stated model law.
   No realized-score grading, money-path reordering, or full historical reconstruction follows automatically.

The synthetic experiment is complete; this real-pool step remains a readiness inventory, not a launched
performance study. The September 10 archive concerns one already-observed Week-1 slate and an older live
revision; any later results must be labelled retrospective development.

## Follow-up: identity census and exact writer trace completed

Allowlisted read pinned to previously recorded object generations/hashes found 800 unique roster sets,
800 unique candidate IDs and 397 unique player IDs. All players map to the frame; the nine-player
position-count checks, salary identity and $50,000 cap checks passed for all candidates. These are
basic structural checks, not a full slate eligibility/stacking/entry-time legality certification.
No actual, ranking, selection/audit metric columns or score matrix values were decoded.
Evidence: `reviews/evidence/2026-09-18-e0-archive-identity.json` and adjacent script.

Receipt identifies clean lab commit `fa5d035ba99928f71736cbb77222515e9cdd94a8`, seed 2026, 10,000
worlds per component, K80, selector dual_emax, and build September 10 before the September 13 lock.
Frame and roster order hashes are now recorded. The exact archived code's `candidate_matrix` maps
`frame.id` in its existing order to score-array rows. `model_draws` fills by frame masks, the saved
incumbent matrix is `sel_draws`, and the frame write only drops `nkey` without reordering. This is
source-based ordering support rather than an embedded immutable player-ID vector in each array.
Receipt contains array SHA256 values; full NPY-byte hash verification remains before consumption.

Crucial independence finding from that exact revision's `scripts/live_week.py`:

- Generation seed 2026; incumbent selection seed 2076; incumbent audit seed 2126.
- Corrected-hsim seed 2326. Its worlds and incumbent selection worlds are concatenated for selection:
  **20,000 component-world columns total**, not 10,000 total. The two components represent different laws.
- Saved sidecars are incumbent **selection** and corrected-hsim **selection** matrices. Neither is an
  independent audit of the selected mixture book. Treating the second sidecar as a holdout is invalid.
- The independent incumbent audit is used for candidate marginal summaries but its full matrix is
  not persisted by this writer. It is not a full-mixture audit even if recovered elsewhere.
- Incumbent draws are shifted to shared means; corrected-hsim calibrates its own weights. New seeds
  alone need not reproduce a fixed common conditional law if calibration is refitted for each seed.

Therefore there is no validated independent full-mixture audit bank in these sidecars. Do not launch
an original-law precision claim on a split of the existing matrices and call it independent validation.

## Concrete next pilot choices

A bounded **empirical-distribution pilot** is possible: freeze the archived mixture as an empirical
joint distribution; independently sample decision and audit columns from it (preserving entire
joint-world columns and equal component mass), select on decision samples and evaluate on the full
empirical distribution. That estimates resampling instability conditional on this particular archive.
It is not new original-law worlds, real calibration, or an unbiased estimate of the original selection
optimism. The archived pool and distribution may share upstream estimation, and empirical tails can
omit rare events. A protocol must make those limits primary, not a footnote.

The stronger alternative needs archived components/model identities and fixed hsim calibration weights
(or reproducible matching construction) to generate an independent same-law mixture bank, with generation,
selection and calibration randomness explicitly separated. Ask the workstation for any retained full
incumbent audit arrays or fixed calibration weights before rebuilding anything. File names alone do not
establish those properties. No historical full-panel regeneration is justified yet.
