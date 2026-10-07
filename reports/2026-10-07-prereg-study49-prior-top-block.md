# Preregistration: study 49, the prior-top term block in the harness (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator's decision (10-07, through the laptop):** the prior-top term goes into Week 5 LIVE, capped, on part
  of the book. He chose "Live, capped, part of book" over paper-only and the uncapped whole-book form.
  - The term: a player's mean share of the PRIOR weeks' real Millionaire top-1% lineups, 5 × z within position,
    clipped at 0 (the outside reviewer's `make_priortop_files.py`).
  - The form: 8 of the 26 rows are built after the live block, on the projection + min(0.20 × pred_own, 2.0)
    (production `union_reselect --term-block-rows 8`, the laptop's `production/term-block-20261007`).
- **Its evidence is three weeks, in-sample.**
  - The uncapped whole-book replay (Weeks 2–4): P(≥ 1 big) .041 → .014, .002 → .303 and .434 → .764.
  - The exact capped 8-row form: .041 → .031, .002 → .093 and .434 → .404. That is ahead in one week of three; the
    mechanics are clean and there is no disaster.
- **His yes to this study (10-07, about 05:20):** "Yes, run it". Over 36 slates the harness cannot prove the term,
  because its winners are sampled-field winners. But it can catch harm before Sunday: a WORSE read would be a reason
  to pull the block.
- **The prior, stated before any outcome:**
  - The harness already carries this idea. Study 48's `hist` feature (a player's share of the prior slates' sampled
    top-1% lineups) has an all-53 coefficient of −0.01. Recent touchdowns regress (td_l4 −0.10, end-zone targets
    −0.17).
  - The census (§6) prices the block at 0.48 projected points per row. Its 8 rows average 123.7 against 129.1 for the
    live block's.
  - So NO DIFFERENCE, leaning WORSE, is the likeliest reading.

## 2. Arms (`experiments/s49_term_block.py`; the block in `experiments/term_book.py`)
**The build.** On each slate-bank his live Week-5 book and production's 15 spares are built: 41 rows through one
state, with the winners' mix, the round-robin, limit 4, QB cap 5, caps 13 / 6 and no ownership term. Study 48's harness
is used throughout (`s48_winner_like.py` `c22d2811…`, imported and sha-asserted). It is built three ways:
- **LIVE** (reference): mix_fill's round-robin, called. On the smoke slates its 41 rows and dealt ranks equal study
  48d's exactly.
- **TERM8** (DECISION): production's term block, `term_book` (sha `62c2306e…`; study 38's amendment 6 copies the same
  file):
  - one state;
  - the 18-row live block first, study 42's round-robin on the quotas at its size, on the plain objective;
  - then the 8-row block, the same at its size, on the objective + the capped term;
  - the block's rows at study 46's block_positions(26, 8): ranks 2, 5, 9, 12, 15, 18, 22 and 25;
  - each block interleaved on its own positions' head weights;
  - the 15 spares after, on the plain objective.
- **TERM_ALL** (exploratory): the outside reviewer's replay form, every row (book and spares) on the objective + 0.20 ×
  pred_own, uncapped.

**The harness analogue of the file**, per scored slate:
- **The source:** each prior slate of the season's sampled top-1% lineups (study 48's training draws: the calibrated
  v2 field drawn from that slate's REAL ownership, 60,000 lineups, the top 1% by REALIZED points; training table
  `66272167…`).
- **prior_top:** each player's share of those lineups, averaged over the prior slates he was on.
- **pred_own:** 5 × z within position (over every player of those slates), clipped at 0, exactly as
  `make_priortop_files.py`.
- **The term, as production's own_bonus then the cap:** skill players only; 0.20 × pred_own where pred_own > 0;
  min(·, 2.0) for TERM8.
- **The coverage gate:** coverage is the share of the pool's skill players projected ≥ 5 who appear in the prior
  slates. Below 0.5 there is no block (production's refusal).
- **Week 1 has no prior slate:** no file, so TERM8 and TERM_ALL equal LIVE there (2 of 36 slates, counted).

**Production's constraints** (caps 13 / 6, QB 5, the overlap limit 4) are asserted on every arm's 41 rows. Each arm's
41 rows are dealt by the head layout.

**Tested** (`tests/test_s49_term_block.py`, 9 tests), on a scripted builder whose cells offer their rows by the CURRENT
objective:
- with no term rows, term_book IS mix_fill's round-robin (rows, cells, spares, the builder's final state, the solves);
- with 8 term rows, the live block is built first on the plain objective, then the term block on the objective + the
  term, then the spares on the plain objective again (each solve's objective checked);
- the block sits at block_positions(26, 8);
- a failing cell passes its quota to A1;
- the file's rule, strictly prior (never the scored week or another season; a slate the player missed is not a zero);
- the term, the cap and the coverage gate;
- the constraint check;
- the census is outcome-blind;
- the reader's levels and verdicts.

## 3. Endpoint and rule (study 18b's; the reader `scripts/s49_report.py`)
- **PRIMARY:** P(≥ 1 big seat) per slate on the calibrated field v2, TERM8 − LIVE.
  - Two-sided 0.95. B 20,000, seed 20261101; slates resampled within season.
  - Banks 1545–1550. The reviewer's unique-blob scan of both repositories found these numbers as banks or seeds only
    in study 49's own usage lines. That covers every blob in history up to 5 MB; the 8 larger blobs per repository
    were not searched.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdicts:** DEAD LEVER (TERM8 dealt identically to LIVE on more than 80% of slate-banks) / WORSE (upper < 0) /
  PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY** (two-sided 0.95): TERM_ALL − LIVE; both on l02; each arm's levels, projection, predicted ownership
  and term points per row.

## 4. What a verdict can do
This study informs a decision he has already made (the block is armed for Week 5 on his word). It cannot license the
term, because the harness's winners are sampled.
- **WORSE:** the harness says the block costs big seats. I recommend pulling it before the lock (TERM_ROWS = 0), and
  he decides.
- **NO DIFFERENCE:** the block stays his capped, modest bet. The weekly evidence is study 38's MIXT_QA0_NOTERM line
  (amendment 6): his book without the block, on the real field every week.
- **PASS or FAIL (guard):** reported as read. A PASS supports keeping the block; it does not prove the term.

## 5. Production parity
The lab's term block equals production's. Study 38's amendment-6 smoke built the lab's book with the 8-row block from
the Week-4 inputs. Its 26 book rows equal the laptop's Week-4 term8 union book (production 26fb8d40) position by
position, 26 of 26.

## 6. Smoke and integrity
- **The smoke** (2024 W10 and 2023 W1, bank 1406, the full path; run twice, the second time on the final code
  `94f3e6d`):
  - every arm built 41 rows within production's constraints;
  - LIVE equals study 48d's 41 rows and ranks on both slates;
  - on 2024 W10 the block sat at ranks 2, 5, 9, 12, 15, 18, 22 and 25, and 17 of 26 rows were shared with LIVE;
  - on 2023 W1 there was no file, and both term arms were identical to LIVE;
  - the second run is identical to the first apart from timing and the term-book sha (the block moved verbatim into
    its own file);
  - the census and the reader exited 0. The reader printed its 2 headers, and its header names STUDY 49 (tested).
- **The binding census** (outcome-blind; bank 1406; 36/36, code `94f3e6d` clean; `results/s49/CENSUS_s49_binding.txt`
  `2d14d898…`, raw `81967ce6…`; lab `037ca38`):

  | | LIVE | TERM8 | TERM_ALL |
  |---|---|---|---|
  | projection per row (change) | 128.04 | 127.56 (−0.48) | 123.79 (−4.25) |
  | predicted ownership per row (change) | 78.56% | 78.72% (+0.16) | 72.57% (−6.00) |
  | capped term points per row | 8.68 | 9.85 | 12.24 |
  | book rows shared with LIVE | — | 16.8 of 26 | 1.4 of 26 |
  | identical to LIVE | — | 0.056 | 0.056 |

  - The file applies on 34 of 36 slates. Where it applies: 99 pool players carry a term, 27 of them at the 2-point
    cap (the largest uncapped term is 8.1 points); coverage is 0.98 on average (minimum 0.72).
  - TERM8's block rows project 123.74 against its live block's 129.11.
  - No quota passed to A1 and no row was dropped. About 56 s per slate-bank at 8 workers, beside 48e's run.
- **Code:** nfl2 `production/s49-term-block-20261007` @ `94f3e6d` (the census at `037ca38`):
  - `experiments/s49_term_block.py`, sha256 `fc674f267f7b5b7a6c5407df5558cf09a553f72e28c7304e80cbc32a222a3515`;
  - `experiments/term_book.py`, `62c2306eff1135713d599b788bcbd29be9db308c2eb8537183f3d291b996b887`;
  - `scripts/s49_drive.py`, `77b6a96d0ddd5b295caca1bfd5ec488bd42beb593390807159818f3dc2dff3d8`;
  - **`scripts/s49_report.py` (the reader), sha256 `8cae1f22363637efa678a2125bd78dc5ca5e7e0796269d164337ef8e5ae9121f`**;
  - `scripts/s49_census.py`, `076cea95d12ee029b5083bc07d95824397a747a2a3aefa37d28de624e242e30a`;
  - `tests/test_s49_term_block.py`, `f42bf322c0253ea8033bc41fea71edbb93363ca4c6d6197e6d2737271d78e8de` (9 tests);
  - `experiments/s48_winner_like.py` `c22d2811…`, `experiments/s46_half_half.py` `30647fef…`, `experiments/mix_fill.py`
    `dcf6a299…` and `experiments/l02b_field_sampler.py` `fadf9cfe…`, unchanged.
- **Order:** this freeze → the laptop's ack and bank scan → the scored run (after study 48e's) → the confirmatory census,
  committed before the read → the read → the laptop's re-run → the LEDGER row and an Addendum. The read goes to him
  before Friday's arming.
