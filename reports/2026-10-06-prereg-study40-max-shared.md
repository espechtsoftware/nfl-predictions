# Preregistration: study 40, fewer shared players between rows on his live book (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop scans the banks, acks the census and re-runs the frozen reader.

## 1. Why
- **The outside review (10-06)** screened seven one-setting levers on a fixed-book replay of Weeks 2–4 against the REAL
  Millionaire fields (`reports/2026-10-06-fixed-book-lever-screen-w2-w4.md`; production `union_reselect.py`, the armed
  Week-5 settings, one argument changed per arm). `--mean-max-shared 5` (every union row shares at most 5 of 9 players
  with every earlier row; the live value is 7) read ahead on P(≥ 1 big seat) in two of three weeks:

  | Week (projections) | live 7 | 5 shared |
  |---|---|---|
  | W2 (ours) | .931 | .908 |
  | W3 (ours) | .009 | .310 |
  | W4 (FP) | .034 | .343 |

  Its guards held over the three weeks (mean entry pct +.014; expected big seats ratio 1.24). Its mechanism is the
  published one for top-heavy contests: an upper bound on the overlap with earlier entries (Hunter, Vielma and Zaman
  2016). The screen calls itself a candidate, never a verdict: three weeks, two on projections no longer played, seven
  arms screened together.
- **The prior record, stated before any outcome of this study:**
  - Studies 36 and 37 (exposure caps and the regulars' player curve) spread the book and read NO DIFFERENCE, leaning
    worse, under our ratings. The overlap limit is a different lever: the best players can still fill half the book (the
    13-row cap), while every pair of rows must differ in at least four players.
  - The lab's August overlap caps were null to negative on a different objective and population: 008 (γ5 −1.12 on a
    240-candidate K=1 bank, the weekly maximum) and 044 (cap-4 prefix, null). Neither tested P(≥ 1 big seat) on the
    26-row winners' mix.
- **Why now:** the operator, 10-06: "Please next proceed with anything you feel has a chance of helping" and "I want to
  exhaust all reasonable options". The production switch exists (`UNION_MEAN_MAX_SHARED`, default 7; production
  `production/union-max-shared-env-20261006` @ `3c3449dd`, reviewed), so a verdict can be acted on.

## 2. Arms (study 39's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- Every arm: the winners' mix (study 28's `mix_book`, unchanged), the QB cap of 5 rows, production's player / DST caps
  13 / 6, and **his live objective: the mean with NO ownership term**. The arms differ ONLY in the overlap limit: study
  18's `MAX_SHARED`, which the cap builder reads at every solve (book rows and spares alike, as production's
  `--mean-max-shared`), set for the arm's build and restored. Every built row is checked against the limit; a breach
  stops the slate-bank.
- **MIXT_QA0** (reference): his live book, at most 7 shared.
- **MIXT_MS5** (DECISION): at most 5 shared.
- **MIXT_MS6** (exploratory): at most 6 shared.

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `fe49d7a` clean; `results/s40/CENSUS_s40_binding.txt` `13d79acb…`, raw `1dd1fe4f…`)

| | shared players per pair of book rows (max) | pairs sharing 6+ / 7 | QBs | games | distinct players | projection per dealt lineup vs MIXT_QA0 |
|---|---|---|---|---|---|---|
| MIXT_QA0 (reference) | 2.87 (7) | 9.9% / 3.6% | 6.94 | 8.97 | 27.6 | — |
| **MIXT_MS5 (DECISION)** | **2.75 (5)** | **0 / 0** | 7.75 | 9.19 | 30.3 | **−0.04** |
| MIXT_MS6 | 2.82 (6) | 7.6% / 0 | 7.44 | 9.14 | 28.6 | −0.03 |

- It ASSERTS on every row a 26-row book, production's caps, the QB cap 5, no ownership term, and each book's limit.
- No short books; no arm is identical to the reference on any slate-bank.
- The limit binds on the tenth of the live book's row pairs that share 6–7 players, at a paper cost of 0.04 projected
  points per lineup; it adds about one QB and three distinct players.

## 4. Endpoint and rule (study 18b's, as studies 35–39)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_MS5 − MIXT_QA0. Banks 1479–1484: the reviewer's unique-blob scan of
  both repos (15:57) is clean (production: none; the lab: study 40's own usage lines, and a sha that begins 1480 after
  `bank":1010`); the laptop's scan comes with its ack, before the scored run. B 20,000, seed 20261021; two-sided 0.95.
- **Guards:** guard 1, mean entry pct, one-sided lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
- **The guards gate a PASS only.** A primary interval that spans 0 reads NO DIFFERENCE whatever the guards show; both
  guards are printed either way.
- **Verdicts:** DEAD LEVER / WORSE / PASS / FAIL (guard) / NO DIFFERENCE.
- **EXPLORATORY:** MIXT_MS6 − MIXT_QA0; per arm, the shared players per pair of book rows, the QBs, the games covered and
  the dealt projection.

## 5. What a verdict can do
- **PASS:** the 5 becomes a candidate for his book, offered with its evidence and its projection cost. The switch is
  reviewed; it needs Friday's rehearsal at 5 before it touches an entry. Entering it is his call. Note: a live 5 makes
  study 38's frozen paper weeks INVALID (its parity requires the live 7), so a W5 adoption needs study 38 amended before
  the W5 lock (legitimate then: no W5 outcome exists), or study 38 loses those weeks.
- **NO DIFFERENCE:** his taste, told plainly what it costs on paper; the outside screen's real-field weeks stay the
  case for it, with the harness unable to confirm.
- **WORSE or FAIL:** his book stays at 7.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): every arm built 40 rows (26 book + 14 spares), each book's largest
  pairwise overlap equals its limit (7 / 5 / 6); the census and the reader exited 0; the reader printed its 2 headers and
  its header names STUDY 40 (tested).
- **Code:** nfl2 `production/s40-max-shared-20261006` @ `fe49d7a` (the census at `dd2868c`):
  - `experiments/s40_max_shared.py`, sha256 `aa4ee82035a5c80ed88a269bd9fd513ce64bb10e49249a8e9107be71e48e74bd`;
  - `scripts/s40_drive.py`, `7c368f05e6d6b9fe7a4638239fc02f15d786a02441a0f9bb82f46bb17a1c4a1e`;
  - **`scripts/s40_report.py` (the reader), sha256 `4bf0079d7bde59ba4b2ac4657e5bf4d42c54cdb42935b0acd3350842f2150b50`**;
  - `scripts/s40_census.py`, `efcef54db3c3b9235f6bb6aecad0b28e3fd813489730cecfe0d37fcc1720cbef`;
  - `tests/test_s40_max_shared.py`, `354f2254bb201cceee28f75ecd06d126fdeaa03499f155cc9424ae65aad80717` (7 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field; the
  outside screen is the real-field complement (three 2026 weeks).
