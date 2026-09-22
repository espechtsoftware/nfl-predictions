# Doubtful is absence, not ambiguity — and the ATL miss had a different cause

Operator approved treating Doubtful as absence. Implemented, tested, and then measured
on the real frame — where it turns out to be a **no-op**, for a reason that matters more
than the refinement.

## The refinement, as approved

`find_backup_qbs` treated Doubtful and Questionable as one "ambiguous" class and skipped
the whole team. The laptop's snap-count review separates them: **13 of 13 Doubtful
player-weeks took zero offensive snaps and scored zero**, while Questionable played
**77.4%** of the time. The rule is right for Q and was wrong for D.

A Doubtful QB is now **unavailable**: he cannot be the primary, he is zeroed himself, and
the next available QB is promoted so his backups stop carrying inflated projections.
Questionable still makes a team ambiguous. `QB_DOUBTFUL_ABSENT=0` reverts it without a
redeploy. Tests: **15 pass**, including the ATL/Tua shape, the tie-order boundary in both
permutations, that Q is still ambiguous, and the kill switch.

## But it does not fire on Week 2, and the laptop's attribution was wrong

The review says *"Atlanta's depth-1 was Out, promoting a Doubtful depth-2 to primary, so
the team was declared ambiguous."* On the actual served frame that is not what happened.
ATL's QB rows are:

| player | depth | status | proj |
|---|---:|---|---:|
| Tua Tagovailoa | 2 | **D** | 17.47 |
| Cooper Rush | 3 | — | 14.44 |
| Jack Strand | 4 | — | 2.56 |

**There is no depth-1 row.** Penix is not on the DK slate at all, so ATL is skipped by
the earlier `no depth-1 on file → nothing gated` guard, *before* the ambiguity rule is
ever reached. Verified by running the gate both ways on the archived frame: 38 QBs
zeroed, 304.1 points, 28.0% of pool — **identical with `QB_DOUBTFUL_ABSENT` on and
off**, and Tua ungated in both.

## The real residual gap

Teams with no depth-1 QB row are ungated **entirely** — every backup keeps its full
projection:

| | teams with no depth-1 QB | pool lineups affected |
|---|---|---:|
| Week 1 | 1 of 24 (ATL) | 8 of 3,200 (0.2%) |
| Week 2 | **3 of 26 (ATL, MIN, SEA)** | **1,068 of 12,555 (8.5%)** |

These are precisely the three teams the propagation report listed as "untouched, by
rule" — the rule doing the untouching is the depth-1 guard, not the promotion logic.

**Not changed here, deliberately.** Promoting the shallowest QB present when depth-1 is
missing is defensible — a QB absent from the DK slate cannot be rostered and is very
likely not playing — but it is a different rule from the one approved, it weakens a
guard that exists to protect against data gaps, and it has no measurement behind it yet.
It should be proposed with evidence, not slipped in alongside an approved change.

## Shipping recommendation

The image built and deployed today (`08909616`, all three steps green including the
boundary tests that now cover the gate) does **not** contain this refinement. Since the
refinement is a measured no-op on both available slates, there is no reason to rebuild
for it — it should ride the next build. The deployed gate is the substantive change:
38 QBs zeroed, 28.0% of pool, precision 89.6% / recall 87.8% against snap counts.


---

## Addendum (same day): the depth-1 gap is now closed too

Measured "promote the shallowest QB present" on both released weeks for every team that
lacked a depth-1 row:

| team-week | promoted | played? | gated | proj removed | those QBs scored |
|---|---|---|---|---:|---|
| W1 ATL | Cooper Rush | yes, 7.7 | Strand | 2.50 | 0 |
| W2 ATL | Cooper Rush | yes, 2.4 | **Tua**, Strand | 20.03 | Tua **0**, Strand 2.0 |
| W2 MIN | Carson Wentz | yes, 6.3 | McCarthy | 15.91 | 0 |
| W2 SEA | Drew Lock | yes, 21.4 | Milroe | 2.34 | 0 |

**Promotion correct in 4 of 4 team-weeks**, and **38.22 of the 40.78** projection points
removed came from QBs who scored exactly zero — **93.7% precision**, against 89.6% for
the deployed depth-1 path. Implemented behind `QB_NO_DEPTH1_PROMOTE=1`, 17 tests pass.

Combined effect of both refinements on the archived frames:

| | QBs zeroed | proj removed | pool lineups affected | Tua gated |
|---|---:|---:|---:|---|
| Week 2, deployed image | 38 | 304.1 | 3,514 (28.0%) | no |
| **Week 2, with both** | **42** | **342.4** | **3,891 (31.0%)** | **yes** |
| Week 1, deployed | 38 | 269.4 | 651 (20.3%) | n/a |
| Week 1, with both | 39 | 271.9 | 651 (20.3%) | n/a |

**This changes the shipping recommendation.** The Doubtful refinement alone was a no-op
and did not justify a rebuild; together with the depth-1 promotion it is worth one, and
the two share a single build. `project-slate` has still not run for Week 3, so it is in
time.

## Also verified, no change needed

`nfl2/scripts/live_week.py` defaults `--selector` to **`cov194`**, a threshold-keyed
selector at 194 — precisely the objective the calibration work shows is wrong by 146x in
Week 2. **`sunday_build_host.sh` passes `--selector dual_emax` explicitly on both bank
invocations**, so Sunday is safe. Recorded as a latent hazard: the safe path is guarded
only by the call site, and a manual invocation of `live_week.py` would silently select on
a threshold the simulator cannot calibrate.
