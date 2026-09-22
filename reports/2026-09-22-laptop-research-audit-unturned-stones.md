# Research audit: what has been proposed, what was never run, and where the
# remaining scoring upside plausibly is

Laptop agent, 2026-09-22, at the operator's request: audit both repositories for research
done, experiments proposed but never run, and promising findings never converted — "no
stone unturned regarding ways to improve scoring."

Sources: 949 reports and the 120-addendum system study in `nfl-predictions`; 78 frozen
preregistrations, `LEDGER.md` (65 rows), and the August idea memos in `nfl2`. Everything
below is cited to a file so it can be checked rather than believed.

**One framing note before the list.** The ledger's own conclusion is that *points is the
wrong axis* — no lever moves the book more than ~2 points, dose moves the pool ~8, and a
points-optimal book sits 36–49 below the Millionaire winner. So I have sorted by expected
value against **finish and money**, not by points.

---

## A. The systemic finding: the adopted-stack guard cannot see the money path

`CLAUDE.md` states the adopted stack is documented where it is implemented, guarded by
`src/nfl_dfs/research/config_manifest.py`, "which must show zero discrepancies".

**That manifest inspects six `nfl_dfs` modules and contains the string `nfl2` exactly zero
times.** It reads *this* repository's live code. The money path is `nfl2/scripts/live_week.py`.

That is precisely how the chalk fade — an adopted, twice-proven lever — sat at **zero for
every live week of 2026** without any gate noticing: `production_policy.py:247` sets
`OWN_MODEL: ""` (naive fade), and nfl2's caller never passes `own_est`, so the degraded
branch ran unconditionally. The manifest said zero discrepancies the whole time, correctly,
because the disagreement is on the other side of a repository boundary it does not cross.

**Recommendation (highest structural value, cheap).** A cross-repo consumption audit: for
each lever in the adopted policy, assert that the nfl2 money path actually consumes it, and
fail closed when one is declared-but-ignored. The chalk fade is one instance; nothing
currently rules out others. This is a test, not a model change, and it protects every
future adoption rather than one.

---

## B. The one named modelling lever, drafted and never signed

**Tail calibration (would become PREREG-101).**
`reports/2026-09-16-prereg-tail-calibration-DRAFT.md`, explained for the operator in
`reports/2026-09-18-tail-calibration-what-you-are-approving.md` — *"nothing has been signed,
frozen or run."* The current handover says **do not launch**.

Why it is the last one standing, in the project's own words: the simulator claims the best
lineup in the entered book breaks 220 about **9%** of the time; the true rate is about
**3%**. The pool is 1.6x too optimistic, the *selected book* 2.8x — selection amplifies the
error, because the lineups that look best lean hardest on the scenarios the simulator
handles worst. Nine ordering approaches have been tested and closed; this one does not
re-rank, it reweights the worlds.

**Status: blocked on three operator questions, not on evidence or compute.** If there is one
stone to turn, this is it, and it is waiting on a signature.

---

## C. Fourteen frozen preregistrations with no ledger row

`LEDGER.md` has 65 rows against 78 frozen PREREG documents. These were designed, frozen, and
never concluded:

| prereg | subject |
|---|---|
| 040 | calibrated-marginal law as an additional selection critic |
| 042 | external proposer supply into the union |
| 043 | participation/eligibility law (audit P1) |
| 051 | **winner-shape supply: relaxed stack topology at fixed compute** |
| 061 | KG-5 same-pool hybrid reranker (design stage) |
| 062 | candidate-level feature→outcome association sweep (CFOS) |
| 069 | prop-covered lineup admission — strict arm INFEASIBLE, closed |
| 071 | JPAR-1 participation-conditioned coherent hsim critic — r1/R2/R3 VOID |
| 072 | CP-1 prop + transfer-recipient + projection-fill universe (DRAFT) |
| 073 | JPAR-1b on the shared sealed pool (PROPOSED, awaiting production review) |
| 074 | CP-3 tail-regime diversification in a frozen top-2,000 frame (DRAFT) |
| 075 | CP-4 contextual game-core allocation (DRAFT) |
| 076 | CP-1 fresh-judge retrieval crossing |
| 077 | prospective 2026 evaluation of the nominated UNION_EMAX retrieval law |

Several are genuinely dead (069 infeasible, 071 void). But **051, 062, 074 and 077 are not
recorded as closed anywhere I can find**, and 073 is explicitly *awaiting production
review* — a cohort the lab proposed and no one ever answered. With the lab agent gone, these
have no owner at all.

**Recommendation.** Half an hour triaging these into *dead / superseded / still worth
running* would either free them or stop them from being re-derived a third time. **051
(winner-shape supply at fixed compute)** is the one I would look at first: the standing
diagnosis is that the corpus usually contains the winner's *players* but almost never the
winner's *roster*, and 051 attacks roster shape rather than player supply.

---

## D. Ranked next steps that were published and then not done

From `reports/2026-09-16-findings-since-week1-synthesis.md` §4:

**D1. Questionable-exposure cap (step 4) — never preregistered.** PREREG-100 found
`Q_dnp −5.9` and `Q_limited −2.9` residual, zero rates 47%/25%. The follow-up was named and
never written.

**My Week-1/2 cohort work today sharpens this rather than contradicting it**
(`2026-09-22-laptop-doubtful-verification.md`): *Questionable as a whole* is the best-value
cohort on the board — 124 player-weeks, **77.4% played**, **1.274 PPR per $1k against 1.003**
for unflagged players. So a blanket Q cap would destroy value. The cap has to target
**Q_dnp / Q_limited specifically** — the ones who don't play or play limited — which is
exactly what PREREG-100 said and is *not* what "Questionable-exposure cap" sounds like.
Worth writing down before someone implements the wrong rule.

**D2. Cash-game / double-up shadow (step 6) — never measured, and I would rank it first.**
The system's measured strength is its **calibrated mean**: 61% of entries above the
Millionaire median, 25% above the cash line. Every lever in the ledger has been an attempt
to win a tournament tail the simulator demonstrably models badly (see §B: 9% claimed vs 3%
actual at 220). A double-up/cash shadow plays to the part that is *already calibrated*
instead of the part that is broken.

It was proposed as "measure on paper for two weeks before money" and, as far as I can find,
**no such shadow was ever built or measured**. Against Week 1 (~$400 in, ~$140 back) and
Week 2 ($245 in, $26 back), a strategy targeting the 25%-above-cash-line property deserves
two weeks of paper before another tournament lever does.

**D3. Tail calibration (step 3)** — see §B.

---

## E. August idea memos: mechanisms proposed, never converted

`nfl2/LAST-CHANCE-LINEUP-SCORE-IDEAS-2026-08-28.md` (844 lines) and
`LINEUP-SCORE-IMPROVEMENT-RESEARCH-2026-08-28.md` (602 lines) contain a ranked programme.
Cross-referencing against `LEDGER.md`, these have no corresponding cohort:

1. **Tail-driver credibility audit** (outcome-free): for each simulated 220/230 event, ask
   whether the one or two players driving it have a plausible route/target/red-zone/SIS
   opportunity path. Explicitly designed as outcome-blind, so it is cheap and safe, and it
   is diagnostic for §B — it would say *which* worlds the simulator is wrong about.
2. **Externally anchored tickets**: a small fixed budget-neutral sleeve forcing one
   plausible ceiling anchor into a solve, letting the simulator build the other eight slots.
3. **Residual-world column arm**: prices the next lineup against the current book rather
   than re-ranking a fixed pool. Memo says the score-free core exists and the
   current-source adapter does not.
4. **Tail-story cluster columns + quality-diversity archive**: optimise across a coherent
   cluster of related worlds instead of one noisy world. (`QD_CELLS` is `0` in the adopted
   policy — built, off.)
5. **Within-slate adaptive solve allocator**: spend candidate work on whichever generator is
   producing new portfolio value *on that slate*.
6. **Minimum-edit high-score path** (P0 diagnostic): exact roster edit distance from the
   book to the week's winner, with salary and legality recomputed. Cheap, and it answers
   "supply or retrieval?" directly — the question the whole programme turns on.
7. **Boom-world visit stratification across games** — `EXPERIMENT_REVIEW_SUGGESTIONS.md`
   records experiment 014 at **+2.62**, one of the largest single numbers in the corpus.

Item 6 and item 1 are both **outcome-free diagnostics** — they cannot contaminate a gate and
they do not need a money-path change. They are the cheapest unturned stones here.

---

## F. Data gaps that cap what any model can do

From README *Known gaps* plus my own measurements today:

- **`contest_entries` has never received a row.** Only `contest_ownership` is populated. DK
  purges standings after ~4 days, so historical field rosters are unrecoverable. This is the
  only path to a measured field model — and the finish objective (§B, PREREG-098) is
  precisely what needs one. **The September standings downloads are load-bearing and the
  capture path is still unexercised against a real settled contest.**
- **`contest_entries.payout` is NULL on all 1,305,992 rows**, so **no ROI can be computed
  from the warehouse at all**. Dollars come from the operator's export by hand. For a
  programme that has now reframed itself around money rather than points, that is the
  measurement layer being absent.
- **`contest_ownership` Week-2 coverage is much thinner than Week 1** — 471 distinct names
  against 675 (measured today). 61 of 429 Week-2 frame players have no row and score 0 by
  default in any realized-points analysis. Week 1 was 7 of 391. Any cross-week comparison
  scored this way is not symmetric between weeks.
- **`tabpfn_projections` holds only week 3 for 2026** — weeks 1 and 2 were destroyed by the
  truncate-and-rewrite of the bad early run and have not been rebuilt.
- 2022–2024 DK salary gap (three seasons with null salary features).

---

## G. Built, not wired

Capability that exists and is not in any live path: archetype clustering (CLI-only, no
scheduled refresh, graph-derived inputs deferred); overlay detection (`dk_contest_fills`
scaffold, never validated against a live slate's approach to lock); showdown Captain Mode
(no backtest at all); the exploration sleeve (three reproduced fail-open paths, parked,
research-only); and the `user-supplied lineup analyzer` requested 2026-08-08.

None of these is a scoring lever today. The overlay detector is the one with a money story —
finding an overlaid contest is worth more than a 2-point lineup improvement — and it is
scaffold-only because nobody has watched one slate's fills by hand.

---

## H. What I would actually do, in order

1. **Get PREREG-101 signed or explicitly killed.** It is the only named modelling lever
   left, it is written, and it is waiting on three questions. Ambiguity is costing more than
   either answer would.
2. **Build the cross-repo lever-consumption test (§A).** Cheap, and the chalk fade proves
   the failure mode is real and silent.
3. **Run the two outcome-free diagnostics (§E.1, §E.6).** They cannot contaminate anything,
   they need no money-path change, and they answer *supply vs retrieval*, which decides
   whether §C.051 or §E.3 is the right next mechanism.
4. **Measure the cash/double-up shadow on paper (§D2).** It plays to the one property that
   is already calibrated.
5. **Triage the fourteen orphaned preregistrations (§C).** They have had no owner since the
   lab closed.
6. **Fix the money measurement (§F).** A programme steering on finish and dollars cannot
   compute ROI from its own warehouse.

## Caveats

I have read 949 report filenames, not 949 reports. Where I assert "never run" I mean no
ledger row and no report I could find; several early addenda were **RETRACTED by later
audits**, so any item here should be re-checked against the last fifteen addenda and the
lab ledger before anyone acts on it. Corrections welcome and expected — particularly from
production, which has context on the August programme that I do not.
