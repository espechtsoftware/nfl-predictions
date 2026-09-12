# External review of the PREREG-076 `UNION_EMAX` non-adoption

**Date:** 2026-09-09  
**Scope:** PREREG-076 R2, the reported `+3.7781`-point mean weekly K80 maximum, its non-adoption, and a better successor design  
**Recommendation:** keep the non-adoption; preserve exact `UNION_EMAX` as a replication anchor; add a separately preregistered control-anchored robust-union challenger; obtain adoption evidence only from genuinely new football outcomes

## Executive conclusion

The non-adoption was correct. It should not be interpreted as a failed idea.
`UNION_EMAX` found a real-looking and potentially valuable mechanism: two almost
disjoint generators supplied complementary lineups, and selecting across their
union raised the historical weekly K80 maximum by `+3.7781` points. The raw
bootstrap interval, `[+0.1989, +7.3474]`, narrowly excluded zero and the effect
had the same sign in 2023 and 2024.

But the result does not yet show that the system became better at the part of
the tail that matters most. It changed weeks at or above 194 from 6 to 10 and
weeks at or above 200 from 4 to 7, while producing no increase at 210 and no
220/230 week in either arm. Its preregistered primary endpoint,
`GLOBAL_WEMAX_PROXY`, was positive but uncertain: `+0.007519`, 95% interval
`[-0.006856, +0.021670]`. The same historical player outcomes had already been
opened during PREREG-072, and the continuation was selected after that read.
The raw result is therefore strong development evidence, not adoption evidence.

My main disagreement is with the phrase **“genuinely fresh generation
cohort”** if it means new random seeds on the same 2023-2024 slates. That would
be a useful stochastic replication, but it would not be a fresh efficacy
cohort. The football outcomes, and the development decisions they influenced,
would still be reused. The clean confirmation is a frozen 2026 prospective
shadow. A 2025 CP-1 read could be an additional pipeline-specific transport
check, but it is not epistemically clean across the wider program because 2025
results have informed other work.

The best immediate redesign is not another unconstrained greedy union. Start
with the DK-only K80 control and admit union candidates through robust,
one-for-one swaps evaluated across independent simulation banks and separately
named laws. Preserve a protected DK core and require proposed swaps to improve
the average simulated maximum without materially worsening rare states already
covered by the control. This directly attacks the observed failure mode:
`UNION_EMAX` gained on many ordinary/shoulder weeks but sometimes discarded a
control lineup that would have delivered a 200-plus result.

I would run four frozen shadow books on each prospective 2026 slate:

1. `CTX0_DK80`, the exact control;
2. exact `UNION_EMAX`, unchanged, as the replication anchor;
3. `CTX40_DK40`, unchanged, as the structural-hedge benchmark; and
4. a new `ANCHORED_UNION_80`, which protects at least 40 DK-only seats and
   permits only robustly beneficial swaps from the full union.

Only one challenger should be declared primary for adoption testing; my choice
would be `ANCHORED_UNION_80`. The other two are mechanism comparators. This is
small enough to interpret and broad enough to learn whether the benefit came
from candidate complementarity, a fixed source hedge, or unconstrained
re-optimization.

## What I reviewed

I reviewed the following exact evidence rather than relying on the headline:

- PREREG-076 result report and JSON at lab commit `d3df9a1`:
  `reports/2026-09-09-prereg076-r2-fresh-retrieval-score-result.md` and
  `results/prereg076_fresh_retrieval_score_v1.json`;
- the score-free selector implementation at source commit
  `72ce2543bdb76b0489b2d695385ab425382a7f18`, principally
  `src/nfl2/cp1_fresh_retrieval.py` and `src/nfl2/selectors.py`;
- PREREG-072 and its raw-score report, which opened the candidate outcomes and
  nominated the structured-context/retrieval continuation;
- the production-to-lab successor nomination at lab commit `4ac06b6`;
- all 108 authenticated PREREG-076 R2 score-free cell artifacts from selector
  banks 770, 771, and 772; and
- the current production handoff and the earlier same-pool WEMAX-versus-DEMAX
  result.

The immutable PREREG-076 seal inspected for this review was:

`gs://nfl-2-506823-lab/seals/PREREG-076/103b770r2-103b771r2-103b772r2.json#1788960730683819`

Its recorded SHA-256 is
`5ccdd9154d3ce4975d79e360bdb91da90e74d3245d75d1f549de04566975995e`.
The result JSON SHA-256 is
`85d16a3eeb1e7e9fe693286573f05b655ba5a26a09174dc8cf603cd4c8cb1163`.

## What the experiment actually tested

For each of 36 2023-2024 slates, the experiment reopened two already accepted
candidate populations from bank 740:

- 800 full-universe, DK-legality-only candidates; and
- 800 full-universe, historical-GPP-context candidates.

The control selected K80 only from the DK population. `UNION_EMAX` deduplicated
the two populations, then greedily maximized raw expected book maximum over one
common P_MIX judge for that cell. Each judge contained 10,000 incumbent and
10,000 hierarchical worlds with participation masks. Three newly seeded
selector banks repeated that score-free choice. Realized outcomes were then
opened once for the sealed cohort.

This design cleanly answers a narrow question: **given these previously
generated populations and this P_MIX selection law, does allowing the selector
to choose from both sources retrospectively produce a better historical K80
book than forcing it to choose only from DK candidates?** It does not answer
whether a future-slate book improves, whether P_MIX transfers to the exact
current-money law, or whether the added raw points increase first-place equity.

## Result anatomy

### Registered comparison

| Metric | `CTX0_DK80` | `UNION_EMAX` | Difference |
|---|---:|---:|---:|
| Mean raw weekly K80 maximum | 179.460 | 183.238 | **+3.778** |
| Primary `GLOBAL_WEMAX_PROXY` | — | — | **+0.007519** |
| Proxy 95% interval | — | — | `[-0.006856, +0.021670]` |
| Raw 95% interval | — | — | `[+0.1989, +7.3474]` |
| Weekly W/L/T | — | — | `21 / 10 / 5` |
| Weeks at least 194 | 6 | 10 | `+4` |
| Weeks at least 200 | 4 | 7 | `+3` |
| Weeks at least 210 | 3 | 3 | `0` |
| Weeks at least 220 / 230 | 0 / 0 | 0 / 0 | `0 / 0` |

This is encouraging, but it is principally a **shoulder-to-lower-tail gain**.
It is not yet evidence that the system retrieves more 210-plus or
winner-range lineups. That distinction matters because three points added near
180 may have little tournament value, while three points added near a winning
threshold may be decisive.

The mean also hides an asymmetric weekly distribution. After averaging the
three selector banks within slate:

- median delta was only `+1.55`;
- the interquartile range was approximately `[-0.24, +11.81]`;
- the range was `-23.30` to `+24.55`;
- nine weeks gained at least 10 points; and
- three weeks lost at least 10 points.

Two losses expose the specific risk. On 2023 Week 4 the control averaged 215.50
and the union 192.20 (`-23.30`). On 2024 Week 11 the control averaged 205.10 and
the union 188.85 (`-16.25`). The union can create large upside, but it can also
displace the incumbent lineup that covers the realized high-scoring state.
That is the reason to anchor the next selector to the control rather than
rebuild all 80 seats from zero.

### The secondary arm may contain the more useful clue

The prespecified `CTX40_DK40` arm beat control by `+3.4383` raw points, with a
95% interval `[+0.8479, +6.2589]`, and by `+0.009532` on the proxy, with interval
`[+0.001423, +0.018591]`. Derived directly from the frozen weekly rows:

- `UNION_EMAX` beat `CTX40_DK40` by only `+0.340` raw points;
- `UNION_EMAX` was **worse by about 0.0020** on the governing proxy;
- `CTX40_DK40` produced 11/7/4 weeks at 194/200/210, versus 10/7/3 for
  `UNION_EMAX`; and
- both produced zero weeks at 220/230.

The quota ladder was informed by the earlier opened result, so the 40/40 arm
cannot be adopted from this panel. It nevertheless suggests an important
mechanism: **source balance acts as regularization against simulation-law
overconfidence.** The unconstrained selector found a slightly higher raw mean,
but the fixed hedge did at least as well on the more tail-oriented measures and
avoided some displacement.

### `UNION_EMAX` is effectively a context-heavy book

The score-free artifacts make the mechanism clearer:

- deduplicated union size: 1,575 to 1,591, mean 1,584.6;
- overlap between the two 800-candidate sources: only 9 to 25, mean 15.4;
- context seats selected by `UNION_EMAX`: 49 to 70, mean 60.8;
- mean overlap of `UNION_EMAX` with DK80: 19.0 lineups; and
- mean overlap with context80: 59.4 lineups.

Thus, candidate complementarity is genuine, but the final book is not a neutral
union. Under P_MIX it behaves roughly like a 60-context/20-DK allocation. The
historical outcomes instead make the 40/40 hedge look at least as attractive.
This is consistent with P_MIX overstating the incremental value of context
candidates or understating the insurance value of DK-only lineups.

### The selector's internal confidence did not identify realized gain weeks

Across all 108 score-free cells, P_MIX predicted a positive mean-book-max
advantage for the union every time: range `+2.10` to `+3.54`, mean `+2.68`.
That is expected to some degree because the union is the larger choice set and
is optimized on the same worlds used to calculate that advantage.

I joined each cell's score-free predicted advantage to its bank-specific
realized raw advantage. The diagnostic relationship was weak:

- 108-cell Pearson correlation: `0.077`;
- 108-cell Spearman correlation: `0.185`;
- after averaging selector banks within slate: Pearson `0.085`, Spearman
  `0.178`; and
- mean predicted advantage was `2.735` in realized wins, `2.624` in losses,
  and `2.608` in ties.

The 108 cells are not 108 independent football outcomes, so these figures are
diagnostic rather than an inferential test. They still show that the magnitude
of the in-law optimization gain supplied almost no separation between weeks
where the union helped and weeks where it hurt. More optimization against the
same judge is unlikely to solve that problem.

### Selection is less stable on the union frontier

For a common slate, pairwise overlap between union books selected by different
fresh banks averaged 58.1 of 80; the all-three intersection averaged 49.8.
For DK80 those figures were 64.4 and 57.9. The union offers more options but
also creates a flatter, noisier selection frontier. A single bank can therefore
replace roughly 30 seats without strong cross-bank support. This is another
reason to use a consensus/robust core and a bounded exploration sleeve.

## Why the non-adoption is right

There are four independent reasons not to promote this result directly.

1. **The outcome cohort was already open.** PREREG-072 exposed candidate-level
   score behavior and led directly to the structured-context and allocation
   continuation. The later freeze prevents further cheating, but it cannot
   undo that adaptive path.
2. **The registered primary remains uncertain.** Its interval crosses zero.
   The raw diagnostic is positive, but switching the primary endpoint after
   seeing the result would be endpoint shopping.
3. **The effect has not moved the deep tail.** The improvement stopped below
   210 and included damaging displacement on two strong control weeks.
4. **The law has not earned money-law transport.** The result is exact evidence
   under its P_MIX judge. A separate result under the exact current-money law is
   required; the two laws should not be blended into one unnamed estimand.

The frozen decision rule was followed correctly. `adoption=false` and
`promotion=NONE` are strengths of the process, not excessive caution.

## The better next selector: control-anchored robust exchange

I recommend a new, separately named arm, `ANCHORED_UNION_80`. It should not
replace or mutate the nominated exact `UNION_EMAX` arm.

### Construction

1. Generate and deduplicate the same DK-only and context candidate sources.
2. Construct the exact DK-only K80 control first. This is the initial book.
3. Calculate each control lineup's **insurance contribution**: the loss in book
   maximum when it is removed, measured separately across multiple independent
   banks and under the exact current-money law and P_MIX stress law.
4. Consider one-for-one exchanges between a current seat and any unselected
   union candidate. For each exchange calculate:
   - average marginal maximum gain across selection banks;
   - dispersion and worst-bank gain;
   - change under each separately named law;
   - loss of rare-world coverage currently supplied by the dropped lineup; and
   - new extreme-world clusters covered by the added lineup.
5. Accept only robustly positive exchanges. A practical frozen score is
   `mean marginal gain - lambda * cross-bank standard deviation`, accompanied
   by a non-inferiority constraint under the current-money law. Freeze `lambda`
   and the non-inferiority margin before any prospective outcome.
6. Protect at least 40 DK-only seats and cap the exchange count at 40 for the
   first test. Stop earlier when no admissible positive exchange remains.
7. Use untouched judge blocks only for score-free audit; do not select on the
   blocks used to advertise held-out simulated performance.

The 40-seat floor is a new prospective hypothesis motivated by the secondary
arm, not a licensed optimum. It must be labeled that way. A useful alternative
is to freeze a source-neutral floor based on control insurance contribution,
but that is harder to communicate and audit in the first test.

This construction differs from a fixed 40/40 split. It guarantees at least 40
DK seats, but the remaining seats may come from either source. More importantly,
every departure from the incumbent has an explicit marginal justification and
a measurable displacement cost. It should retain much of the union's upside
while reducing the `215.5 -> 192.2` type of failure.

### Why not merely change EMAX to WEMAX?

The project has already run that same-pool objective swap. PREREG-056 found
approximately `+0.00022` proxy utility and `+0.251` raw points, with substantial
book turnover but no useful lift. The current evidence says the missing input
is not just a different monotone transform of the same simulated scores.

A tail-rescue sleeve remains promising only if it introduces something the
judge does not already know: independently modeled coherent tail regimes,
point-in-time market/role information, or candidate-level features validated
out of fold. Rebranding EMAX as WEMAX without new information is a closed path.

## Improve the target, not only the selector

`GLOBAL_WEMAX_PROXY` is a smoothed pooled CDF of historical Milly winner
scores. It is useful, but it is not same-slate win probability and it ignores
slate difficulty, field size, contest structure, and duplication. Raw average
maximum has the opposite problem: every point receives equal value regardless
of whether it changes tournament placement.

The ideal endpoint is a pre-lock conditional contest utility:

`U(max_book_score | slate size, field size, totals, salary/ownership shape, contest)`

Until enough full-field data exist, use a regularized, leave-season-out model
of winner threshold conditional on observable slate characteristics. For 2026,
freeze a model trained only on data available before the slate. Once full
contest entries and duplication are captured, graduate to expected best-book
payout or first-place probability.

For the immediate prospective test, do not delay waiting for that model. Freeze
one primary endpoint before Week 1/first eligible slate:

- if the operational goal is literally average weekly maximum, make raw K80
  maximum primary and retain the existing proxy as secondary;
- if the goal is tournament-winning equity, retain a smooth winner-oriented
  utility as primary, but add a raw-score and deep-tail guard.

In either case report two displacement measures:

- downside on weeks where the control reaches a predeclared high threshold;
  and
- expected shortfall of the challenger relative to control, not just mean
  improvement.

This prevents a method from passing by converting many 180s into 194s while
discarding the few 210-plus control hits the portfolio exists to find.

## A concrete three-track successor program

### Track S: stochastic replication, no adoption authority

Run the exact nominated `UNION_EMAX` against exact `CTX0_DK80` with fresh
candidate and judge seeds on the same historical slates. Call this what it is:
**same-outcome stochastic replication**.

Use it to answer:

- Is the raw lift stable to candidate generation randomness?
- Does the approximately 60/20 emergent source mix persist?
- Is union book membership less stable than control membership?
- Does an independent score-free audit bank confirm the selected-bank gain?

This track may strengthen or weaken mechanism confidence. It cannot license
adoption, regardless of how many new seeds are used, because selector banks do
not create new football outcomes.

### Track R: score-free robust-selector screen

On fresh candidate and world identities, compare:

- exact `CTX0_DK80`;
- exact `UNION_EMAX`;
- exact `CTX40_DK40`; and
- `ANCHORED_UNION_80`.

Use a strict generation/selection/audit partition. Evaluate under the exact
current-money law first and P_MIX as a separately reported stress law. Do not
average the laws into a single favorable score. Required score-free outputs
should include source seats, unique candidate counts, conditional novelty,
selected-book overlap, all-bank intersection, marginal swap receipts, and
worst-law displacement.

This track can choose the prospective challenger, but cannot establish realized
efficacy.

### Track P: 2026 prospective confirmation

Freeze all arm definitions, inputs, seeds, code/image identities, and decision
rules before the first applicable slate lock. Produce one deployable K80 book
per arm and seal all hashes before outcomes. No Week-1 money-policy change is
implied; shadow books are sufficient.

Treat weekly slates as the outcome units. Multiple selector banks on one slate
are sensitivity replicates, not extra sample size. If results will be viewed
weekly, use a preregistered anytime-valid rule or fixed checkpoints; otherwise
seal the accumulated outcome comparison until the scheduled read. Do not alter
the arm after an early win or loss.

Declare one primary challenger and comparison. I recommend
`ANCHORED_UNION_80 - CTX0_DK80`. Exact `UNION_EMAX` and `CTX40_DK40` should be
secondary mechanism comparators or placed in a multiplicity-controlled family.

An optional 2025 CP-1 read may be useful as a pipeline-specific transport
check if its exact authority remains inaccessible to the CP-1 reader. It must
be labeled **externally informed**, not a pristine holdout: other program work
has already consumed 2025 information. A 2025 evaluation also must not use a
winner CDF trained on 2025 winner outcomes; use raw maximum or a leave-2025-out
registry.

## Rules and laws that should be kept or revised

| Rule or law | Disposition | Reason |
|---|---|---|
| No adoption from PREREG-076 | **Keep** | Correct protection against adaptive reuse of opened outcomes. |
| One authenticated result read; no rerun | **Keep** | Prevents silent selection among reads. |
| Separate generation, selection, seal, and outcome read | **Keep** | Necessary audit boundary. |
| Exact K80, legality, deterministic dedup/ties | **Keep** | These are product and reproducibility invariants. |
| “Fresh generation cohort” as confirmation | **Rename/limit** | New seeds on old outcomes prove stochastic robustness, not future efficacy. Require a fresh outcome cohort for adoption. |
| Exact `UNION_EMAX` must be the only successor | **Relax through a parallel lane** | Keep exact union as the confirmation anchor, but permit a separately named robust challenger. Do not mutate the frozen arm. |
| Positive in every selector bank and season | **Use as a stability diagnostic, not a universal veto** | Banks are Monte Carlo sensitivity views; seasons/slates are the outcome units. A rare-tail improvement can legitimately be uneven. |
| P_MIX-selected gain implies money-law gain | **Reject** | Preserve law separation. Current-money and stress-law results need distinct names and gates. |
| `GLOBAL_WEMAX_PROXY` always primary | **Revisit prospectively** | It is pooled and not contest-conditional. Freeze the endpoint that matches the operator's actual goal before the next read. |
| Unconstrained re-optimization over the union | **Replace in the main challenger** | It selected about 61 context seats, had weaker bank stability, and caused large incumbent displacement losses. |
| Universal historical GPP structure | **Do not restore** | Complementary source generation is supported; a universal construction law is not. |
| Interval exclusion required for every exploratory nomination | **Do not require** | A sign-based nomination can efficiently route development. Adoption should have a separately frozen practical-evidence threshold. |

The important governance change is to maintain two lanes. The **replication
lane** preserves exact frozen arms and evidence lineage. The **innovation lane**
may change the mechanism under a new name and must earn its own prospective
evidence. Requiring every new idea to be an exact copy would be too rigid;
allowing the copied arm to drift would destroy the confirmation.

## Recommended order of work

1. Freeze and emit the four 2026 shadow books before the first applicable lock.
   This is the only time-sensitive action and requires no new in-season feature
   collection.
2. Correct successor terminology so same-slate/new-seed results cannot be
   mistaken for adoption-grade freshness.
3. Run the exact same-outcome stochastic replication, but label it development
   evidence only.
4. Implement the control-anchored exchange selector with explicit marginal
   swap receipts, a 40-seat DK floor, independent audit banks, and named law
   separation.
5. Select one prospective primary challenger without opening 2026 outcomes.
6. Settle all frozen shadows at predeclared checkpoints. Report raw maximum,
   winner-oriented utility, 194/200/210-plus behavior, control-high-week
   displacement, and book stability.
7. Add a contest-conditional winner/payout objective after sufficient field and
   duplication capture exists; do not hold up the current shadow waiting for it.

## Final assessment

PREREG-076 is one of the more promising recent results, but the headline should
be stated precisely:

> Combining nearly disjoint DK-only and GPP-context candidate populations and
> selecting across them under P_MIX improved the development-panel raw weekly
> K80 maximum by 3.78 points, mostly between 194 and 200, while leaving the
> 210-plus count unchanged and sometimes displacing strong control hits.

That supports continued investment in **complementary candidate sources plus
better portfolio retrieval**. It does not yet support an unconstrained
context-heavy union in the money book. The highest-potential refinement is to
turn the DK control into an insured base portfolio, admit only robustly valuable
union swaps, and make the resulting arm compete prospectively against both the
exact union and the simple 40/40 hedge.

The no-adoption should stand. The mechanism should advance—but under a design
that can distinguish repeatable optimization, genuine future-outcome lift, and
actual deep-tail tournament value.
