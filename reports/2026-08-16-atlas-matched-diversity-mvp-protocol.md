# ATLAS matched-diversity MVP protocol

**Frozen:** 2026-08-16 CDT, after strict current-money Part-A harvest and
before any MVP construction output or realized-outcome query

**Protocol:** `20260816-atlas-matched-diversity-mvp-v1`

**Evidence class:** outcome-free, point-in-time score-free construction test

**Production impact:** none

## Question

At the same native candidate budget, with unchanged non-boom families,
CBWU-OI admission and final exact-80 selector, does the fixed ATLAS
matched-diversity construction add robust high-tail candidate coverage and
conditional player-interaction reach without materially sacrificing the
selected book's 194/230 support?

Current-money Part A established that the ATLAS v1 world ranking consistently
finds higher attainable exact legal optima. It also showed modest pair/game
concentration. This protocol freezes Part B/C: enumerate diverse near-optimal
lineups inside eight structural world clusters and measure whether that
premise survives the complete fixed-budget construction path.

## Outcome firewall

The acquisition, construction, admission, selection and effect disposition
must not query or read player actual scores, candidate actual scores, selected
historical memberships, contest ranks, ownership results, payouts or any
post-lock field. SQL and local schemas fail closed on those tokens. This cell
cannot promote a historical arm, estimate ROI or claim a realized-score gain.

## Immutable sources

- The five current-money player/candidate world panels
  `20260815-atlas-money-worlds-r0-v1` through `r4-v1`.
- The complete 54-slate, 270-cell source grid and all execution/environment
  receipts under
  `reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/`.
- The production-law transfer report SHA-256
  `8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446`.
- The exact point-in-time player catalog and production legality receipt used
  by the transfer.
- The frozen CBWU-OI implementation and its passed score-free source report
  SHA-256
  `556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`.

Each native source contains 10,000 player worlds and its fixed candidate book.
The required candidate tags are exactly `lev`, `epi`, `game`, `dark`, `qbvar`
and `boom`; all tags except exact `boom` are non-boom. Candidate identity is
the sorted nine-player ID tuple, never row order.

### R3/2025 Week 1 identity repair

The transfer validly used the preregistered player-world GCS recovery for
R3/2025 Week 1 after an ancillary BigQuery 429. Part B additionally needs that
cell's candidate rosters and tags, which the NPZ intentionally does not
contain. Before the MVP analyzer runs, launch one source-only deterministic
repair from the exact original image, code, seeds, player inputs and
simulation environment into a new create-only panel/output identity.

The repair is valid only if, after stable player/candidate alignment:

1. `player_ids`, all 10,000 `player_draws`, `cand_ix` and all candidate totals
   exactly equal the original immutable GCS object;
2. exactly 248 unique legal candidate rosters reconstruct those totals within
   `1e-4` and carry one permitted tag;
3. exactly 40 are tagged `boom`; and
4. the execution-owned image, command, resources, environment, account and
   terminal state pass a strict receipt check.

Any numerical or identity mismatch invalidates the MVP source. The repair may
not substitute a different world, candidate book or simulator law.

## Three fixed books

| Book | Native generator | Candidate admission | Role |
|---|---|---|---|
| P0 | incumbent 40-boom | canonical R0--R4 quota/fill CBWU | non-gating production context |
| P1 | incumbent 40-boom | complete-union CBWU-OI v1 | causal control |
| P2 | ATLAS 8x5 boom | complete-union CBWU-OI v1 | treatment |

P2 versus P1 is the only causal contrast. P2 versus P0 is disclosed composite
context. All books use identical five player-world blocks, point-in-time
players, non-boom families, native R0 candidate budget, 194 CBWU-OI admission
rule and unchanged exact-80 194-coverage selector.

## Fixed structural world clusters

For each native seed/slate independently:

1. rank all 10,000 worlds by the passed ATLAS v1 roster-slot upper bound,
   breaking ties by world ID;
2. exact-solve the top 40 worlds with the production $49,000--$50,000,
   QB+2, bring-back, two-game, RB/DST and same-team-RB rules and the shared
   two-pass stable identity tie-break;
3. scan those worlds in ATLAS proxy order and take the first world for each
   previously unseen dominant-game signature until eight anchors exist;
4. if fewer than eight dominant games exist, continue the same scan taking
   the first previously unseen QB-stack-core signature, then the first unused
   exact world if still necessary; and
5. assign every non-anchor top-40 world to the lowest-index anchor with the
   same dominant game; if none matches, assign it to the anchor with maximum
   exact-roster overlap, breaking ties by anchor index. Within each cluster,
   order worlds by ATLAS proxy rank then world ID.

The eight anchors, memberships and fallback reason are retained. A cell with
fewer than eight exact unique rosters is mechanically invalid.

## Eligible interactions and fixed pricing

The eligible universe is derived only from distinct native R0--R4 candidate
rosters:

- every unordered player pair appearing in at least one legal native roster;
- stack-core triples consisting of one QB and two same-team WR/TE pass
  catchers appearing together in at least one native roster; and
- no other triples.

For tuple `t` and block `b`, define support as the maximum native-candidate
probability of clearing 194 among candidates containing `t`, cross-scored on
block `b`. For an ATLAS source seed `k`, price the tuple from the other four
blocks only: sort their four supports, drop the minimum and maximum, and
average the middle two. This is the fixed leave-one-seed-out robust support.

Let `a(t)` be the number of native seed books (1--5) containing the tuple.
The novelty multiplier is
`min(2.0, sqrt(5 / a(t)))`. Multiply robust support by this capped multiplier.
Normalize positive pair weights and positive triple weights separately to
sum to one, then assign fixed class masses `0.80` to pairs and `0.20` to
stack-core triples. Empty positive pair support invalidates the cell; an empty
triple class transfers its `0.20` mass to pairs and is explicitly reported.

Coverage is conditional on the complete distinct non-boom union: every tuple
already represented by any non-boom roster starts covered and contributes no
novelty objective. After each accepted ATLAS lineup, its newly covered
eligible tuples are removed from later objectives. Weights are never derived
from realized outcomes or from the block whose source seed is being priced.

## Near-optimal enumeration and count parity

For each seed/slate, generate exactly five accepted lineups per structural
cluster, 40 total, in five round-robin passes over cluster index:

1. the first accepted lineup for a cluster/world is its exact legal world
   optimum;
2. every later solution for that world must retain at least `98%` of its
   positive optimum;
3. stage two maximizes the currently uncovered fixed interaction weight;
4. stage three retains the stage-two optimum within `1e-9` and minimizes the
   stable sum of player identity ranks; and
5. every prior ATLAS roster and every native non-boom roster is banned only as
   an exact nine-player identity (`max_overlap=8`), not by a generic Hamming
   diversity rule.

If a world cannot supply the next unique 98%-eligible addition, move to the
next ranked world in that cluster. If that cluster exhausts, refill from the
next cluster cyclically while retaining the originating seed and the same
98% rule. Never loosen the score floor, interaction definition or legality.

The incumbent source must contain exactly 40 unique `boom` additions per seed
and exactly 200 globally distinct boom additions per slate after deduplication
against the complete non-boom union. P2 must likewise contribute exactly 40
per seed and 200 globally distinct additions. A deficit is a mechanical
failure, not permission to add solves or candidates after seeing results.

Each P2 synthetic native book is its unchanged non-boom candidates plus the
40 ATLAS additions, reconstructed on the same native player-world matrix.
P2 then passes through the exact same CBWU-OI fixed-budget admission as P1.

## Required receipts

For every seed/slate and aggregate, retain:

- source hashes, player/world identity and the R3 recovery receipt;
- cluster anchors, signatures, membership and refill path;
- solve attempts, feasible results, exact duplicates and unique additions;
- optimum, absolute regret, percentage regret, 98% floor, interaction
  optimum and stable identity objective for every proposal;
- native, global discovery, admitted and final exact-80 candidate counts;
- conditional eligible pair/triple coverage and weighted coverage per added
  candidate;
- player frequency, pair/core/game reach, overlap and effective rank;
- candidate-pool and exact-80 best-of-book p194/p210/p230 on every block; and
- the same quantities by source seed with its pricing-excluded block clearly
  labeled. That block is held out from tuple pricing, not from source-world
  selection or common five-block OI admission, and must not be described as a
  fully independent historical holdout.

Repeated runs and player/candidate row permutations must reproduce cluster,
proposal, admission and exact-80 identities exactly.

## Frozen score-free disposition

Mechanical validity is evaluated first. Only a fully valid, count-matched
P0/P1/P2 result receives an effect disposition.

The P2-versus-P1 MVP score-free gate passes only if all are true:

1. aggregate conditional eligible pair weight covered is strictly higher;
2. aggregate conditional stack-core-triple weight retains at least `90%` of
   P1 (or the triple class is validly empty and disclosed);
3. candidate-pool best-of-book p210 coverage improves strictly in aggregate
   and on at least three of five pricing-excluded blocks;
4. candidate-pool p230 coverage retains at least `95%` of P1; and
5. final exact-80 p194 and p230 coverage each retain at least `90%` of P1.

Report exact-80 p210 as a primary diagnostic but do not add a post-result
threshold. Also report the complete 187/194/200/210/220/230/240 grid,
per-season distributions, capped preservation, q10/median/min reach ratios,
entropy/Simpson effective counts, pairwise roster overlap, top-player Jaccard
and full maximum-game signatures including ties.

These are score-free shadow-admission conditions, not a money promotion gate.
A valid pass licenses one separately labeled 2026 pre-lock P0/P1/P2 shadow.
A valid failure closes MVP v1 and routes to the already-declared stack-core x
shell fallback; it does not license tuning the 98% floor, class masses,
cluster rule or thresholds from historical outcomes.

## Prospective consequence

If licensed, freeze P0/P1/P2 candidate and exact-80 books before each 2026
lock. Afterward report candidate C and selected S at every registered tail
threshold, distinct-slate crossings, mean/downside, overlap, effective rank
and influence at Weeks 4/8/13/18. The descriptive prior is improvement mainly
in the 194--210 shoulder; any 220+ gain is stronger-than-prior evidence, not a
retroactive requirement. Production remains unchanged until a separate
prospective promotion decision.
