# Follow-up: PREREG-L05 draft and the Week-3 head layout

**2026-09-24, afternoon.** This is a review of what the team did with `reports/2026-09-24-corpus-selection-sorting-research.md`. It
is based on HANDOFF through `a5d2d857` and the PREREG-L05 draft at nfl2 `be9588a`. One item is time-sensitive: it concerns
L05's reading table, which should change **before tonight's freeze**. The replay script is
`reports/lab-handoffs/2026-09-24-corpus-selection-sorting/head_replay.py`.

## 1. PREREG-L05: the design matches the spec; cell D needs changing before the freeze

The arms, labels, oracle arm, primary, support census and relaxed-stack judgement are what the review proposed. The
determinism fix to the sets builder (`651aedae`) is a real catch.

**The problem is cell D.** When neither arm is flip-eligible, cell D reads "the sleeve does nothing measurable, even with
perfect labels" and closes the chalk-core sleeve for 2026. But "not flip-eligible" means "not shown", not "absent", and
this panel has little power at the effect size we expect.

- **The interval.** L02's SLEEVE_L2 had d = −0.0043 with 90% interval [−0.0090, +0.0010]. That is a half-width of about
  0.0050, so a standard error of about 0.0030. L05 has the same slates, bank count and bootstrap, so expect the same width.
- **Chance that one arm's 90% upper bound falls below zero** (normal approximation; the both-seasons condition lowers each
  figure slightly):

| true effect | P(upper bound < 0) |
|---:|---:|
| 0 | 0.05 |
| −0.0043 (L02's estimate) | **0.41** |
| −0.0060 | 0.63 |
| −0.0076 | 0.80 |

- **What that means for cell D.** Suppose both arms truly have L02's effect. Then both miss with probability 0.35 if
  they were independent, and more, up to about 0.59, because they share the control. So cell D closes a working sleeve
  for the season somewhere between a third and three-fifths of the time.

**Suggested changes, all outcome-blind:**

1. **Cell D requires evidence of absence.** Classify as D only if `SLEEVE_L2_ORACLE`'s 90% lower bound is above −0.0043,
   which rules out an effect of L02's size. Otherwise record **"inconclusive"**: the sleeve stays a paper arm, with no
   closure and no adoption.
2. **Co-report LAG − ORACLE with its own interval.** Cells B and C currently infer "the predictor is the bottleneck" from
   one arm passing and the other failing. With about 40% power per arm, that pattern arises by chance.
3. **Consider four banks instead of two** if L02's per-slate-bank rows show that between-bank variance is a material part
   of the total. That is a design use of an already-read study's variance, not of its effect. The workstation has about 28
   hours before Sat 10:00, and two banks take 8–10.

## 2. The head layout: replayed on the historical books, and it holds up

The operator's Week-3 layout is a hybrid the review never tested. So `head_replay.py` replays it on the review's 107
historical expected-max books, using **production's own `assign_ranks` and `fewest_low_order`** from `enter_layout.py` at
`a5d2d857`.

- **Contests.** The Week-3 structure is 40 contests and 198 entries: wildcat 2×2, sat20 19×1, FFWC 1×4, supersat2 12×5,
  supersat25hi 3×17, supersat25lo 3×20. It is rebuilt from HANDOFF, since `contests.json` is private.
- **Not replayed.** The historical frames carry no designations, so the injury-flag rule cannot be tested.

Each cell is the change in each contest's best lineup / average lineup (contests weighted equally; t over slates):

| comparison | best | average |
|---|---|---|
| **head + fewest-LOW vs sequential/greedy** (the old default) | **+4.66 (t 6.5, 6/6 seasons)** | **+3.69 (t 6.5, 6/6)** |
| head + greedy vs sequential/greedy | +2.01 (t 3.7, 6/6) | +1.12 (t 3.0, 4/6) |
| **head: fewest-LOW vs greedy order** | **+2.65 (t 4.0, 6/6)** | **+2.57 (t 5.1, 6/6)** |
| head + fewest-LOW vs top + fewest-LOW (the price of the variety rule) | −2.28 (t −1.9) | −1.36 (t −1.3) |
| snake + fewest-LOW vs sequential/greedy | +1.81 (t 3.5, 6/6) | +2.31 (t 4.5, 6/6) |

The adopted layout keeps about two-thirds of `top`'s gain on the best lineup while keeping most lineups unique.

**Caveat.** The test bed exaggerates the cost of deep books: 198 of about 240 candidates here, against 12,555 live. So the
head-vs-sequential gap is probably overstated. The fewest-LOW-vs-greedy comparison uses the same book, so the depth
problem does not affect it.

**Where flagged rows land.** "Flagged rows behind every clean row" plus the snake deal sends the last rows to the largest
contests. The rehearsal had 50 flagged rows out of 144. On a slate like that, all of them land in the six supersat25
contests: 20 of the 51 hi entries (39%) and 30 of the 60 lo entries (50%). None land in the wildcat, sat20, FFWC or
supersat2 contests, and the head rows are clean. So the late-game injury risk concentrates in the contests holding 56% of
the entries. That may be intended; it should be a conscious choice. The alternative is to bar flagged rows from the head
only and order them by LOW like the rest.

## 3. The other items

- **Relaxed stack left out of L05:** agreed.
- **Lev's build time:** agreed it is the next question. It is unscheduled, and it matters from Week 4.
- **`qbvar` / `game` / `dark`: the reason is on record.** They were never dropped by decision. `N_QB_VARIANTS=4`,
  `N_GAMESTACK=4` and `N_DARKGAME=10` are in production's adopted policy, but nfl2's `generate_candidates` builds only lev
  and boom. So they have never run on the money path (the 09-22 cross-repo lever audit; the laptop's QB-variants report:
  "port it or stop calling it adopted"). No decision followed.
  - The replay pools add evidence for a port: those candidates reached a slate's top 5 at 1.5–1.7× their pool share, and
    expected-max took 45% (`qbvar`), 65% (`game`) and 86% (`dark`) of them.
  - This needs an operator decision: port (priced high in the audit) or retire from the policy.
- **Two corrections to the circulated summary:**
  - L02's labels were not "wrong about a quarter of the time". A quarter of historical winners' actually 20%+-owned players
    carried the low-owned label; LOW labels overall are about 94–99% precise.
  - Monday's paper scoring can illustrate one week, but it cannot show whether the layout works. The historical replay above
    is the evidence.
