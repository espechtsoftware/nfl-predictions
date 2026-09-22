> # CORRECTED 2026-09-22 — the 99.9% headline was a DST artifact, and the attribution IS measurable.
>
> Both definitions I used here counted **defenses** as phantoms: a DST has no row in
> `snap_counts` (offensive snaps belong to players), so "projected ≥ 5 and zero snaps" caught
> **23 of the 26 DSTs**. Every lineup rosters exactly one DST, so contamination read 99.9%.
>
> Excluding DSTs (`reports/lab-handoffs/phantom_contamination.py`):
>
> | | value |
> |---|---:|
> | genuine phantoms | **38** (QB 22, WR 8, RB 5, TE 3) |
> | pool share carrying ≥ 1 | **63.8%** (not 99.9%) |
> | zero-phantom control group | **4,543** candidates (not 14) |
> | Spearman(sel_mean, realized), all | −0.4908 |
> | Spearman, zero-phantom candidates | **−0.3449** (p = 4.7e-127) |
>
> **Availability accounts for about 30% of the inversion; about 70% is something else**
> (players who played and were mis-projected — the Jefferson stand-in is the named case).
> That restores, with a better number, the "about a quarter" I first reported in `ce932e77`
> and then withdrew here as unmeasurable. The monotone table below survives unchanged in shape.

# 99.9% of the Week-2 pool contained a player who never took a snap — which is why
# the availability share of the inversion cannot be cleanly estimated

Delivers the check I said I owed in `ce932e77` ("the clean test is snaps per player-week,
which I have and will run next"), and **corrects my own decomposition in that report.**

## 1. The promised check: is the "dead" cohort really absent?

Of the 37 players projected ≥ 5.0 who scored exactly 0.0:

| | n | share |
|---|---:|---:|
| **took zero offensive snaps** (truly absent) | **27** | **73.0%** |
| took snaps and scored nothing (played, busted) | 10 | 27.0% |

So the cohort is mostly availability, not mostly bust — but not purely. And the split is
almost entirely positional:

| pos | in cohort | of those, zero snaps | mean projection |
|---|---:|---:|---:|
| **QB** | **24** | **22** | 11.68 |
| RB | 2 | 2 | 7.87 |
| TE | 4 | 1 | 6.95 |
| WR | 7 | 2 | 9.49 |

**22 of the 27 genuine absences are quarterbacks.** The TE and WR members mostly *played*
and simply busted — Marvin Harrison Jr. took 37 snaps, Jeudy 34, Mason Taylor 34. That is
projection error, a different defect. **The availability problem in this pool is a QB
problem, which is exactly what production's gate targets.**

## 2. The correction: my "quarter of the inversion" number is not a clean attribution

In `ce932e77` I reported that restricting to candidates carrying none of these players moved
Spearman from −0.4908 to −0.3720, and called that availability explaining about a quarter of
the inversion.

**That decomposition used the 37-player definition, which mixes 27 absences with 10 busts.**
Tightening it to *measured absence* — projected ≥ 5, zero snaps, and present in the standings
export so the zero is observed rather than imputed — gives 44 such players and:

| control group | n candidates | Spearman |
|---|---:|---:|
| all candidates | 12,555 | −0.4908 |
| carrying zero absent players | **14** | −0.5341 (p = 0.049) |

**Fourteen candidates.** There is no control group, so the attribution cannot be computed.
My −0.37 figure should not be quoted as "availability explains a quarter of the inversion";
it is the correlation among candidates free of a *mixed* cohort, which is a different and
much weaker claim.

## 3. The reason there is no control group is itself the finding

**99.9% of the 12,555 candidates contain at least one player who was projected ≥ 5.0 and
never took an offensive snap.**

Not a majority. Essentially all of them. Only 14 lineups in the entire pool were free of a
phantom, and that is why the decomposition has nothing to compare against.

## 4. What survives, and it is the part that matters

The monotone relationship is robust — it holds under **every** definition I tried (37-player
mixed, 61-player raw, 44-player measured):

| absent players in lineup | n | mean realized | **mean simulated** |
|---|---:|---:|---:|
| 1 | 5,316 | **103.24** | 122.45 |
| 2 | 5,186 | 88.57 | **126.83** |
| 3 | 1,763 | 81.43 | **127.73** |

**More phantoms → lower realized score → higher simulated rating.** Every time, under every
definition. The mechanism is not in doubt; only its *share* of the −0.49 is, and on this
slate that share is unmeasurable because there is no uncontaminated population to compare to.

## 5. What this means for the week

The pool the money path selected from was, essentially in its entirety, built on at least one
body that was not going to play. Production's QB gate removes 364 projection points that
produced 13 — and §1 says 22 of the 27 genuine absences were QBs, so **the gate is aimed at
the right 80% of the problem.**

Measuring what the gate does to the inversion needs a pool *regenerated* with the gate on.
That is a rerun, not a re-analysis, and it is the honest way to get the number I tried to
estimate here.

**Week 1 would also give a real control group** if its contamination is lower, which is the
second reason that candidate file is the most valuable thing outstanding.
