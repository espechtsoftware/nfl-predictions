# Preregistration: study 48e, a winner-likeness gate at generation (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator (10-07), verbatim:** "How about trying using this neo4j 'looks like a winner' process at the start of
  the process -- before a lineup is added to the corpus it needs to appear winner like? I think that would be a good
  next test today".
- **What came before:**
  - **Study 48 (Addendum 152) PASS:** within his book, the more winner-like rows finish better at equal projection
    (+0.082 [+0.029, +0.134]).
  - **Study 48b (Addendum 153) NO DIFFERENCE:** re-dealing the same rows by the score does not help.
  - **Study 48d (Addendum 154) NO DIFFERENCE, leaning positive:** choosing 26 of the 41 built rows by the score moved
    P(≥ 1 big) +0.021 [−0.015, +0.060], at a cost of 1.7 projected points per row. The swapped-in spares are built
    after the book, from what the caps leave.
- **The real-field evidence, which counts against the score** (the laptop, 10-07, descriptive; the frozen score with
  point-in-time inputs, on the FULL real Millionaire fields of Weeks 2–4, about 160–172k entrants and 1,600–1,700
  top-1% lineups a week):
  - On the whole field the score flags the worst lineups: at equal projection the AUC for the top 1% is .548, .546 and
    .590, and the lowest score fifth wins less (.57% vs 1.07% for the highest fifth, in Week 2).
  - **Among the high-projection lineups, where ours live, it does not find winners.** In the top 20% by projection the
    AUC is .492, .538 and .391. In Week 4 the most winner-like fifth was the worst (.14% against .56%).
  - Its parts are unstable week to week. The structure part's AUC is .447, .774 and .520; the player-fact part's .596,
    .444 and .477.
  - The laptop's earlier check on his own Week 3 and Week 4 books agrees (partial −0.10 and −0.02).
  - The outside reviewer weighs this most. The harness's "winners" are top-1% rows of SAMPLED fields, so the score may
    partly learn the sampler's habits.
- **What the gate changes.** It acts while the book is built. Each row the solver proposes is scored. A row below the
  bar is set aside, and the solver proposes another for the same slot that shares at most 4 players with it, up to 10
  tries. Every try is still the solver's best row under the caps and the rows already committed. So the gate should
  cost less projection than 48d's selection, and it acts only where the book's own rows fall below the bar.
- **The prior, stated before any outcome:**
  - The binding census (§6) shows the gate acts on every slate at a small projection price. GATE re-peeks 71% of first tries and replaces about 6 of 26 book rows
    with a fallback, at −0.33 projected points per row (48d's selection cost −1.72). It also raises predicted
    ownership by 2.2 points per row, higher on 81% of slate-banks: the gate re-chalks the book a little, as the
    outside reviewer warned.
  - The harness measures winner-likeness against sampled fields, and there study 48 passed. The real fields do not
    support it among lineups like ours.
  - So NO DIFFERENCE is the likeliest reading. A harness PASS would not settle the real-field question (§5).

## 2. Arms (`experiments/s48e_winner_gate.py`)
**The build.** On each slate-bank his live Week-5 book and production's 15 spares are built: 41 rows through one
state, with the winners' mix, limit 4, round-robin, QB cap 5, caps 13 / 6 and no term. It is built three ways:
- **LIVE** (reference): mix_fill's round-robin, called as study 48d calls it. On the smoke slate its 41 rows, scores and
  dealt ranks equal study 48d's exactly, and its 26 book rows equal study 48's book.
- **GATE**: the same round-robin with the gate on every peek:
  - the peeked row is scored;
  - at or above tau it is committed;
  - below tau it joins the banned lineups for the rest of THAT peek, so the next try shares at most 4 players with it
    (the book's own overlap rule), and the cell is re-solved on the same state, up to R = 10 tries;
  - if no try passes, the best-scoring try is committed (ties go to the earlier try), and the fallback is counted;
  - a cell whose first solve fails passes its quota to A1, exactly as today;
  - the 15 spares pass the same gate.
- **GATE_SOFT**: the same, with tau at the 25th percentile (the outside reviewer's "safer form").

**The score** is study 48's frozen walk-forward model (`s48_winner_like.py` `c22d2811…`, imported and sha-asserted;
training table `66272167…`), fitted per scored slate on 2022 plus the 2023–24 slates strictly before it.

**tau**, per scored slate, is point-in-time. It is the q-quantile (numpy, linear) of that same model's scores on the
training top-1% rows of the slates before the scored one: q 0.50 for GATE, 0.25 for GATE_SOFT. The score is the
model's log-odds of a top-1% finish. So the bar reads: this row must look at least as likely to win as the typical
(GATE) or a lower-quartile (GATE_SOFT) past winner.

**Per arm and book row, recorded pre-lock and outcome-free:**
- the projection;
- the score;
- the predicted-ownership sum (the TABPFN pre-lock prediction in percent, the harness's analogue of production's FP
  projected ownership);
- the score's ownership-rank feature;
- the salary.

These answer the outside reviewer's question: does the gate re-chalk the book? In the all-53 model the ownership rank
is the largest coefficient (+0.198 per sd).

**Production's constraints** (caps 13 / 6, QB 5, the overlap limit 4) are asserted on every arm's 41 rows. Each arm's
41 rows are dealt by the head layout (study 1b's).

**Tested** (`tests/test_s48e_winner_gate.py`, 11 tests), on a scripted builder that offers each cell's rows in a fixed
order and never offers a banned lineup:
- with tau = −inf the gated fill IS mix_fill's round-robin: the rows, cells, spares, quota passes, the builder's final
  state and the sequence of solves;
- a rejected try is banned for its peek only;
- the first passing try is committed;
- with no pass, the best try is committed, ties going to the earlier;
- a gate that runs out of solvable tries commits the best so far, without passing the quota;
- the spares are gated;
- the constraint check;
- one row scores as in the batch, in any player order;
- the census is outcome-blind;
- the reader: its two decisions, its printed levels (0.975, 0.95 exploratory, guard one-sided 0.95), the verdicts and
  the study rule.

## 3. Endpoint and rule (study 18b's; the reader `scripts/s48e_report.py`)
- **TWO CO-PRIMARY DECISIONS.** GATE − LIVE and GATE_SOFT − LIVE both decide. The reviewer proposed the median gate,
  and the outside reviewer and the laptop the soft gate. By the operator's rule (when the agents disagree, test both),
  both decide, with a Bonferroni split.
- **PRIMARY, per decision:** P(≥ 1 big seat) per slate on the calibrated field v2, ARM − LIVE.
  - Two-sided 0.975 for each decision. B 20,000, seed 20261031; slates resampled within season.
  - Banks 1539–1544. The reviewer's unique-blob scan of both repositories found these numbers as banks or seeds only in
    study 48e's own plan and usage lines. That covers every blob in history up to 5 MB; the 8 larger blobs per
    repository were not searched.
- **Guards, per decision** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats
  ratio ≥ 0.80. **The guards gate a PASS only.**
- **Verdict, per decision:** DEAD LEVER (the arm dealt identically to LIVE on more than 80% of slate-banks) / WORSE /
  PASS / FAIL (guard) / NO DIFFERENCE.
- **STUDY:** PASS if either decision passes. If both pass, the candidate is GATE_SOFT, the smaller change. Otherwise
  the two per-decision verdicts stand.
- **EXPLORATORY** (two-sided 0.95): both arms on l02; each arm's levels, the gate's pass rate and fallbacks, projection,
  score, predicted ownership, ownership rank and salary.

## 4. Production's frozen threshold and parity (the laptop's questions, 10-07)
- **The model.** Live in 2026 every training slate is prior. So the walk-forward model IS study 48's all-53 model
  (`MODEL_all53.json` `41169d44…`), and the rows are the top-1% rows of all 53 slates (31,858).
- **The history feature.** Production scores a candidate with the player-history feature set to 0 (PORT_NOTES; its
  all-53 coefficient is −0.01). So the live threshold scores those rows the same way.
- **The frozen live threshold: GATE tau = −4.49767187489062**; GATE_SOFT −4.71933426819823. With the rows' own history,
  not for use: −4.5180 and −4.7415.
- **Source:** `scripts/s48e_live_tau.py`, which refits the model and asserts it equal to `MODEL_all53.json`. Its output
  is `results/s48e/LIVE_TAU.json`, sha256 `d1c8aaaa2b9202c69614ab8ced19deddc892105586aacb705ac0a33f0a4cd209` (lab
  `c59fa5b`).
- **Production pins it.** `FROZEN_GATE_TAU` in `nfl_dfs.inference.winner_like`. check_week_runtime fails a tau more
  than 1e-12 away from it, and so does any non-finite tau. The union refuses a different tau without
  `--winner-gate-tau-override`.
- **Parity.**
  - The fixture: `scripts/s48e_parity_fixture.py` (lab `0d43823`) runs production's configuration (all-53, history 0,
    the frozen tau, R 10, best fallback) on 2024 W10, bank 1406. It writes the PRIVATE
    `~/private/s48-port/PARITY_gate_2024w10.json`, sha256 `4138a5bb313a305f07e22e334f3048af1b57788c97b62fd9dcf1ef5e5382aa20`.
    It records 41 peeks (20 passing, 21 fallbacks) and 312 tries.
  - The result: production's gate (`production/winner-gate-20261007` @ `7467b8ce`, OFF) reproduces every try's score
    (worst difference 3.6e-15) and every pick (41 of 41).

## 5. What a verdict can do
- **A harness PASS is necessary, not sufficient.** Arming the gate for a live week also needs real-field support among
  top-projection lineups. Weeks 2–4 do not show it (§1).
  - So even on a PASS the gate is NOT armed for Week 5.
  - It becomes a candidate pending study 48f, the outside reviewer's real-field refit. 48f fits walk-forward on the real
    2026 fields and grades only on real fields from Week 5 on, prospectively, because Weeks 1–4's real outcomes have
    now been examined.
  - Arming would then need, by its deadline: production's gate (pinned, OFF) reviewed; a rehearsal; a study 38
    amendment before the lock; and his yes.
- **NO DIFFERENCE, WORSE or FAIL:** the gate stays OFF. The winner-likeness line rests on 48f's real-field answer.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path; run twice, the second time on the final code `0d43823`):
  - every arm built 41 rows within production's constraints;
  - LIVE equals study 48d's 41 rows, scores, projections and dealt ranks exactly, and its book equals study 48's;
  - the gate acted on one row there (that week's book scores above the bar: −3.78 against −4.43), and GATE_SOFT was
    identical to LIVE;
  - the second run changed no row, rank or score of the first, and added only the ownership, rank and salary fields;
  - the census and the reader exited 0. The reader printed its 2 headers, and its header names STUDY 48E (tested);
  - about 70 s per slate-bank for all three arms, alone.
- **The binding census** (outcome-blind; bank 1406; 36/36, code `0d43823` clean; `results/s48e/CENSUS_s48e_binding.txt`
  `7a642e37…`, raw `5ede3bf3…`; lab `3a114f6`):

  | | LIVE | GATE | GATE_SOFT |
  |---|---|---|---|
  | tau, mean (range) | — | −4.489 (−4.516 to −4.429) | −4.746 (−4.788 to −4.735) |
  | today's book rows at or above tau | — | 0.460 | 0.720 |
  | book rows passed (on the first try) | — | 0.762 (0.291) | 0.958 (0.518) |
  | fallbacks per book; solves per book | — | 6.19; 125 | 1.08; 68 |
  | spares passed | — | 0.381 | 0.739 |
  | projection per row (change) | 128.04 | 127.71 (−0.33) | 127.86 (−0.18) |
  | mean score (change) | −4.511 | −4.345 (+0.166) | −4.413 (+0.098) |
  | predicted ownership per row (change; share of slate-banks higher) | 78.56% | 80.72% (+2.15; 0.81) | 79.83% (+1.27; 0.75) |
  | ownership-rank feature; salary per row | 0.9387; 49,967 | 0.9427; 49,972 | 0.9413; 49,970 |
  | identical to LIVE | — | 0.000 | 0.056 |

  No quota passed to A1 and no row was dropped in any arm. About 180 s per slate-bank for the three arms at 16 workers.
- **Code:** nfl2 `production/s48e-winner-gate-20261007` @ `0d43823` (the census at `3a114f6`):
  - `experiments/s48e_winner_gate.py`, sha256 `55b39bfc425484071c0ead7287dabc99c9397a0620c3f392e094ec554d6fa2f5`;
  - `experiments/s48_winner_like.py` (study 48's, frozen), `c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c`;
  - `scripts/s48e_drive.py`, `520413fde4ceeb42a194b0db4d4b84c433cfa67e282a41dd3cd0b8efca8cba8b`;
  - **`scripts/s48e_report.py` (the reader), sha256 `c4c92c18032da02281887cef2fe23a7bd788c953973f8bd7a415ad4b8a7e8f9b`**;
  - `scripts/s48e_census.py`, `49eddd0bfac0158fb1e5fd7117c67fb641eb78fe22a0469228e237f9f575aca5`;
  - `scripts/s48e_live_tau.py`, `be8e846e05e2507e10fe4c754c4788aa5674bb67a2c65a906610cd96dc865836`;
  - `scripts/s48e_parity_fixture.py`, `da5a8950d29dfae1a4f159833da7674c9e9a438adafd91f2c0c84fecf4f873ac`;
  - `tests/test_s48e_winner_gate.py`, `52227e02e7d899d9477ffc3c90285b386803dc1e32a60c1126ff64a7a46a1f99` (11 tests);
  - `experiments/mix_fill.py` `dcf6a299…` and `experiments/l02b_field_sampler.py` `fadf9cfe…`, unchanged.
- **Order:** this freeze → the laptop's ack and bank scan → the scored run → the confirmatory census, committed before
  the read → the read → the laptop's re-run → the LEDGER row and an Addendum.
- **Disclosed:** before this freeze, and with no outcome seen, the design gained the ownership, rank and salary records
  and the second decision (GATE_SOFT), at the outside reviewer's request relayed by the laptop. The census was re-run on
  the final code.
