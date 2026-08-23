# Process health assessment

Date: 2026-08-17. **No code was changed. No outcome was queried.**

Written in response to a direct operator question: *the deployment is taking
forever and the process seems to endlessly find issues to correct — are these
legitimate problems, and will it ever stop?*

**Short answer: no, not on the current trajectory — and the reason is
structural, not a lack of discipline.**

> **CORRECTION, 2026-08-18.** Section 2.3 of the original version of this
> document overstated its central statistical claim, and the correction is
> accepted in full. The `+0.030` figure I cited was **not** a candidate-level
> simulator/outcome correlation: it was a 54-observation *omitted-oracle*
> rank/regret statistic drawn from superseded panel `20260805-hf5`, whose
> scorecard is non-citable after the PIT/DST repairs. I took a narrow statistic
> about a range-restricted subpopulation from an invalid panel and generalised
> it to "the simulator does not predict the objective." That was wrong.
> §2.3 below has been rewritten with the correct figures. **The process
> findings in §1, the six-arm transfer record, and every recommendation in §3
> are unaffected** — but the mechanism I proposed for them was too strong.

---

## 1. What the repository actually shows

| | count |
|---|---:|
| Documents in `reports/` | **389** |
| Protocols | 83 |
| Repairs | 49 |
| Reconciliations | 43 |
| Amendments | 24 |
| Invalidations | 3 |
| **Governance subtotal** | **202** |
| **Results** | **56** |
| **Governance-to-result ratio** | **3.6 : 1** |

Document creation rate, last eight days: 25 / 40 / 35 / 69 / 43 / 54 / 56 / 24.
Roughly **fifty documents per day, sustained.**

Since the forensic completed on 2026-08-14: **489 commits**, approximately
**180 new documents**, and **zero production adoptions.** The last substantive
change to `src/nfl_dfs/inference/production_policy.py` was the CBWU promotion on
2026-08-14 (`74c22b5`). Everything in the 489 commits since is hardening,
shadowing, plumbing or repair.

That is the shape of the problem. The work is not slow — it is producing
enormous output. The output has stopped being science and become **process about
science**.

---

## 2. Three different things are being conflated

### 2.1 Some problems are genuinely real

The audit discipline has earned its keep. Real defects caught, each of which
would have produced a false conclusion:

- DST held constant across all 30,000 simulated worlds
- `H` solved under production stacking rules, so the forensic cannot see loss
  caused by those rules
- DST salary aliases dropping 478 rows across 2019/2021
- The Dirichlet allocation-unit error (`26e73c5`), which moved every dependence
  measurement
- Post-lock injury data, end-of-season position leakage, cross-season smoother
  contamination
- The ownership-fade mislabel, the GREEN2 environment typo, the TDLEDGER
  season-pooling defect

The operator's instinct to distrust an unaudited result is correct. The
headline replay figure went 27/107 → 17/107 → non-citable. Without this
discipline the system would have been deployed on a fiction.

**This layer should not be reduced.**

### 2.2 Most recent problems are self-inflicted by the apparatus

The ATLAS matched-diversity grid has been attempted six times:

| grid | cause of loss | scientific content |
|---|---|---|
| repair2 | CBC `SIGKILL` at ~84% of a 4 GiB cap | some — real resource limit |
| repair3 | all 54 cells rejected a new prefix (hard-coded constant) | **none** |
| repair4 | one 16 GiB memory failure + 6 platform errors | partial |
| repair5 | `ATLAS world <n> identity tiebreak is infeasible` | some — real defect |
| repair6 | dual-canary execution failed; closed `no-scoreable-population` | **none** |

Two of six taught anything about the model. The rest were build and transport
failures. **Final disposition (2026-08-18): the ATLAS matched-diversity grid
never produced a scoreable population at all** — six attempts, zero science.

**And each apparatus failure carries the full ceremony of a scientific one:** an
invalidation document, a repair protocol, an amendment, an image rebuild, a
revalidation, a reconciliation. One hard-coded prefix constant consumed roughly
six documents and a day.

That is not rigor. It is ceremony attached to a build error.

### 2.3 The deep problem — a weak surrogate, not a broken one

**Corrected 2026-08-18.** On the terminal 54-slate CBWU forensic corpus, the
simulator's candidate-level association with realized score is **weak but real
and positive**:

| statistic | pooled Spearman | mean within-slate |
|---|---:|---:|
| `p_line` | 0.216 | 0.156 |
| simulated mean | 0.237 | 0.195 |
| simulated q99 | 0.223 | 0.166 |

Within-slate intervals are above zero under slate bootstrap, and the held-out
candidate model reached **ROC AUC 0.6255**. That is a usable weak signal. It is
*not* the null instrument the first version of this document described.

The real problem is narrower and more tractable than "the simulator is
invalid," and it has two parts.

**(a) A weak surrogate is not sufficient as a sole gate.** At ρ ≈ 0.22, the
simulated criterion carries real information but nowhere near enough to
adjudicate a mechanism on its own. That is entirely consistent with the
transfer record, which is the finding that actually carries the argument:

| mechanism | simulated criteria | realized outcome |
|---|---|---|
| Schaake shuffle | passed its premise | rejected |
| Gumbel (plain) | passed | 26/107 vs 27/107 |
| Gumbel (fixed-budget) | passed | 20/107 |
| Gumbel (hierarchical) | passed | 23/107 vs 27/107 |
| Cross-entropy worlds | promising first run | 26/107 vs 27/107 |
| Fast-role / latent role | passed | 11/107 vs 17/107 |

Six mechanisms cleared a weak gate and failed the real one. **That record — not
a correlation coefficient — is the evidence that simulated criteria cannot be
the sole promotion or closure screen.**

**(b) The miscalibration is concentrated in the tail, which is the objective.**
The selected-book calibration audit found the simulated book-maximum
distribution is **too fat in the shoulder and too thin in the tail**: 194
over-predicted (8 realized vs 10.26 expected), 210 under-predicted by 2.2x
(6 realized vs 2.76 expected). Independently, the dependence diagnostic found an
under-coupled QB hub with over-produced high multiplicity — which produces
exactly that shape. Two methods, same shape error.

So the honest diagnosis is not "the instrument reads nothing." It is
**"the instrument reads the middle adequately and the tail poorly, and the tail
is the entire objective."** That is a specific, upstream, fixable problem, and it
points at marginal/dependence calibration rather than at another construction
sweep.

**Why the loop still does not terminate on its own.** A weak gate produces
mostly nulls; every null invites a refinement; every refinement needs a
protocol, an image, and a rebuild; every rebuild can fail and needs a repair
document. The loop is self-sustaining for process reasons regardless of whether
the surrogate is null or merely weak. The termination condition has to be
imposed from outside — which is what §3 proposes.

## 3. What I would do

### 3.1 Ship the money path and decouple it from research

The production policy is frozen and works. **Nothing in the research queue
blocks it.** Week 1 is roughly three weeks out.

The deployment is not waiting on science — it is entangled with a research queue
competing for the same single 32 GiB compute slot, the same immutable-image
build pipeline and the same review bandwidth. Separating the two costs nothing
scientifically and immediately stops research failures from reading as
deployment delays.

### 3.2 ~~Validate the surrogate before running arm 41~~ — DONE, and it reframed the problem

**Executed 2026-08-17.** The selected-book tail calibration audit ran on 54
slates with 50,000 worlds per book and an independent stdlib-only
reimplementation (zero mismatches, max delta `4.44e-16`).

Result: the surrogate is **weak, not null** (§2.3), the audit is underpowered at
6-17 events per threshold, and the informative signal is the **shape**: the
simulated book maximum is too fat at 194 and too thin at 210, matching the
independently measured under-coupled QB hub.

The corrected next question is therefore **not** "is the simulator valid" but
**"can the tail of the simulated book-maximum distribution be calibrated?"**
That is upstream marginal/dependence work, and it now outranks another
construction sweep on the queue.

### 3.3 The most valuable thing available is data that does not exist yet

- `nfl_raw.dk_contest_fills` — **empty**
- `nfl_raw.contest_ownership` — 103,556 rows, no populated score field
- 2026 prop coverage — **one bookmaker, one market**, 898 rows

There has never been real contest fill, duplication or payout data. A season of
real prospective data is worth more than any simulated arm, and **it can only be
collected by operating.** Every week not deployed is a week of that data
permanently lost.

### 3.4 Cap governance rather than abandoning it

A single rule — *mechanical repairs get a receipt, not a protocol* — would remove
on the order of ninety documents without touching one scientific safeguard.
Protocols, amendments and reconciliations should attach to **claims about the
world**, not to build failures, prefix constants or resource envelopes.

---

## 4. My own contribution to this

I have written roughly twenty-five review documents in this window, and nearly
every one spawned a reconciliation, an amendment, or both. Several of my
accepted recommendations — the pair-reach floor, the high-tail guards, the
support census, the retry and canary rules — **added governance surface.**

They were individually defensible. Collectively they are part of what the
operator is feeling. If the ratio in §1 is to change, some of that has to come
off, and the reviewer function should be held to the same standard as everything
else.

---

## 5. Summary

**The project does not have a discipline problem. It has a targeting problem.**

The rigor is real, it has caught real defects, and it should not be loosened.
But it is being spent adjudicating mechanisms on an instrument that is only
weakly predictive overall and specifically miscalibrated in the tail that
defines the objective. Until that tail calibration is repaired, more careful
measurement of the same quantity produces more documents and no adoptions.

| # | action | cost |
|---|---|---|
| 1 | **Ship the money path; decouple deployment from the research queue** | none scientifically |
| 2 | ~~Test whether simulated coverage predicts realized tail outcome~~ **DONE 2026-08-17** — weak/underpowered; shape error localised to the tail. Next: upstream marginal/dependence calibration | superseded |
| 3 | **Start collecting real contest fill / duplication / payout / prop data in Week 1** | requires operating |
| 4 | **Mechanical repairs get a receipt, not a protocol** | removes ~90 documents |

Items 1 and 3 are the same action. Item 2 has now been executed: the surrogate is
weak rather than null, and its failure is concentrated in the tail. That makes
upstream tail calibration — not another construction sweep — the highest-value
research direction.
