# Preregistration: study 48, does a lineup "look like a winner"? A winner-likeness score on the built book (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-06 night), verbatim:** "After the lineups are put together … would there be any benefit to
  loading them into Neo4j and looking at each of them quickly and seeing if it looks like a winner?" Then: "I want to
  do it right away."
- **On the inputs**, through the outside reviewer's plan (`reports/2026-10-06-neo4j-winner-likeness-inputs.md`,
  review branch `4533254f`): "make sure that all the inputs … has all the data points that could help it look like a
  winner … for each player selected in a lineup, what their red zone … attempts are, the number of touchdowns, the
  number of attempts".
- **The question, in his terms:** among the lineups we have already built (his live book's 26 rows), do the ones that
  look more like recent winners finish better at the same projection? If they do not, no tiebreak or swap built on the
  look can help. That makes this the cheap first test. Neo4j stays the tool for looking (the laptop's facts layer);
  this study is the test.
- **The prior, stated before any outcome:**
  - Every test of choosing among good lineups so far sits at chance: the "monkeys", 098, the class model, and study 32
    at one entry.
  - Copying the regulars' visible habits did not carry their edge (study 34).
  - The winning shape follows the game script week to week.
  - The contrarian row read WORSE (study 45).
  - The book already matches the winners' shape rates.
  - So NO DIFFERENCE is the likeliest reading.

## 2. The score (point-in-time; `experiments/s48_winner_like.py`)
**The winners it learns from.** For each PRIOR slate, the winners are the top 1% by realized points of that slate's
calibrated field: the v2 sampler drawing 60,000 lineups from the slate's real Millionaire ownership, which is known by
then. The rest of that field is the contrast: a random 6,000, weighted to stand for the 59,400.
- On 2022–24 no real lineups exist, so these are SAMPLED-field winners, and the player-history feature means "players
  often in the sampled top 1%".
- Only the 2026 Monday line (descriptive) sees REAL winners.

**The features of a lineup (24), all PRE-LOCK; the same week's red-zone touches, touchdowns and points never enter
(tested):**
- **Shape and field:**
  - the QB's WR / TE teammates (0–3);
  - a bring-back (an opponent RB / WR / TE);
  - a QB-team RB;
  - the players from the QB's game;
  - the players from the slate's top-total game (pre-lock totals);
  - the salary used;
  - the mean ownership percentile rank of its skill players. In training this uses the prior slate's REAL ownership.
    In scoring it uses the pre-lock TABPFN prediction. It is rank-based, so the prediction's compression does not
    matter; its noise only attenuates this feature at scoring.
  - the mean frequency of its players in the top-1% lineups of the 4 previous slates of the season.
- **The operator's per-player facts:**
  - **Red zone and goal line:** the summed red-zone (inside 20) and end-zone targets of its RB / WR / TEs over the last
    4 weeks, and the goal-line (inside 3) carries of its QB / RBs.
  - **Volume:** the mean target share, WOPR and route share of its WR / TEs; the mean carry share of its RBs; the mean
    snap share of its RB / WR / TEs; its WR / TEs' team vacated target share.
  - **Environment:** the QB's team implied total, spread and game total.
  - **Touchdowns and attempts** (nflverse weekly stats, each player's last 4 / 8 regular-season games strictly before
    the slate's week, across seasons): the summed rushing + receiving TDs of its RB / WR / TEs over 4 and over 8 games;
    the QB's passing TDs and pass attempts over his last 4.
  - These come from the harness frame's lagged columns, present for 2022–24, with missing = 0. In Week 1 the 4-week
    windows are empty; that holds the same in training and scoring.
- **Named in the plan but absent from the harness frames, so not used:**
  - the props-implied projection (`market_points`, absent in 2022);
  - `xfp_l4` (about 40% present);
  - the model's TD and attempt components (empty).

**The model.** A weighted logistic regression on standardized features (ridge 1e-3, Newton steps). It is fitted on
2022 plus the 2023–24 slates strictly before the scored slate: 17–52 training slates, about 6,600 rows each. The score
is its linear predictor.
- **The training table** (`scripts/s48_prep.py`, built once) is byte-deterministic. Its identity `66272167…` is
  recorded in every row and asserted single by the reader. Two builds gave the same bytes.
- **The training draws' seeds** are `slate_seed(9000, …)` and `slate_seed(9001, …)`. No bank derives them: a bank's
  seeds are bank + 50 and bank + 700, so equality would need banks 8950 / 8951 / 8300 / 8301, which the scan found
  unused. The laptop found no prior `slate_seed(9000 …)` anywhere.

## 3. The test (the harness of studies 46–47: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- On each slate-bank his live Week-5 book is built: study 47's MIXT_LIVE, which is the winners' mix, the QB cap 5,
  caps 13 / 6, no term, the limit 4 and the round-robin. Its 26 book rows are scored by the model fitted on earlier
  slates.
- Each row's realized finish percentile is read on the calibrated field v2, with l02 beside it.

## 4. Endpoint and rule (the reader `scripts/s48_report.py`)
- **PRIMARY:** per slate-bank, the PARTIAL rank correlation between the score and the realized finish percentile on
  v2 over the 26 book rows, holding the row's projection fixed (ranks; both residualized on the projection's rank).
  - The slate's value is the mean over its banks.
  - Banks 1521–1526: the laptop's scan is clean, with no hits anywhere.
  - B 20,000, seed 20261028; slates resampled within season; two-sided 0.95.
- **Verdicts:**
  - **PASS:** lower bound > 0, with at most one season mean < 0. Looking like a winner predicts a better finish at
    equal projection, so the score is a candidate tiebreak. It needs its own book-level test.
  - **NEGATIVE:** upper bound < 0.
  - **NO DIFFERENCE:** otherwise.
- **There is no money guard.** This is a mechanism test, and it moves nothing by itself.
- **EXPLORATORY:**
  - the same on the l02 field;
  - the plain rank correlation, with no projection held;
  - the 5 most against the 5 least winner-like rows of each book: their mean finish and their top-1% rate.

## 5. What a verdict can do
- **PASS:** the read states what a Week-5 use would need, so he can decide on real facts:
  - a book-level swap test, preregistered (does replacing the least winner-like rows with winner-like spares raise
    P(≥ 1 big)?);
  - production code by Friday 17:00 (a score in vetting);
  - Friday's rehearsal.

  Otherwise it is a Week-6 candidate.
- **NO DIFFERENCE or NEGATIVE:** a Monday descriptive line only (the score on his real book against the real
  Millionaire field). The Neo4j facts layer remains the place to look.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path):
  - the book was built and every row scored, with 17 training slates (2022);
  - the census and the reader exited 0; the reader printed its 2 headers, and its header names STUDY 48 (tested);
  - about 58 s per slate-bank.
- **The binding census** (outcome-blind; bank 1406; 36/36, code `ecfa069` clean; `results/s48/CENSUS_s48_binding.txt`
  `905a8b56…`, raw `eb6ac1bd…`):
  - every book row was scored on the 24 frozen features, with 17–52 training slates;
  - the score's standard deviation within a book is 0.316, and its rank correlation with the rows' projection is
    +0.037. That near-independence makes the at-equal-projection test informative.
  - The mean standardized coefficients: ownership rank +0.200, snap share +0.159, QB teammates +0.114, the QB's
    passing TDs (last 4) +0.100; end-zone targets −0.227 and TDs over the last 4 −0.126. These are conditional
    coefficients from the training slates (prior outcomes), not findings about the scored slates.
- **Code:** nfl2 `production/s48-winner-like-20261006` @ `ecfa069` (the census at `853d143`):
  - `experiments/s48_winner_like.py`, sha256 `c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c`;
  - `scripts/s48_prep.py`, `46a63ad50895fcc4473ede8600245bf71dfa53751f2f925aac46a076ac6d368f`;
  - `scripts/s48_drive.py`, `0523b007f6d19f3be13ad0002a9ba7b17f02792c5a9c32acfc152ed4e0301e03`;
  - **`scripts/s48_report.py` (the reader), sha256 `c8d9ece7b3b4169b8d86492b58aa588c7ae7d71f3c3f947866ea7f1d7498cdb5`**;
  - `scripts/s48_census.py`, `0df8e0609c4f5f690a61738b2d999e6ea6f7bd9fc71dd919d33a7aab591d3cf2`;
  - `tests/test_s48_winner_like.py`, `25a6c1c9696d6ec482fa9e7a118eafe3642f370c14d055933382ea8beb345ef2` (9 tests);
  - `experiments/mix_fill.py` `dcf6a299…` and `experiments/l02b_field_sampler.py` `fadf9cfe…`, unchanged.
- **Order:** this freeze → the laptop's ack (the census and the prep re-run) and bank scan → the scored run → the
  confirmatory census, committed before the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
- **Disclosed:** the score's inputs were widened before this freeze, at the operator's and the outside reviewer's
  request (the per-player facts). The census was re-run on the widened code. No outcome of the scored slates was seen
  at any step.
