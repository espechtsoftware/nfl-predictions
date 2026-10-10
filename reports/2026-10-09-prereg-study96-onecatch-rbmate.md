# Preregistration: study 96, the QB's own RB as a stack mate (RBMATE4) together with one receiver per team (ONECATCH), on his armed Week-5 book, in the harness — his Week-5 decision (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (19:19 CDT)** by the outside reviewer; code done, the smoke waiting for the first gap after study 95's
run. The reviewer reviews, runs the binding census and FREEZES; the laptop acks. **This read decides Week 5 by his rule.**
- **Banks and seed:** **3112–3123** (set A 3112–3117, set B 3118–3123; sims bases 3162–3173, fields 3812–3823), seed 20261141 —
  the laptop's full-set check is clean against 698 used banks, study 95's included; its text-scan tally follows.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his decision
- **Study 94** (Addendum 192, lab READ `67b312a4`): RBMATE4 — the QB + one pass catcher + HIS OWN RB on the first 4 C-cell
  rows — **+2.0** [−1.0, +4.9], better on both draws (A +1.7, B +2.4), expected big seats ×1.028; the gain all 2023 (+4.4; 2024
  −0.4). **It was read WITHOUT ONECATCH**, which is now armed for Week 5 (the arm `ee92d15b`).
- **The operator, 10-09, in the laptop's session (HANDOFF `ad00da5c`):** **"Try live W5 if built"** — the option text: "New code
  tonight, plus a test of it together with one receiver per team and the same checks as before. It goes live at Saturday's
  10:28 arming only if all pass, otherwise paper. It would be the fourth change this week."
- **This study is that test:** the two rules together, against his armed book.
- **The prior:** NO DIFFERENCE (the realized QB–RB1 correlation is weak, .082, Addendum 27; study 94's lean is one read, all
  2023). **The transfer caveat:** the harness builds on the simulator's means, not Fantasy Points'; the laptop's outcome-blind
  Week-4 check of the production flag reports what it does to his real book (the laptop's count: it binds on 3 of the first 4 C
  rows).

## 2. Arms (`experiments/s96_onecatch_rbmate.py`)
**Study 94's harness exactly** (its frozen module `s94_rb_pairs.py` `2eb7835b…`, sha-asserted; `run()` = 94's `run()` with six
listed edits, a test asserts it). Both arms: the player cap 0.35, the ownership cap + 15 (89's `own_caps`), at most one TE and
one player predicted < 3% per row (6p's row rules), the QB cap 5, the DST cap 6, the overlap limit 4, the cheap +2 block, 15
spares, Rev6, his live cell quotas.
- **ONECATCH** — his armed Week-5 book: study 93's `lead_rules(0, True, 0, …)` inside `own_caps`. **The same call as study 95's
  LIVE** (a test asserts the text; the census compares the rows and the dealing with study 95's smoke on bank 1406).
- **ONECATCH_RBMATE4** — `combo_rules`: ONECATCH on every B / C book solve AND, on the first 4 C-cell book solves (a slot is taken
  at the solve, ruled or dropped, as 94; an ownership-cap re-solve takes another), 94's interaction floor over (QB, RB of the
  QB's team) pairs, weight 1, floor 1. **ONE optimize call per solve. Tiers: [row + oc] + floor → [row + oc] (the floor dropped)
  → [row] (ONECATCH dropped) → none (6p's fallback)**, all inside the ownership cap; every tier recorded by name. With no slot
  open it is call-for-call study 93's ONECATCH (a test asserts it).
- **Production:** `union_reselect --mix-rb-mate-c 4` (review/rb-mate-c-20261009 @ `4caff46d`, the outside reviewer's), parity
  against `combo_rules` and 94's `rb_pairs` byte for byte (text shas `66ed0eff…` / `5e961923…`).

## 3. The read (the reader `scripts/s96_report.py`)
- 2023–24 (36 slates); twelve banks as two disjoint draws (the same past slates, two random sets of opponents) and pooled;
  study 63's frozen statistics (a test asserts them); two-sided 0.95, B 20,000; the guards gate a PASS only.
- **DECISION: ONECATCH_RBMATE4 − ONECATCH** on P(≥ 1 big seat) per slate.
- **HIS WEEK-5 RULE, printed as one line:** **GO LIVE in W5 iff the point is > 0 on BOTH draws AND the pooled expected big seats
  ratio ≥ 0.80; otherwise PAPER ONLY.** Guard 1 printed beside it, outside his rule. Under no true effect it passes about one time
  in four to one in three (the draws share slates and outcomes).
- **Plainly:** study 94 read RBMATE4 on these 36 slates already (other banks); a second pass on the same slates is not
  independent of the first. The real-week paper arm (study 38 amendment 6u: his book without it, paired) is the check.

## 4. What the harness can and cannot say
- The census reports: the RBMATE slots used vs floors ruled vs floors dropped (a dropped floor is a used slot without the pair),
  ONECATCH ruled / dropped per arm, the QB + own-RB rows per arm, the (QB, own RB) pairs in the pool, the rows shared with /
  dealt identical to ONECATCH, and ONECATCH against study 95's LIVE (rows and dealing).
- A Week-5 GO LIVE also needs every production check: the laptop's Week-4 real-book check, its wiring, study 38 6u's smoke.

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke: the unit tests, the mechanics smoke (2023 W3, 2023 W11,
  2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The smoke:** (the first gap after study 95's run; filled in when it ends).
- **Code:** nfl2 `production/s96-onecatch-rbmate-20261009` @ `3cf3e8eb` (branched from study 95's census `65c2407c`):
  `experiments/s96_onecatch_rbmate.py` `0363a84f…` (pins s94 `2eb7835b…`; `combo_rules` text `66ed0eff…`); `scripts/s96_drive.py`
  `ef706189…`; `scripts/s96_census.py` `f9c9e7c7…`; **`scripts/s96_report.py` (the reader) `a7cdf787…`** (seed 20261141);
  `tests/test_s96_onecatch_rbmate.py` `a9e53ab9…` (12).
