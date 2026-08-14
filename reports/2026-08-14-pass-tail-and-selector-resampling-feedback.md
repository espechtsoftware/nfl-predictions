# Feedback: SIS pass-tail exact-80 result and the selector-resampling diagnostic

Date: 2026-08-14. **No code was changed. No new outcome was queried** — this
reads results already recorded.

---

## 1. The bagging refutation is correct and I concede it

The disposition states that the diagnostic "does not license bootstrap-mean
bagging, which is algebraically the existing empirical objective plus finite
sampling noise."

That is right, and it refutes §4 of
`2026-08-14-selector-stability-under-world-resampling.md` cleanly.

Marginal coverage is **linear** in the world indicator. The expectation of a
bootstrap-resampled linear statistic is the empirical statistic on the original
sample, so averaging marginal-coverage estimates over `B` bootstrap resamples
converges to the value greedy already uses. Bagging a linear functional is a
no-op in expectation. My proposal was caught between two options and neither
works: the linear version adds nothing, and the nonlinear version — membership
voting — breaks complementarity, which I had already ruled out for that reason.

The diagnostic in §3 was still worth running, and it produced real information.
The proposed selector change was wrong.

**If anything survives, it is not bagging but *splitting*.** The report itself
measures selection-half minus validation-half coverage optimism at
`0.01275` — 1.28 percentage points. Selecting on one half of the worlds and
tie-breaking on the other is sample splitting, not averaging, and it removes
that optimism directly rather than in expectation. I would not push it: 1.28
points of optimism on a metric that is already a proxy is small, and the
disposition's own conclusion — that the multi-seed world-union cells supply
genuinely *new* world information and are therefore the relevant experiment — is
the better use of effort. More worlds beats smarter use of the same worlds when
the defect is a finite-sample artifact.

## 2. Two things in the diagnostic worth carrying forward

**2.1 The disjoint-half number is the honest one, and it is worse.**

| measure | overlap of 80 |
|---|---:|
| bootstrap resamples | 61.6362 |
| **disjoint halves** | **54.2778** |

Bootstrap resamples of the same 30,000 worlds share roughly 63% of their draws
by construction, so they are correlated and **understate** instability. Disjoint
halves are independent evidence and are the cleaner test.

Under independent world evidence, **26 of 80 slots differ.** The disposition
reports both but frames the verdict on the bootstrap figure ("inside the
preregistered intermediate band"). The disjoint figure deserves at least equal
weight in the forensic register.

**2.2 The prefix result inverted my prediction, and the report reads it
correctly.**

Prefix overlap rises monotonically: `0.59/1`, `3.13/5`, `6.49/10`, `13.58/20`,
`29.08/40`, `45.12/60`, `61.64/80`. I predicted early picks stable and late
picks noisy; the opposite holds. The first pick agrees barely half the time,
because it is a single argmax over many near-tied total-coverage values, while
the accumulated *set* converges as it grows.

The report's reading — "the exact ordering near the top is less stable than the
broad membership" — is right, and it is reassuring for the objective, since all
80 are submitted and order carries no information.

**The consequence the disposition does not draw:** with 26 of 80 slots
differing under independent evidence, the *effective* number of deliberately
chosen entries is closer to **54 than 80**. That bears on the entries-per-slate
question, and — more importantly for §3 — it means an arm-to-arm difference of a
few threshold-weeks may be partly reshuffling among the unstable slots rather
than mechanism.

---

## 3. The pass-tail result

This is the strongest scoring gain the program has produced in some time, and
the disposition's transfer-boundary caution — that it does not license silently
combining the cache and schedules with the K=1 money-lineup policy, because that
transfer cell was not tested — is exactly right and should be held to.

Three pieces of feedback.

### 3.1 Report distinct weeks, not nested threshold counts — this is the main one

| threshold | control | treatment | delta |
|---:|---:|---:|---:|
| 240 | 0 | 0 | 0 |
| 230 | 1 | 1 | 0 |
| 220 | 3 | 5 | **+2** |
| 210 | 11 | 13 | **+2** |
| 200 | 20 | 23 | **+3** |
| 194 | 37 | 38 | +1 |

These thresholds are **nested**. A week that crosses 220 necessarily crosses
210, 200 and 194. So `+2 / +2 / +3 / +1` is not eight improvements — it may be
as few as **three distinct slates**, with the same two weeks producing the 220
and 210 gains and one further week appearing at 200.

The grid presentation makes a small number of events look like a broad pattern,
and the same is true of every past adoption presented this way.

**Recommendation, and it costs one query:** report the **set of slates that
changed**, per threshold, and the count of *distinct* improved weeks. If the
+2 at 220 and the +2 at 210 are the same two slates, say so. That single number
is what determines whether this is a three-event result or an eight-event one,
and it is the difference between a modest and a strong finding.

This should become a standing field on every exact-80 comparison.

### 3.2 2025 is the least supportive season, and it is the most relevant one

- 2023: improves 220/210/200/194/187 by `+1/+2/+3/+2/+2`, mean `+0.9993`
- 2024: improves 220/210/200/194 by `+1/+1/+2/+3`, loses four at 187, mean `-1.1898`
- **2025: 220 tied; loses `1/2/4` at 210/200/194; mean `-1.0724`**

The aggregate tail-first objective governs and season signs are not a veto —
that is settled policy and I am not reopening it. But the pattern is worth
naming explicitly in the prospective monitoring plan: **the gain is concentrated
in the two older seasons and the most recent season is negative below 220.**

That is the shape you would expect either from an era-specific effect or from
something fitted to older data, and 2026 is the season this will actually be
served into. The result document does note the mixed diagnostics; I would go
one step further and make "does the 2025 pattern persist" an explicit,
pre-declared question for the prospective shadow rather than a general caution.

### 3.3 Read the deltas against the instability just measured

Mean weekly maximum declined `173.8999 → 173.4789`, with a slate-clustered 95%
interval of `[-1.5092, 0.7001]` spanning zero. That is diagnostic under the
standing law, and correctly labelled.

But §2 measured that 26 of 80 selected slots differ under independent world
evidence within a *single* arm. That is a within-arm instability measure, not an
arm-to-arm noise floor — the two are different, and I am not claiming the
pass-tail deltas are inside noise. What it does establish is that **a non-trivial
noise floor exists and has now been partially quantified**, and that a
`+2 / +2 / +3` result should be reported alongside it rather than in isolation.

The multi-seed factorial's per-seed standalone books remain the right instrument
for the actual arm-to-arm floor.

---

## 4. Suggested feedback to give

1. **Adopt "distinct improved slates" as a mandatory field** on every exact-80
   comparison, alongside the nested threshold grid. Retro-fit it to this result
   first — it is one query and it materially changes how strong the finding is.
2. **Give the disjoint-half overlap (54.28/80) equal billing** with the
   bootstrap figure in the forensic register, and record the implied ~54
   effective entries.
3. **Pre-declare the 2025 question** for prospective monitoring rather than
   noting the mixed seasons generally.
4. **Hold the transfer boundary.** The cache and schedules were tested against
   the finite-K research baseline, not the K=1 money policy; that cell is
   untested and the result document says so. Make the eventual production wiring
   record the exact resulting state before Week 1, as it already requires.
5. Bagging is closed. **Do not build a shrinkage or split-selection variant
   unless the multi-seed factorial shows the world sample is limiting** — that
   experiment answers the same question with new information rather than a
   rearrangement of the old.
