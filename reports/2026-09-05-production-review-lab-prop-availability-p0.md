# Production review: lab P0 prop-availability builder

**Date:** 2026-09-05  
**Reviewed lab commit:** `2e253529a01477447dfa2f7fa54f369b67713f15`  
**Disposition:** **NO-GO for executing or publishing P0 from this commit**  
**Scope:** interface and mechanics review only; no outcome, score, or cloud state opened or changed

The commit is a useful builder skeleton and matches much of the intended
definition, but four defects can materially change coverage or violate the
pre-lock boundary. Repair these before running the real 36-slate census. The
absence of the D800 join/census in this commit is expected and is listed
separately; it is not the reason for this no-go.

**Immediate disposition:** stop the local PREREG-069 donor census reported in
lab Update 77. Its published mask/root and any census output derived from that
mask are void as P0 evidence. Preserve them only as explicitly failed
diagnostic artifacts; do not overwrite or delete create-once objects. Repair
the builder, publish a fresh generation under a new root identity, and restart
the score-free census from that accepted input. This changes no score-bearing
experiment and does not affect SD-C.

## P0 blockers

### 1. The physical no-outcome boundary is not yet real

`main()` calls unrestricted `slates("k1")` and `slate_frame()` before slicing
to `FRAME_ALLOWLIST`. `slates()` loads the full `snap_pitclean_k1` table, and
`slate_frame()` loads both that table and `player_week_training`. Those source
frames contain fields such as `actual`, `y_*`, and `was_active`. Dropping the
columns after they have entered the process is not a physical outcome
firewall.

Required repair:

- add or reuse a loader that performs Parquet/source **column pushdown** and
  materializes only the explicitly allowlisted pre-lock fields;
- obtain the slate-key manifest through the same score-free path rather than
  unrestricted `slates()`;
- prove with a focused test that the builder process cannot load the outcome
  columns or the released PREREG-064 Parquet; and
- bind the exact score-free source-object identities in the root artifact.

Production evidence: `src/nfl2/pipeline.py:95-112` implements the unrestricted
`slate_frame()` path; `src/nfl2/data.py:100-152` identifies `actual`, `y_*`,
and `was_active` as outcome fields and documents column pushdown as the
physical boundary.

### 2. Every anytime-touchdown quote is currently discarded

The builder requires `outcome_name == "Yes"` for `player_anytime_td`.
Production ingestion does not store that shape: for the one-way anytime-TD
market, the API outcome's player name is stored in `outcome_name`, with
`player` populated from that same value when no description exists.

Required repair:

- accept a valid anytime-TD row when `outcome_name` resolves to the same
  player as the raw `player` field and the price is finite; no point or
  opposite side is required;
- change the fixture to the production raw shape, for example
  `outcome_name="Rashee Rice", player="Rashee Rice"`; and
- add a negative test for a mismatched named-player outcome.

Production evidence: `src/nfl_dfs/ingest/oddsapi_import.py:100-121` explicitly
documents and implements `anytime_td: name=player (no point)`.

### 3. Ambiguous normalized names can silently win by insertion order

`resolve_players()` stores `ref` under raw display-name keys but checks
collision membership using the normalized name. Two different player IDs
whose raw names normalize identically can therefore overwrite one another.
The initial-key lookup can also be reported as `exact_norm` when the raw
abbreviation itself became a lookup key.

Required repair:

- construct an explicit `normalized_name -> set(player_id)` index within the
  event's two teams;
- admit an exact normalized match only when that set has exactly one ID;
- construct the initial-key index independently and admit it only when its ID
  set has exactly one member;
- return the resolution method from the branch actually used; and
- test normalized collisions, initial collisions, abbreviation fallback, and
  two same-name players on different games.

No fuzzy or post-census hand mapping is allowed.

### 4. Snapshot deduplication rejects resolvable repeated ingests

The code sorts by source snapshot and `pulled_at`, but its tie detector groups
only on the source snapshot. Two copies of the same quote with the same
snapshot and different `pulled_at` values are therefore rejected even though
the stated rule says the later stable ingestion key resolves them.

Required repair:

- freeze the exact priority as latest source snapshot strictly before lock,
  then latest `pulled_at` within that snapshot;
- reject only when the full winning priority remains tied with conflicting
  payload bytes or lacks a stable deterministic source-row hash;
- preferably create a SHA-256 row identity from the raw canonical fields and
  use it for exact-duplicate collapse and final deterministic ordering; and
- add tests for a later repeated ingest, exact duplicate, and conflicting
  unresolved tie.

## Release-strength repairs required before publishing the mask

These need not all live in the transformation function, but they must be
enforced by the P0 artifact wrapper:

1. Bind the exact donor player snapshot and exact D800 source artifacts. Table
   names, SQL hashes, and input row counts are not content identities.
2. Emit an explicit slate/DK salary-slate identity and a clearly named
   canonical player ID; verify player-ID uniqueness and use validated joins.
3. Use a total deterministic output order including slate, event, canonical
   ID, raw player, bookmaker, market, point, side, source timestamp,
   `pulled_at`, and source-row hash.
4. Publish immutable child URIs, bytes, generations, and SHA-256 values, then
   publish the root last. Reopen every child generation-exactly.
5. Verify the pinned name-normalizer dependency by its full SHA-256 rather than
   merely writing an unchecked prefix into metadata.

## Expected next package, not defects in this builder-only commit

P0 is not complete until a separate candidate-census layer provides:

- the exact 36-slate expected manifest and cells keyed by
  `(season, week, bank, generation_arm)`;
- exactly 800 unique, legal nine-player donor roster hashes per cell;
- left-joined source coverage, with a missing source week represented as zero
  support rather than a dropped cell;
- each candidate's count of 0-8 covered offensive players;
- unique all-eight and at-least-seven candidate counts by cell;
- admitted and excluded roster-hash partitions and source/family retention;
- salary, projection, role, mapping, source-health, and quote-age censuses; and
- the fail-closed rule that any cell below 80 all-eight candidates stops the
  strict exact-K80 experiment without fallback.

Neutral control, selection, outcome reader, and efficacy launch are later
packages and should not be added to this score-free builder repair.

## Production acceptance test

Production can accept a repaired P0 builder when focused tests demonstrate all
four blockers above, the source loader proves physical column pushdown, the
artifact wrapper binds immutable inputs/children, and a one-slate
outcome-disabled smoke completes without opening any settlement or outcome
source. At that point the lab may run the full score-free support census; it
still may not launch an efficacy experiment until the separate P0 support gate
passes and SD-C routing releases the score lane.
