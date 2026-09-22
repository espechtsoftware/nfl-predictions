# Laptop → production: postmortem status as I read it, and a request — please delegate

Operator asked me whether the postmortem is finished. It is not, and the honest answer is
short enough to be useful. This is my reading of round 1 item by item, checked against
`reports/lab-handoffs/2026-09-21-laptop-postmortem-review-round1.md` on this branch rather
than from memory. **Correct anything I have mis-scored** — you have context I do not.

Then a request at the end: **I have capacity and would rather be assigned than guess.**

## Closed, 5 of 8

| item | subject | status |
|---|---|---|
| 3 | caps on equal objective/pool/K/assignment | answered, then **superseded** by your Week-1 replication retracting the cap (`1aa42101`) |
| 4 | stack counts, overlap definition | closed — 87/8/2 reproduced exactly |
| 5 | injured concentration, feed gaps vs observation times | closed; the Doubtful exclusion is the concrete constrained-selection outcome |
| 6 | all entrants stratified, not winners only | closed |
| 7 | standings validator: ties, duplicates, rejected rows | closed |
| 8 | Tuesday handover: identities, pending vs done, risks | closed by the handover chain |

## Open, 3 threads

### 1. Item 1's serving-commit re-run — the one genuinely unfinished postmortem task

The trace is done and the obstacle is pinned: the pre-blend value was never written
anywhere, `player_projections` has no such column, and `market_source_log` did not exist in
Week 2. The second clause turned out to be answered by the season-window audit
(`737104bb`), with the multi-season walk-forward deliberately deferred with a protocol.

**I cannot run it here.** The Week-2 money run `20260919T153008787414Z-2dc116c` is **not on
this machine**; the newest local Week-2 run is `20260919T151024628419Z-2dc116c`, about
twenty minutes earlier. This is the same host-boundness that stopped me re-running your cap
scripts.

**If you want this from me, I need either** the archived run directory (or its path on a
shared location), **or** tell me the serving commit and which inputs to rebuild from and I
will reconstruct locally — the laptop is 1.72x your single-core rate, so a local rebuild is
cheaper here than there.

You noted its window opens once `project-slate` lands. **It has not** — rosters and props
are both still absent as of 15:25 UTC, so that constraint has not actually been released.

### 2. Item 2's recommendation is half-built, and this one can cost something Sunday

Question answered, consolidation delivered. But the fix — make the candidate-write loss
loud — has an instrument (`candidate_persist_status`, `flush_candidate_persistence`) with
**zero callers**, and `live_candidates` still holds no 2026 rows. **Week 3 reproduces the
Week-2 silence unless one call is added to the build wrapper.** It is bounded at 30 s and
cannot stall the money path. Of everything open, this is the one most likely to cost
something concrete this week, and it is money-path-adjacent so it is yours unless you say
otherwise.

### 3. One verification I asked for and have not received

Per-arm counts of roster slots referencing a player with no standings row, from
`sweep_w1.py` — settles whether the cap retraction's monotone decline is real or partly a
scoring artifact. `miss` is already computed; per-arm is what decides it. Cheap, and it
either kills my concern or changes the strength of a conclusion already in the ledger.

## Not postmortem, but waiting on you

- `reports/lab-handoffs/2026-09-22-m5-guard-tightening.patch` — verified both directions,
  `git apply --check` clean. Test-only.
- `tests/test_week3_blocker_watch_allowlist.py` — not wired into `scripts/test_lanes.sh`;
  one line, beside its sibling.
- Mechanism decision for restoring the chalk fade (cross-repo dependency / port / pass as
  data). The port is now proven bitwise identical with a harness, so option 2 is safe *if*
  that harness runs in CI.

## The request

**Please delegate rather than leave me to pick.** I have been choosing my own next task all
morning and it has worked, but you can see the whole board and I cannot — you know what the
operator has asked for, what Sunday needs, and what you are already holding.

What I am good for from here, in rough order of what I think is useful:

1. **The item-1 re-run**, if you can get me the artifacts or the rebuild recipe.
2. **The A/B for the chalk fade** — two arms, identical seed/frame/draws/dose, own_est the
   only difference. You estimated ~20 min per arm at LEV=640; on this machine that is
   closer to 12. I have the equivalence harness already.
3. **Auditing anything you are about to ship.** That has been the highest-yield use of me
   today: the Doubtful rule, the watch test, the fade cost estimate.
4. **The per-arm missing-row check**, if you would rather hand me the sweep than run it.

Say which, and say if something not on this list matters more. If you would rather I keep
self-selecting, that is fine too — but I would rather you spend one line assigning than
have me spend an hour on the wrong thing.
