# Preregistration: study 45, a contrarian insurance row (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
The laptop acks the census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06), verbatim:** "This last week, I believe a contrarian play is what won ... Look at what
  contrarian plays have won over the last three weeks. And let's consider you know, a one-off lineup a week or two where
  we do something like that." On the laptop's proposed rule: "Yes, let's try what you described." Test first; Week 5 if
  it reads well by Thursday.
- **The descriptive read** (the laptop, the real W1–4 Millionaires; aggregates): the WINNING lineup was less owned than
  the field in 3 of 4 weeks (ownership sums about 64–101% against the field's 110–117%), each time with three players
  under 5% owned; the recurring route was a low-owned QB and his stack. **But the broad top 1% and top 100 were CHALKIER
  than the field in W1–3** (124–133% against 112–117%); only in W4 was the top less chalky. Contrarian value shows at the
  very top (the single winner), not across the top 1%.
- **Where the row goes** (Rev3 under head): ranks 23–26 carry only the $20 supersats, so an insurance row there could
  never win a big seat. Ranks 1–22 each carry exactly one big entry (ranks 1–2 also the Millionaire). The row replaces
  **rank 22**, whose big entry is ONE single-seat satellite (89 entries; plus a $20 supersat). Its value is that
  satellite's seat chance.
- **The prior, stated before any outcome:** one row moves the book's P(≥ 1 big seat) by at most a point or two, below
  this panel's resolution, so the primary is the replaced position's own seat chance. A contrarian row gives up
  projection (about 1.3 points at rank 22) for a different outcome profile; whether that raises its chance of winning a
  single-seat contest is open.

## 2. Arms (study 43's harness: realized 2023–24 outcomes, 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`)
- His LIVE Week-5 book (the winners' mix, the overlap limit 4, the round-robin fill, the QB cap of 5 rows, caps 13 / 6,
  the mean with NO ownership term) is built once per slate-bank; the arms swap CONTRARIAN rows into fixed book ranks.
- **The contrarian row:** the best-projected lineup (the same mean) under A1's or B's stack rules (the better) whose QB
  is NOT among the slate's 8 most-owned QBs, with at least 3 skill players NOT among the slate's 40 most-owned skill
  players, and the 8 skill players' predicted ownership summing to at most **0.70 × the live book's mean**; within
  production's caps (13 / 6, the QB cap 5) and the overlap limit 4 against the remaining book rows; distinct from every
  built row. A rank whose row is infeasible keeps its live row (recorded).
- **The rule is by rank and ratio, never absolute percent.** The harness's pre-lock ownership prediction (TABPFN_LS, the
  0.20 term's source in studies 31–37) ranks players like the real ownership (correlation .82–.91) but is compressed (its
  top players 13–18% against a real 25–40%), so "under 5%" would not mean the same thing. Live, the same rule reads FP's
  projected ownership, for this row only. The "at least 3 low-owned" part binds little (the live rows already hold about
  4 players outside the 40 most-owned); the QB and the ownership-sum parts bind.
- **MIXT_LIVE** (reference). **MIXT_CON1** (DECISION): rank 22. **MIXT_CON2** (exploratory): ranks 21–22 (two rows, the
  second distinct from and within the limit of the first). **MIXT_CON1_R3** (exploratory): rank 3 (two big entries) --
  does the placement matter?

## 3. The binding census (outcome-blind; bank 1406; 36/36, code `06849be` clean; `results/s45/CENSUS_s45_binding.txt` `df995d96…`, raw `df47c4e3…`)

| | rows feasible | projection vs the replaced | predicted skill ownership vs the replaced (cap) | QB ownership rank | dealt projection vs LIVE |
|---|---|---|---|---|---|
| **MIXT_CON1 (rank 22)** | 100% | **123.80 vs 125.07 (−1.27)** | 51.6% vs 71.7% (55.0%) | 13.6 | −0.05 |
| MIXT_CON2 (ranks 21–22) | 100% | 124.37 vs 125.40 (−1.04) | 51.2% vs 73.5% | 13.7 | −0.08 |
| MIXT_CON1_R3 (rank 3) | 100% | 126.74 vs 131.22 (−4.48) | 53.1% vs 83.6% | 13.8 | −0.25 |

- It ASSERTS his live settings, the caps, the rule and every book within the limit 4. Shapes: mostly B (QB + 1). No arm is
  identical to the reference on any slate-bank.

## 4. Endpoint and rule
- **PRIMARY:** the replaced position's big-seat chance -- per slate (the mean over its banks), the sum over the big
  contests its rank is dealt to of P(≥ 1 seat in that contest) (the harness's `contest_p`), MIXT_CON1 − MIXT_LIVE.
  Banks 1503–1508 (scanned clean by the reviewer: production's hits are numbers such as 0.1505 beside bank 590, the lab's
  study 45's own usage lines; disk none; and by the laptop, with its ack); B 20,000, seed 20261025; two-sided 0.95.
  The book's P(≥ 1 big seat) is printed beside it with its interval.
- **Guards:** guard 1, the mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdicts:** DEAD LEVER / WORSE / PASS (lower > 0, at most one season negative, both guards) / FAIL (guard) / NO
  DIFFERENCE.
- **EXPLORATORY:** MIXT_CON2 and MIXT_CON1_R3, each on its positions' chance and on the book's P(≥ 1 big).

## 5. What a verdict can do
- **PASS:** a Week-5 candidate if it reads by Thursday and he says yes: production builds the row from FP's projected
  ownership (for this row only) by the same rank/ratio rule, parity-pinned to this harness, rehearsed Friday.
- **NO DIFFERENCE:** his taste: the row costs about 1.3 projected points at one satellite entry; he may still enter it
  as insurance, told that.
- **WORSE or FAIL:** the live row stays.

## 6. Smoke and integrity
- **The smoke** (2023 W1, 1406, the full path): every arm swapped its ranks (contrarian rows feasible: the QB the 13th
  most-owned, the skill ownership at the cap against 55% for the replaced row); the census and the reader exited 0; the
  reader printed its 2 headers and names STUDY 45 (tested). Before the census, the first rule (absolute percent: QB < 5%,
  skill sum ≤ 75%) did not bind on the harness's compressed predictions (the replaced row sat at 55%), so the rule was
  restated by rank and ratio (`06849be`); disclosed.
- **Code:** nfl2 `production/s45-contrarian-20261006` @ `06849be` (the census at `b50bb5a`; the manifest's fix at
  `a962eaa`):
  - `experiments/s45_contrarian.py`, sha256 `42cbbd3cb1158b5f4eef4de15e150b09ca6a75a15d5ae6aace61b9525fcb701d`;
  - `experiments/mix_fill.py` (study 42's), `dcf6a29997d97369f467377ceb5a69a0ba3bc0edc51fe0c8ec495610a8436fd7`;
  - `scripts/s45_drive.py`, `cc53690a0e9f37631fd6a56c766da2ebaa7ffd472e7fd06c668c52af5f01fd51`;
  - **`scripts/s45_report.py` (the reader), sha256 `ca403fb000b272352e6a23cf04eb505f49cacdc5f6ee730b07ac9e75bee43994`**;
  - `scripts/s45_census.py`, `42ba6b6ea4637f8e8c90689ee1de72f21ff82a000746033fe3895354fc9321f6`;
  - `tests/test_s45_contrarian.py`, `4cc1245158259b1be12ca79d8bbc021f83ab62408f2d4996125cd4ed17ffed05` (5 tests).
- **Order:** this freeze → the laptop's ack → the scored run → the confirmatory census, committed before the read → the
  read → the laptop's re-run → the LEDGER row and an Addendum.
- **Transfer, said plainly:** our projections (the live book uses FP's); the harness's ownership prediction stands in for
  FP's; and the field is sampled from the real ownership with 70% one-slot stacks, whose top end is 3–6 points easier
  than the real fields' (the field audit) and whose top-end chalk is not calibrated to the real top 1% (124–133%). A
  contrarian row's value depends on exactly that, so a harness verdict here transfers less surely than the construction
  levers'.
