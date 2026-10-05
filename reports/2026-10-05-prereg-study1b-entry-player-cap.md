# Preregistration: study 1b, an ENTRY-level player exposure cap (FROZEN 2026-10-05)

This is the design the reviewer accepted on 2026-10-05, frozen before any experiment, driver or reader is built. From
here on, any change is a dated deviation note appended below. The text above it is never edited.

**The operator's request (10-04, HANDOFF 13:18):** "since we're using the same lineups in many contests, I end up
having people like Chase in 50% of my lineups … I think we should consider restricting that further."

## Why
- Week 4 held each player to 52 of 105 book ROWS. The head layout deals the top rows into many contests, so ENTRY
  exposure went far higher:
  - Chase: 74 of 152 entries;
  - Lawrence, P. Washington and Strange: about 61%;
  - McCaffrey: 62.5%.
- Study 1's game cap did not reduce the one-player-bust exposure (0.072 → 0.080, Addendum 122). That needs a PLAYER
  cap at the ENTRY level.
- Priors:
  - L17: loosening the row cap was HARMFUL. L18: 40% was NEUTRAL.
  - The money gate's 30% ROW cap (A3) finished worse than A1 every week.
  - Concentration on chalk was +EV at the satellite lines (winners study).
  - So an EV cost is possible, and the choice may be a risk preference, as the reviewer noted.

## Arms (the same L-series books, terms and plan; co-run; fresh banks)
- **C (control):** the current book and the head layout as live: row cap 52, DST cap 26, and the small-contest overlap
  limit M = 5 with ceiling 10.
- **EA, the assignment cap at 30%:** C's book, dealt by the head layout. Then, in deal order, an entry whose row would
  push any player above 30% of the plan's mean-track entries is replaced by the next row in solve order that keeps
  every player within the cap and satisfies the contest's existing overlap rule. If none fits, the entry KEEPS its row
  and the miss is counted. The overlap rule is never relaxed: that is L25's SUPPORTED lever and would confound the arm.
  The miss rate is reported. Above 10%, EA's verdict is "the cap cannot be achieved by assignment alone".
- **EW, the entry-weighted cap at 30%, applied in selection:**
  - The sequential optimizer knows the head layout's rank multiplicities in advance (w_k = the number of plan entries
    dealt to rank k).
  - A player is banned from later solves once the sum of w_k over his rows reaches 30% of the plan's mean-track
    entries.
  - The row cap 52 and DST cap 26 still apply. The book is then dealt by the head layout as in C.
- **Exploratory, never decision-bearing:** EW at 25% and 35%, the operator's other suggested levels.

## Mechanics (fixed now, so they are not later deviations)
- **The cap base:** N = the plan's mean-track entries, after the same small-contest overlap limit as C (M = 5, ceiling
  10). The cap is floor(level × N) entries.
- **Who is capped:** every non-DST player, QB included. The DST keeps its row cap of 26. The operator's concern and
  the single-bust measure are about skill players.
- **EA's deal order:** contests in plan order, and within each contest its ranks in head order. An entry's count is
  committed when it is accepted.
  - A replacement row must not already be chosen for that contest, must keep every non-DST player ≤ the cap, and must
    satisfy the small-contest overlap rule at M = 5 in a contest that rule governs.
  - A row that has no fitting replacement keeps its original row and counts as a miss.
- **EW's rule:**
  - w_k = the number of plan entries the head layout deals to rank k, from assign_ranks before the overlap limit. That
    is the multiplicity known in advance.
  - Solve k bans every non-DST player whose entry-weighted count plus w_k would exceed the cap.
  - The realized entry exposure after the overlap limit is reported per arm.
  - If a solve finds no lineup, the book stops short. If the plan then needs a missing rank, that slate-bank is an
    error and is named, never filled.
- **Swing:** a player's median and p20 are quantiles of his own simulated draws (the run's 20,000 selection worlds).
  - The field is l02's gated sampler, FIELD_N = 200,000, re-scored with each scenario.
  - Swings are computed for every skill player in any arm's dealt entries.
- **Mechanics-only mode** writes no outcome. It records rows, deals, binding counts, EA's misses and the maximum entry
  exposure, which is what the support census reads.

## Fixed across arms
- **The ownership term:** LAG-only at λ = 0.10, as in study 1. FP ownership has no history; LineStar is avoided until
  the revision check.
- **K = 105 and the house rules.**
- **The plan:** Week 4's real mean-track contest mix, with Week 3's routed plan as a sensitivity, IF its K fits. It
  needs 106 rows against 105, so it may be unavailable, as in study 1. The reader states it either way.

## Population and banks
- L13's 36 slates (2023–24), the gated field sampler, FRESH banks 1404/1405, verified unused before any run with the
  same all-branch scan.
- The transfer check: EW and EA through the money-gate harness on the real 2026 W1–4 pools (descriptive; W4 flagged).

## Endpoints and decision rule (a risk lever: non-inferiority on finish, superiority on risk)
- **CO-PRIMARY 1, risk (superiority): the WORST SINGLE-BUST LOSS, a near-manipulation check.**
  - Per slate-bank and arm, swing_i is the arm's dealt-entry mean finish percentile with skill player i at his simulated
    MEDIAN minus the same with i at his simulated p20.
    - Everyone else stays realized.
    - The SAMPLED FIELD is rescored in both scenarios, so the swing measures exposure RELATIVE to the field.
    - Both anchors are pre-lock, so swing_i does not use i's own realized score.
    - The median is the typical outcome of a skewed DK-points distribution; the mean would mix in the boom tail.
  - WSB = max_i swing_i over the arm's OWN skill players. This is symmetric: each arm is judged on its own most damaging
    player, not on C's.
  - Rule: WSB(arm) − WSB(C) < 0, with the one-sided upper bound below 0 and both seasons favourable.
  - **Stated plainly:** a cap lowers WSB largely BY CONSTRUCTION. Co-primary 1 therefore mainly checks that the cap
    really cut single-player exposure in ENTRY terms, including through correlated teammates. The DECISION-bearing
    question is co-primary 2, the cost in mean entry finish. That is what the operator is buying: less single-player
    risk, at a measured cost.
  - Why not the expected bust loss (Σ_i swing_i, the first revision): every entry holds 9 players whatever the arm.
    Shifting exposure between players with similar median−p20 spreads leaves the sum nearly unchanged, so it measures
    mean bust loss, not concentration. It is reported as a secondary.
- **CO-PRIMARY 2, cost (non-inferiority):** the dealt-entry mean finish percentile, arm − C. The one-sided lower bound
  must sit above −m.
  - **m = 0.020 (2 percentile points), the OPERATOR'S choice (2026-10-05, a risk preference).**
  - Power at a true Δ of 0 / −0.005: about 0.96 / 0.77 for EA (P4-like), about 0.82 / 0.55 for EW (G-like), and 0.43 at
    Δ 0 if EW is as noisy as study 1's G+P4.
  - Accepted tradeoff: a cap that truly costs about half a point usually passes.
- **PASS** iff both co-primaries hold. Season-clustered bootstrap (slates resampled within season), B = 20,000, fixed
  seed. The family of two arms (EA, EW) is Bonferroni-split: one-sided level 0.9875 per arm and co-primary.
- **Secondaries:**
  - the expected bust loss EBL = 0.20 × Σ_i swing_i (flat nominal P(bust), frozen; no calibration of p20 by position
    exists, and zero-mass ties make "below p20" ill-defined where p20 = 0);
  - the sum of the top-3 swings;
  - P(zero-ticket slate): the operator's pain point; binary over 36 slates, so low power;
  - the worst-decile slate;
  - tickets at the contest lines;
  - best ≥ 194 / 200;
  - the realized one-player-bust exposure (the study 1 measure);
  - EA's miss rate.
- **Vacuity:** an arm whose dealt entries equal C's on more than 80% of slates is a dead lever.
- **Integrity:**
  - the reader is frozen and its sha recorded before any scored bank;
  - an outcome-blind support census (the binding rate, entries changed, EA's miss rate);
  - a full-path smoke on a throwaway bank (discarded unread), including the EBL rescoring path;
  - the lab-API check on the harness's lab calls.
- **If PASS:** the operator chooses the level. It is a reversible trial under adoption track v2, with
  Addendum-1.5-style rollback, and is usable in Week 6 at the earliest.

### Power for co-primary 2 (sized from study 1's already-read banks 1402/1403; outcome-blind about 1b)
These are the per-slate paired differences on the same 36 slates, the Week-4 plan and the season-clustered SE. The
lower bound is one-sided at 0.9875 (z = 2.241). The closest analogues:
- EA re-deals the same book, like study 1's P4: SE 0.0050, half-width 0.0113.
- EW changes the book, like study 1's G at the entry level: SE 0.0063, half-width 0.0142.

| margin m | EA-like: P(pass), true Δ = 0 | EA-like: Δ = −0.005 | EW-like: Δ = 0 | EW-like: Δ = −0.005 |
|---|---|---|---|---|
| 0.010 (1 pt) | 0.40 | 0.11 | 0.25 | 0.07 |
| 0.015 | 0.77 | 0.40 | 0.55 | 0.25 |
| 0.020 (2 pts) | 0.96 | 0.77 | 0.82 | 0.55 |

So a 1-point margin passes a truly harmless cap less than half the time, which makes it near-unpassable by design. A
2-point margin also passes a cap that truly costs half a point most of the time. For scale, in study 1 C's dealt entries
averaged the 53.4th percentile of the sampled field (the Week-4 plan on the 36 panel slates), 3.4 points above the
median. A 2-point margin therefore tolerates a loss of more than half of that edge. Study 1's G+P4 arm (SE 0.0097) shows that a cap which moves both the book and the deal can be twice as
noisy. If EW behaves like that, even m = 0.020 has power of only 0.43.

## Reviewer decisions (10-05)
- The single-bust anchor is median → p20 with the field rescored.
- Co-primary 1 carries the both-seasons rule.
- The worst single-bust loss replaces the expected bust loss as co-primary 1.
- The margin m is put to the operator with the power table.

## Appendix: the power-table script
It reads only study 1's reader functions and its already-read banks. It was run with the lab venv, with
`PYTHONPATH=<production src>:<s1 worktree src>`.

```python
# Outcome-blind about 1b: study 1's already-read banks -> per-slate paired entry-level differences -> SE -> power.
import sys, importlib.util, numpy as np
from pathlib import Path
from collections import defaultdict
from statistics import NormalDist
R = Path.home()/"projects/.nfl2-worktrees/s1-deconcentration-20261005/scripts/s1_report.py"
spec = importlib.util.spec_from_file_location("r", R); r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
res = r.load(Path.home()/"s1-panel/out", [1402, 1403])
contests = r.mean_contests(Path.home()/"week4-sunday/contests.json")
S = defaultdict(lambda: defaultdict(list))
for k, bb in res.items():
    for b, m in bb.items():
        bk = m["books"]
        for arm, lay, key in (("C","head","C"),("G","head","G"),("C","spread","P4"),("G","spread","GP4")):
            es = r.entry_stats(bk[arm], contests, r.deal(bk[arm]["rows"], contests, lay), None)
            S[k][key].append(es["mean"])
z = NormalDist().inv_cdf(1 - 0.025/2)   # one-sided lower bound, family 0.975 over 2 arms
print(f"one-sided z (0.9875) {z:.3f}; slates {len(S)}")
for key in ("P4","G","GP4"):
    by = defaultdict(list)
    for (s, w), v in S.items():
        by[s].append(np.mean(v[key]) - np.mean(v["C"]))
    se = np.sqrt(sum(np.var(x, ddof=1)/len(x) * (len(x)/36)**2 for x in by.values()))
    hw = z*se
    line = f"{key:4s} vs C: est {np.mean(np.concatenate(list(by.values()))):+.5f} se {se:.5f} half-width {hw:.5f} |"
    for m in (0.010, 0.015, 0.020):
        line += f" m{m:.3f}: P(pass|d=0) {NormalDist().cdf(m/se - z):.2f} P(pass|d=-0.005) {NormalDist().cdf((m-0.005)/se - z):.2f};"
    print(line)
```

---

## Deviation note 1 (2026-10-05, before any experiment code, bank or outcome): the operator re-chose m = 0.015

**What prompted it:** the reviewer flagged that the operator chose m = 0.020 without the scale. The wrong draft
sentence ("1 point is about 2% of the edge") was never shown to him: it was only in the draft file. But neither was
the correct scale.

**What he was shown:** "in the test data our entries average about 3.4 points above the median of the field (53.4th
percentile). A 2-point allowance means the cap can pass even if it gives up more than half of that edge. A 1.5-point
allowance gives up less, but a harmless cap passes only 77% / 55% of the time (vs 96% / 82% at 2 points). Keep 2
points?"

**His answer, verbatim:** "Change to 1.5 points".

**Effective from this note: m = 0.015.** It replaces the m = 0.020 in co-primary 2.
- Power at a true Δ of 0 / −0.005, from the table above:
  - EA (P4-like): 0.77 / 0.40;
  - EW (G-like): 0.55 / 0.25;
  - EW, if it is as noisy as G+P4: 0.25 at Δ 0.
- A cap that truly costs half a point now passes only 25–40% of the time. EW's test is close to a coin flip even when
  the cap is harmless.
- Everything else in the frozen text is unchanged.

## Deviation note 2 (2026-10-05, after an outcome-blind mechanics smoke, before any scored bank): EW is enforced at entry level

**What the smoke showed:** throwaway bank 1406, 2023 W1, the Week-4 plan (147 entries), mechanics only.
- EW as frozen does not hold its cap. The realized maximum player exposure is:
  - EW: 50 entries against a cap of 44;
  - EW25: 42 against 36;
  - EW35: 64 against 51.
- The cause: the frozen w_k come from assign_ranks BEFORE the small-contest overlap limit. limit_small_overlap then
  re-deals the 2–10-entry contests onto later ranks, whose players gain entries the w_k never counted.
- On the same slate, EA missed 58 of 147 entries (39%), and its maximum stayed at 81 entries against C's 82.

**The change (reviewer-accepted):** EW, EW25 and EW35 are each built as their own capped book (unchanged), dealt as C,
THEN passed through EA's frozen re-deal at the same level. Misses are counted and reported per arm exactly as for EA. A
fixed-point rebuild was rejected: it has no convergence guarantee and costs 3× the solves.

**What the arms now mean:**
- EA is the cap by assignment alone.
- EW is selection diversification PLUS assignment enforcement.
- So EW vs EA isolates what selection adds.

**Reader additions (before its sha is frozen):**
1. The reader reports each arm's REALIZED maximum player exposure, in entries and as a share, per slate and pooled,
   beside its miss rate. It is the honest manipulation check behind WSB. If an arm's realized maximum stays above its
   cap, the reader says that WSB's improvement is partial.
2. The frozen "> 10% misses → the cap cannot be achieved" rule applies to EW as well as EA. A leaky arm cannot pass on
   a cap it does not deliver.

The decision rule, the margin (0.015) and everything else are unchanged.

## Deviation note 3 (2026-10-05, before any scored bank): the reader is frozen and the census is in

**Code:** nfl2 `production/s1b-entry-cap-20261005` @ 635ab60.
- Reader `scripts/s1b_report.py`, sha256 `f7e40cddeff14dcfbb0eea0ed9782d6a1bd41d30712a3adb18f127de7cb1322c`.
- Experiment `experiments/s1b_entry_cap.py`, sha256 `c3c3190239258f32ded5d4ea9b274a1591a7f01e3cdcd7aac625a496a4dd1867`.
- Driver `scripts/s1b_drive.py`; census `scripts/s1b_census.py`; tests `tests/test_s1b_entry_cap.py` (11 pass, and a
  mutation of the cap check is caught).
- The overlap ceiling of 10 is hard-set and asserted.
- The full-path smoke on throwaway bank 1406 passed: build and reader rc 0, output deleted unread.
- Banks 1404 and 1405 were verified unused by the all-branch bank-label scan. The labels found at 1340 and above are
  1340, 1341 and 1400–1403.

**The outcome-blind census:** banks 1404/1405, mechanics only, 72 slate-banks, no errors. Verbatim in the lab at
`results/s1b/CENSUS_s1b.txt`.

| arm | dealt entries changed vs C | miss rate (mean / max) | realized max exposure (mean / max) | slate-banks over the cap |
|---|---|---|---|---|
| C | – | – | 0.611 / 0.660 | – |
| EA (30%) | 0.063 | 0.382 / 0.435 (72 of 72 above 10%) | 0.589 / 0.660 | 72 |
| EW (30%) | 0.827 | 0.024 / 0.088 | 0.318 / 0.367 | 49 (mean +2.8 entries) |
| EW25 | 0.869 | 0.025 / 0.095 | 0.263 / 0.306 | 60 |
| EW35 | 0.748 | 0.027 / 0.116 | 0.368 / 0.435 | 54 |

**Read before any outcome:**
- EA's frozen rule will report "the cap cannot be achieved by assignment alone" on every slate-bank. That is now
  known from mechanics.
- EW delivers the cap to within about 3 entries. The reader's "WSB improvement partial" flag will fire, because the
  realized maximum exceeds the cap on 49 of 72 slate-banks.
- No arm is vacuous, and no book is short.

## Deviation note 4 (2026-10-05, before any scored bank): the reader is re-frozen with PARTIAL carrying its numbers

At the reviewer's request, the PARTIAL flag now reads "PARTIAL (over the cap on n/N slate-banks; mean excess +x
entries; worst +w)". It stays a FLAG and never fails an arm; only the frozen miss rule fails an arm. A bare "PARTIAL"
would have made an arm at 0.32 against a 0.30 cap read like a failure.

**The reader is re-frozen:** nfl2 `production/s1b-entry-cap-20261005` @ acea6b9.
- `scripts/s1b_report.py`, sha256 `384e62f77acedb71a0d73baf46e0f7ee79c466f5fb9bb0dc8817baf00f465629`. This supersedes
  note 3's f7e40cdd.
- The experiment is unchanged: `c3c3190239258f32ded5d4ea9b274a1591a7f01e3cdcd7aac625a496a4dd1867`.
- Checks: 11 tests pass, and the full-path smoke on throwaway bank 1406 (2023 W5) passed with build and reader rc 0.
  Its output was deleted unread.
