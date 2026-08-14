# Phase S failures: diagnosis and operational recommendations

Date: 2026-08-13. Review of the Phase S execution failures.
**No code was changed. No outcome was read.**

---

## 1. The science is not affected — say this first

Every Phase S failure is **infrastructural**. None is a scientific failure, and
none creates a contamination risk:

- retries are byte-identical, with no arm, config, seed, feature or code change;
- the replay pipeline is deterministic, so a retried cell produces exactly what
  the failed cell would have produced;
- every failed cell wrote **zero** candidate rows, feature rows and artifacts —
  there is no partial state to reconcile;
- `analyze_sis_asoe_phase_s.py` fails closed on an empty frame
  (`if frame.empty: failures.append(...)`), so a zero-row execution cannot pass
  into a result even if one were mistakenly harvested.

The cost is money and calendar time, not validity. That distinction matters
because the *volume* of failures is alarming in a way the *consequence* is not.

## 2. Four failure modes, one root cause

| mode | cells | signature |
|---|---:|---|
| failed before application startup | 3 | zero application logs, zero rows |
| truncated SciPy shared library (`file too short`) | 1 | failed before replay import |
| BigQuery Storage internal 500 | 2 | before first replay write |
| `Internal error running task`, **exit code 0** | 14 | ~30 min, zero logs, zero rows |

**Twenty of thirty cells — a 67% infrastructure failure rate.** That is not bad
luck. All four signatures are consistent with a single cause: **a 30-cell
concurrent burst contending for the same image registry and the same BigQuery
Storage API.**

The truncated shared library is the diagnostic one. `file too short` on a
numeric library is an **image-materialisation failure**, not a code defect — it
is what a partially-realised layer looks like, and it happens under registry
pressure when many replicas pull the same large image simultaneously. Startup
failures with no logs and 30-minute `Internal error` terminations are the same
pressure expressed differently.

`cloud_sis_asoe_phase_s.sh` does stagger, but by `sleep 30`. Thirty cells at
30-second intervals are all in flight within fifteen minutes, and the
long-running ones overlap completely. Staggering the *launch* does not limit
the *concurrency*.

## 3. The highest-severity item is not a crash — it is the manual ledger substitution

Twenty failures each require the operator to move a row from
`pending_infrastructure_retries.txt` into `infrastructure_retries.txt` and
substitute a new execution ID into `executions.txt`.

That is **twenty opportunities to substitute the right ID into the wrong cell.**

In an ordinary panel a mix-up would likely surface as a mechanical
inconsistency. Phase S is a **5-seed × 2-arm × 3-season factorial**, and a
mis-assigned cell would attribute one seed's output to another seed's slot.
Every row would still be internally valid — correct schema, correct counts,
correct invariants — while silently corrupting exactly the two quantities the
factorial exists to estimate: the seed-variance envelope and the interaction
term. No existing invariant check would catch it.

**Recommendation, and I would treat this as the one blocking item:** have the
analyzer verify each execution's *own* recorded `(arm, seed, season)` from its
manifest against the cell it is being read into, and hard-fail on mismatch.
Trust the artifact's self-description, not the ledger file that a human edited
twenty times under retry pressure.

## 4. Operational recommendations

### 4.1 Cap in-flight concurrency instead of staggering launches

Replace `sleep 30` between launches with a **maximum-in-flight cap** — poll and
release a queued cell only as an active one finishes. Eight to ten concurrent
cells is a reasonable starting point given the observed contention.

This is precisely the manual procedure the handoff already prescribes
("release queued byte-identical retries in small batches only as active slots
finish"). It should be a loop in the runner, not an instruction to a person —
which also removes most of §3's substitution exposure, because the runner can
write the ledger itself.

### 4.2 Retry BigQuery Storage 500s inside the application

A transient 500 *before the first write* currently kills a 30–60 minute
execution that must then be re-run from scratch. Client-level exponential
backoff on the Storage read path is standard, cheap, and converts two lost
cells into two brief pauses.

### 4.3 Make the replay resumable per slate

The project already has this pattern — `9247d5d Add resumable SIS backfill
runner`. Applying per-slate checkpointing to the replay path turns a
30-minute total loss into a few-minute loss. At a 67% failure rate that pays for
itself on the first panel, and it is the difference between a burst being
expensive and a burst being unaffordable.

### 4.4 Add a numeric-stack self-check at startup

The `file too short` failure was lucky: it failed loudly, before the replay
import. The same pull corruption could in principle materialise a *subtly*
broken numeric library rather than an unloadable one.

An immutable digest pins **which** image runs; it does not guarantee every layer
materialised intact on a given replica. A few-second startup assertion —
import the numeric stack, run a fixed computation, compare against a hardcoded
expected value, exit non-zero on mismatch — closes that gap deterministically
and would have converted this failure into a clean, self-explaining one.

### 4.5 Check image size and registry locality

Registry throughput is the shared resource behind at least two of the four
modes. Confirm Artifact Registry is co-regional with the jobs, and check whether
the runtime image can be slimmed. Both reduce the pressure that produced these
failures rather than retrying through it.

## 5. What was handled well

Worth recording, because the response to these failures was disciplined:

- every retry byte-identical, with no configuration drift;
- zero-row failures correctly classified as *no result*, not partial results;
- the refusal to burst-launch all fourteen queued retries at once, on the
  correct reasoning that six earlier retries plus ten original cells already
  occupy capacity;
- durable provenance for every substitution rather than a silent re-run.

The instinct throughout was right. The gap is that the correct procedure is
being executed by hand, twenty times, in exactly the place where a hand error
would be least detectable.

---

## Recommended order

1. **§3 manifest-verified cell assignment** in the analyzer — blocking, because
   it protects the factorial's two headline quantities from the one error mode
   that would not otherwise surface.
2. **§4.1 in-flight concurrency cap** in the runner, with the runner owning the
   ledger — removes both the contention and most of the manual exposure.
3. **§4.2 BigQuery retry** and **§4.4 startup self-check** — small, and each
   eliminates a mode already observed.
4. **§4.3 resumability** before the next multi-cell panel.
5. **§4.5 image/registry check** as background work.
