# ATLAS MVP R3/2025 source-repair protocol

**Frozen:** 2026-08-16 CDT, before launching the repair replay

**Protocol:** `20260816-atlas-mvp-source-repair-r3-2025-v1`

**Production impact:** none

## Purpose

The original production-law R3/2025 replay uploaded its complete Week 1
candidate/player-world NPZ, but a subsequent ancillary BigQuery write was
rate-limited. The production-law transfer validly used the immutable NPZ; the
matched-diversity MVP additionally needs Week 1 candidate roster identities
and generator tags. This source-only repair recovers them without changing a
simulation, candidate-generation, scoring, or selection setting.

## Immutable source

- Execution: `replay-atlasmoney-r3-2025-htrch`
- Execution receipt SHA-256:
  `60173988c785b88253052e40d73cfe396f9947c44f84f4bfe279be781db07ca9`
- Image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8`
- Code SHA: `545ddae1b8e1256fde8e345683e0004aa5463b5e`
- Full environment SHA-256:
  `f0807cc2045d59b89fd7cd856e8633b88c105250fdfc09ffe91efbfe13ca6f03`
- Original Week 1 artifact:
  `gs://nfl-predictions-503414-raw/cand_scores/20260815-atlas-money-worlds-r3-v1/2025_w1_0590227023eb.npz`
- Original artifact SHA-256:
  `7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805`

The rerun must use the same image, command, 2025 input, 4 CPU, 16 GiB RAM,
14,400-second timeout, zero retries, service account, code identity, two
random seeds, and every environment value.

## Only permitted changes

Exactly two infrastructure destinations change:

| Key | Original | Repair |
|---|---|---|
| `PANEL_RUN_ID` | `20260815-atlas-money-worlds-r3-v1` | `20260816-atlas-mvp-repair-r3-2025-v1` |
| `REPLAY_LINEUPS_TABLE` | `nfl-predictions-503414.nfl_features.replay_lineups_atlasmoney_r3_2025` | `nfl-predictions-503414.nfl_features.replay_lineups_atlas_mvp_repair_r3_2025` |

Both destinations are create-only. No existing panel or diagnostic roster
table may be overwritten.

## Strict completion gate

The repair is usable only if all checks pass:

1. the execution is a clean immutable terminal success and its complete
   receipt differs from the source only at the two destinations above;
2. all 18 expected 2025 slate cells persist and Week 1 has exactly 248 unique
   candidates, exactly 40 exact-`boom` tags, and only registered tags;
3. original and repaired Week 1 `player_ids`, `player_draws`, `cand_ix`,
   `totals`, and `tail_line` arrays are exactly equal;
4. each stored Week 1 roster contains nine unique catalogued players and its
   player-world sum equals its candidate-total row within absolute `1e-4`;
5. each roster is a legal $49,000--$50,000 DK Classic roster with the frozen
   position, game, stack, bring-back, RB/DST and same-team RB constraints.

Any missing cell, mismatch, duplicate, illegal roster, relaxed tolerance,
different tag count, or receipt difference invalidates the source and stops
the MVP. The repair reads no realized player/candidate outcome, contest rank,
payout or post-lock field data.
