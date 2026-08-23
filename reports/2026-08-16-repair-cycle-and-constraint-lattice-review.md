# Review: ATLAS repair cycle, resource diagnosis and the constraint lattice

Date: 2026-08-16. **No code was changed. No outcome was queried.**

Covers everything since the CBC review: the native and cgroup resource
diagnostics, the 16 GiB preflight, repair3/4/5, the high-tail guard amendment,
the continuous-parity fallback, and the new constraint-lattice protocol.

**Two confirmations, one process finding that is now the binding constraint on
the whole programme, one standing-law violation in the new protocol, and one
minor evidence defect.**

---

## 1. Confirmed: the resource diagnosis worked and the answer is decisive

The instrumented diagnostic returned exactly what was needed:

| cell | child | peak / 4 GiB |
|---|---:|---:|
| 2024 Week 7 | `-9` / **SIGKILL** | 84.24% |
| 2024 Week 15 | `0` — completed | 82.11% |
| 2024 Week 16 | `-9` / **SIGKILL** | 84.38% |

Two SIGKILLs at ~84% of cap, a clean MPS parse, and a native log ending
mid-pass. Combined with 2023 Week 8's later explicit *"The configured memory
limit was reached"* at **16 GiB**, memory is established.

The `sigkill-without-cgroup-oom-confirmation` label is the right level of
restraint. Cloud Run exposed only the cgroup-v1 `failcnt` interface, not v2's
`oom_kill` counter — my recommendation assumed v2 and the fallback was handled
honestly rather than by overclaiming. Including Week 7 closed the gap I flagged.

**Confirmed separately: the high-tail guard amendment.** It adds no-decline
guards at 220/230/240, keeps the 200 anchor and the `single-event-extreme-tail`
label, and — the part that matters most — **explicitly discloses that the 200
anchor was informed by prior CBWU-OI results on the same panel.** The regression
test proving that two added 200-weeks plus one lost 230-week cannot earn the
positive label is the right way to make a gate real rather than declarative.

## 2. The binding constraint is now the execution contract, not the science

This is the item I would act on before launching anything else.

Four consecutive grids have produced no science:

| grid | envelope | outcome |
|---|---|---|
| repair2 | 1 CPU / 4 GiB | SIGKILL on 3 cells |
| repair3 | 4 CPU / 16 GiB | **all 54** failed on a hard-coded `SHARDED_OUTPUT_PREFIX` constant |
| repair4 | 4 CPU / 16 GiB | 1 natural memory failure, 47 cancelled, **6 `Internal error running task`** |
| repair5 | 8 CPU / 32 GiB | pending, same contract |

Only repair2 failed for a reason worth learning from. The other three were lost
to a string constant, an infrastructure error class, and the cascade rule that
one failure voids all 54.

**The arithmetic is the problem.** With an independent per-cell infrastructure
failure probability `p`, a zero-retry 54-cell grid completes with probability
`(1-p)^54`:

| per-cell failure rate | P(clean 54-cell grid) |
|---:|---:|
| 1% | 58% |
| 2% | 34% |
| 5% | 6% |
| 11% (repair4's 6/54) | ~0.2% |

Some of repair4's six internal errors may be cancellation artifacts, so treat
11% as an upper bound. **But even 1–2% makes a clean grid a coin flip**, and the
contract is about to be applied to repair5 *and* the constraint lattice — two
more 54-cell zero-retry populations.

**The fix costs nothing scientifically.** Each cell is an independent shard with
a pinned image, pinned code, deterministic computation and create-only output. A
retry of a cell that wrote **zero objects** cannot select a favourable result —
it either produces the identical deterministic object or fails again. Create-only
is preserved precisely because the failed cell left nothing behind. So the
zero-retry rule buys no protection against outcome-shopping, which is the only
thing it could be guarding, while guaranteeing repeated total-grid loss.

**Suggestion:** permit exactly one mechanical retry per cell, admissible **only**
when the cell is terminal-failed with zero objects written and a non-solver
terminal reason, with both execution IDs receipted. This was already the
intended design once — the CBC protocol's second branch proposed *"repair3 with
one predeclared mechanical retry per cell"* — and it was dropped. It should come
back.

## 3. The preflight-generalisation gap is narrowed but still open

My earlier concern was that the 16 GiB preflight validated 2024 Week 15 — a cell
that had **already succeeded at 4 GiB** — and so demonstrated nothing about the
failing cells. repair4 then failed on 2023 Week 8 at that same 16 GiB envelope.
Preflighting the actual worst known cell at 32 GiB is the right correction.

The residual issue is spread. Week 15 peaked at **3.52 GB**; 2023 Week 8 exceeded
**16 GiB**. That is a **greater than 4.5× range**, and only **4 of 54 cells** have
ever been memory-probed. Preflighting the worst *known* cell does not bound the
worst *unknown* cell.

**And repair5 will run blind.** It pins the repair2 image `sha256:ce03feb…` and
code `60f296f` — which predates the cgroup instrumentation. That instrumentation
exists only in the diagnostic runner. So if a repair5 cell dies, the receipt will
again say `NonZeroExitCode` with no peak, no signal and no margin.

**Suggestion — no image change required.** Harvest **Cloud Run / Cloud Monitoring
peak memory per execution** for all 54 repair5 cells post-hoc, as a
metadata-only step in the strict finisher. It is outside the container, touches
no outcome, and yields a complete per-cell margin table for free. If the
observed maximum lands near 32 GiB, the next grid is already known to be at
risk; if it lands at 12, the envelope question is closed permanently.

## 4. The constraint lattice freezes a cell-dependent gate with no support census

The lattice is a real methodological advance — the first arm here to use
**held-out simulated blocks**, so the swap rule cannot be chosen on the block
that measures it. The p230-anchored gate is also genuinely tail-first, better
aligned with the objective than the ATLAS historical rule. Both are improvements.

**But the gate violates a standing project law.** CLAUDE.md:

> **Preflight support before freezing cell-dependent gates.** When a proposed
> protocol requires minimum counts in calibration cells, run an outcome-blind
> support census first and record the eligible row/event counts for every
> required cell.

The gate requires aggregate held-out p230 coverage to **strictly improve** and to
improve in **at least 3 of 5 folds**. The admission rule states outright that
*"One world is the exact finite-sample margin"* — so the operative quantities are
counted in single worlds out of 10,000.

**No p230 support census was recorded before the gate was frozen.** If control
p230 book coverage runs at, say, 3–30 worlds per fold, then "improves in ≥3 of 5
folds" is close to a coin flip and the diagnostic is underpowered before it
starts.

The cost of skipping it is unusually high here, because the protocol says a
failure *"closes this exact v1 design; its cells, quotas, world ranker,
admission margin and gate may not be swept on the same 54-slate simulation
panel."* **An underpowered null would permanently close a design that might have
worked.**

**Suggestion:** run the census first. It is entirely score-free — simulated
coverage on the immutable native books, no outcomes — and cheap. Record control
p230/p210/p194 book coverage per fold and per slate, then confirm the 3-of-5
condition is powered at the observed magnitudes. If p230 support is too thin,
re-anchor the gate *before* freezing rather than discovering it afterwards. This
is exactly the situation the law was written for.

**Second, smaller point on the same protocol.** Held-out blocks control **Monte
Carlo noise, not model misspecification.** Five seeds of the same simulator on
the same slates share any dependence-structure error, so a mechanism that
exploits such an error passes all five folds. A pass certifies *"not
seed-overfit"*; it does not certify transfer. Given that Schaake, three Gumbel
variants, CE and fast-role all satisfied simulated criteria and then failed, the
consequence boundary should name this explicitly. The narrow license — a 2026
pre-lock shadow only — is already right; the reasoning should be stated with it.

**Third:** the lattice inherits the §2 contract *and* picks 16 GiB, the envelope
that just failed on ATLAS. Its workload differs (exception MILPs, no large
interaction blocks), but it has **no memory data at all** and up to 400 raw
proposals per slate. A single full-cell resource preflight before the 54-cell
launch would cost one execution and is the lesson repair3/4 already paid for.

## 5. Minor: a malformed hash in durable evidence

[2026-08-16-atlas-repair4-terminal-census-result.md](reports/2026-08-16-atlas-repair4-terminal-census-result.md)
records the empty object-inventory SHA-256 as:

```
e3b0c44298fc1c149afbf4befc8996fb92427ae41e4649b934ca495991b7852b855   (67 chars)
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855      (64, actual)
```

Verified with `printf '' | sha256sum`. The value itself is inconsequential — it
is an empty inventory — but **a 67-character hash cannot have come from a hash
function**, so that evidence line was hand-transcribed.

In a programme whose entire audit chain is hashes, durable-evidence blocks
should be machine-emitted. Worth a quick check of whether other evidence lists
are transcribed the same way, since a transcribed hash that happens to be the
right *length* would not announce itself.

---

## 6. Summary

| # | item | priority |
|---|---|---|
| 1 | **Permit one mechanical retry per zero-object, non-solver cell failure.** Four grids lost, three to non-scientific causes; at even 1–2% per-cell infra failure a clean 54-cell zero-retry grid is a coin flip. Determinism + create-only means a retry cannot shop outcomes | **highest — before repair5 and the lattice** |
| 2 | **Run the p230 support census before the lattice gate is frozen** — standing CLAUDE.md law; an underpowered null permanently closes the v1 design | **highest** |
| 3 | **Harvest per-execution peak memory for all 54 repair5 cells** from Cloud Monitoring; no image change, and repair5 is otherwise blind | high |
| 4 | Full-cell **resource preflight for the lattice** before its 54-cell launch; it picks the envelope that just failed on ATLAS with no memory data | high |
| 5 | State in the lattice boundary that held-out blocks control **MC noise, not misspecification** | medium |
| 6 | Machine-emit durable-evidence hashes; one recorded value is 67 characters | low |

The resource diagnosis and the high-tail guard are both closed correctly.
Nothing here blocks the running 32 GiB preflight — items 1 and 3 apply to the
repair5 launch that follows it, and item 2 applies before the lattice gate is
treated as frozen.
