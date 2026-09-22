# Laptop review item 2: you were right about `own_shadow`, and the authoritative record is empty too

Answering the sub-question in item 2 of
`handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Separate missing telemetry from missing money-path inputs (**zero
> `own_shadow` does not alone prove which ownership input generation
> consumed**).

Confirmed, and then the trail leads somewhere worse.

## 1. `own_shadow` is telemetry. Its emptiness proves nothing.

`live_lineups._log_ownership_shadow`, by its own docstring, is a *"best-effort
asynchronous capture of the irrecoverable live own vector."* The write is
wrapped so failure is swallowed:

```python
except Exception:
    log.exception("own-shadow write failed")
```

It is write-only — nothing reads it back into generation. An empty table means
the **logger** did not run or failed. That is a telemetry fact and carries no
information about the money path. Your caution was exactly right.

## 2. The authoritative record exists, and names the lever precisely

What generation consumed is recorded as `OWN_MODEL` inside `lever_env` on each
row of `nfl_predictions.live_candidates`. `OWN_MODEL` is one of the **125 lever
keys** in `engine._lever_keys`, alongside the whole `OWN_BARBELL_*` family and
`MIN_LOWOWN`. The adopted policy sets `OWN_MODEL: ""` — the naive fade —
in `production_policy.py:247`.

So the question is answerable in principle, from the candidate rows, not from
`own_shadow`.

## 3. Except `live_candidates` has no 2026 rows at all

| season | week | rows | most recent write |
|---|---|---|---|
| 2024 | 3 | 20,665 | **2026-09-21 01:57** |
| 2022 | 1 | 124 | 2026-08-05 |

**20,789 rows total, none from 2026.** The Week-2 book's generation levers were
never persisted, so neither source can establish what generation consumed.

Worse, the 2024-week-3 rows were last written **today**. That is the synthetic
offline-run contamination — the same class that put 18,185 synthetic rows into
`own_shadow` and prompted the autouse warehouse guard. The table meant to hold
the irrecoverable production record instead holds test output.

## 4. Why it is empty, and why nobody noticed

```python
cand_log_async:    bool = True     # fire and forget
cand_log_required: bool = False    # failure does not stop the run
```

Those are the live-path defaults. Only `prospective_latent_role.py` overrides
them to `async=False, required=True`.

The async choice is **deliberate and defensible** — `engine.py:2411` explains
it: *"cand_log_async=True so a stalled warehouse call can never block"* the
money path. Nobody wants a Sunday build hanging on a telemetry write.

But the consequence is that the record described in the same codebase as
*"irrecoverable post-build"* is the first thing dropped under failure, and
drops **silently**. Two independent post-build records — `own_shadow` and
`live_candidates` — are both best-effort, and both are empty for the week we
most need to explain.

## 5. Recommendation: make the failure visible, not necessarily fatal

We would **not** simply flip `cand_log_required=True`. That trades a silent
telemetry loss for a possible money-path stall, which is the worse failure on a
Sunday, and the async design was chosen for that reason.

The cheaper fix is to make the loss **loud**: have the build receipt record
whether the candidate write succeeded and how many rows landed, so a missing
record is visible at build time rather than discovered a week later during a
post-mortem. That keeps the money path unblockable while ending the silence.

**Week 3 will otherwise reproduce this exactly.** The levers that produced
Sunday's book will again go unrecorded, and the next post-mortem will again be
unable to say which ownership input was used — which is precisely the question
you asked.

## Status of item 2

The sub-question is **answered**: telemetry and money-path input are distinct,
`own_shadow` is the former, `lever_env` on `live_candidates` is the latter, and
neither holds a 2026 row. The broader item 2 — per-bug introduced commit,
reproducer, affected outputs, regression test and fixed-path replay — is a
consolidation we have partly done per-defect (the composite-ordering defect
carries all five at `3a942f49`) and have not yet collated into one table. Say
if you want that next, or if the receipt change above is the better use of the
time before Sunday.
