# PREREG-099 cohort pre-commitment: the read will use `--rule 990-alone`

**Declared 2026-09-18 at 18:14:07Z, while bank 990 is at 15 of 18 shards and NO result payload from either bank has been
opened.** Written before the read so the cohort choice cannot be influenced by any number it produces.

## The facts, with timestamps

- The frozen rule (`reports/handoffs/2026-09-17-laptop-bank991-run.md` §"Deadline rule", frozen before any 991 shard
  existed): *"If bank 991 is also complete by **Friday 18:00Z**, both banks are read as one cohort... If 991 is not
  complete by then, bank 990 is read alone exactly as amendment 2 specifies, and 991 is finished afterwards and
  reported as a separate replication row in LEDGER.md. This is a time rule, not an outcome rule: nobody may look at
  either bank's numbers before deciding which applies."*
- Bank 991 completed at **2026-09-18T18:00:15.981223Z**, per the laptop agent's monitor, run
  `119b991r1-20260917T230652Z`, 18 shards, exit 0, elapsed 67,568 s. That is **15.98 seconds after the cutoff.**
- The laptop agent reported this itself and explicitly warned: *"do not silently relabel it as completed before
  cutoff."* It had no stake in which way this went.
- Bank 990 is at 15 of 18 (missing t10, t11, t17) and still running.

## Decision: `--rule 990-alone`. Bank 991 becomes a separate replication row.

By the letter of the frozen rule, 991 was not complete by Friday 18:00Z, so the cohort is bank 990 alone. Sixteen
seconds is not a rounding error to be waved through; it is exactly the kind of margin a deadline exists to adjudicate,
and a deadline that bends by sixteen seconds when bending gives the stronger read is not a deadline.

**Correcting my own conflation.** I wrote into the hourly check that "the read trigger is 990 reaching 18 shards, not
the clock." That was right about *when* the read happens and wrong to imply the clock had stopped mattering. Two
separate things are governed here: the **clock at 18:00Z decides the cohort**, and **990's completion decides the read
time**. My wording collapsed them, and had the laptop not reported the completion timestamp precisely I might have
carried that error into the read and quietly taken the two-bank cohort. Recorded as an error of mine.

## CORRECTION (same day, before the read): I had the cost backwards

My first statement of this said reading 990 alone "makes a DOUBLING verdict harder to reach." **That is wrong and is
retracted.** Checked against the reader and the frozen text:

1. **Amendment 2 already set this cohort to one bank.** *"Operator decision: one bank (990), not two. The reader takes
   one run; the DOUBLING rule's per-bank clause collapses to the pooled ratio."* Reading 990 alone is therefore the
   preregistered design, not a degraded fallback. Bank 991 was an addition whose inclusion was conditioned on the
   deadline.
2. **The two-bank route is strictly HARDER, not easier.** `prereg099_report.py` line 218 requires
   `lo >= 1.7 AND all(per-bank ratio >= 1.5)`. Under `990-alone` that is one bank; under `both` bank 991 must
   independently clear 1.5 as well. The deadline rule says as much: the two-bank cohort *"additionally requires each
   bank's own ratio ≥ 1.5."* An extra necessary condition cannot make a verdict easier.
3. **Pooling adds no independent evidence about the world.** The bootstrap resamples **slates** (18 under amendment 4)
   with both banks of a slate moving together. The number of resampled units is 18 either way. A second bank reduces
   only the within-slate Monte Carlo noise of each slate's contribution; it creates no additional NFL slates or seasons.

**So the honest cost of `990-alone` is small and possibly negative.** It is the preregistered estimator, on the same 18
clusters, with one fewer necessary condition. What is genuinely given up is the extra Monte Carlo precision and the
corroboration value of an independent bank clearing the floor on its own.

Bank 991 is not wasted either way: the frozen rule sends it to `LEDGER.md` as a separate replication row, so its
numbers are still read and reported — just not pooled into the primary verdict.

## The operator may override this; I recommend he does not

Protocol decisions are the operator's. He can direct a two-bank read and I will run it. My recommendation is against,
for one reason: every frozen gate in this program derives its force from the fact that we have never once bent one
after the fact, including when bending was cheap and obviously convenient. Sixteen seconds is the cheapest possible
bend and therefore the most expensive precedent.

If he overrides, the read must record that it was an override of the frozen deadline, with these timestamps, and the
LEDGER row must say so.

## Execution, unchanged otherwise

When 990's last shard lands: commit the untracked `run_119_local_v4.sh`, read ONCE with
`--rule 990-alone`, record in `PREREG-099.md` and `LEDGER.md`, commit, push, report the verdict and supply ratios.
The amendment-5 reader cherry-pick was conditioned on the two-bank route and is **not** applied under this rule;
amendment 2's reader governs, exactly as the frozen text says.
