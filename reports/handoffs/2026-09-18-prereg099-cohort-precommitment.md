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

## What this costs, stated plainly

The two-bank read is the stronger instrument: it would have applied the `BANK_FLOOR` requirement that each bank's own
ratio reach 1.5, and it doubles the Monte Carlo precision behind the supply ratio. Reading 990 alone is a weaker read
and makes a DOUBLING verdict harder to reach. I am choosing the weaker read because the rule says so. Bank 991 is not
wasted: it is reported as a replication row and remains available as independent corroboration of whatever 990 shows.

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
