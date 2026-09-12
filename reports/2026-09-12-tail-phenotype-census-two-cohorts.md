# Tail-phenotype census on two opened cohorts — hypothesis generation for the supply arms

**Date:** 2026-09-12 · **Source:** read-only Cypher against the local Neo4j (`nfl-kg-local-smoke`: the
PREREG-083 cohort and the production E0 historical slice) · **Evidence class:** outcome-viewed development
data. This informs the *design* of prospectively graded arms (PREREG-091, the tail-supply shadow arms); it is
not adoption evidence and must not be re-used to tune anything on these slates.

## Cohort A — PREREG-083 (lab): 36 slates × 2 arms × 200 candidates, K80 books

Realized 200+ per 1,000 candidates, and how often the selector took that phenotype:

| distinct games in roster | n | realized ≥200 | per 1,000 | share selected into K80 |
|---|---:|---:|---:|---:|
| 3 | 655 | 1 | 1.53 | 83% |
| 4 | 4,023 | 4 | 0.99 | 61% |
| 5 | 6,697 | 12 | 1.79 | 35% |
| 6 | 3,008 | 7 | 2.33 | 13% |

| max players from one game | n | realized ≥200 | per 1,000 | share selected |
|---|---:|---:|---:|---:|
| 4 | 7,823 | 16 | 2.05 | 22% |
| 5 | 5,259 | 7 | 1.33 | 57% |
| 6 | 1,102 | 1 | 0.91 | 75% |
| 7–8 | 216 | 0 | 0.00 | 92–100% |

Position shape: 2RB/4WR/1TE 2.07 per 1,000 (selected 41%), 3RB/3WR 1.81 (46%), 2RB/3WR/2TE 0.34 (33%).

The realized-best candidate per slate sat at mean simulated-q99 rank 82–92 of 200 (the simulator's tail
ranking is close to uninformative about which candidate wins), and reached the K80 book on 19/36 (control)
and 18/36 (treatment) slates — a 1.2–1.3× lift over the 40% base rate.

## Cohort B — production E0 corpus: 54 slates, the 279 realized 200+ lineups, eight final-fit books

| distinct games | max from one game | n (≥200) | in any final book | of which ≥220 |
|---|---|---:|---:|---:|
| 5 | 4 | 58 | 10 | 4 |
| 6 | 3 | 52 | 3 | **9** |
| 6 | 4 | 36 | 5 | 4 |
| 5 | 5 | 23 | 6 | 4 |
| 5 | 3 | 22 | 3 | 1 |
| 7 | 3 | 17 | 3 | 4 |
| 4 | 5 | 15 | 2 | 2 |
| 7 | 2 | 13 | 0 | 1 |
| 4 | 4 | 11 | 1 | 2 |
| 6 | 2 | 11 | 1 | 1 |

Of the 34 realized 220+ lineups, 14 span ≥6 games with ≤3 from any one game; the books captured 7 of the 100
200+ lineups in that phenotype (7%) against 12 of 49 concentrated ones (≥5 from one game, 24%).

QB teammates among the 279: 0–1 teammates 91 lineups, 9 captured (10%); 2 teammates 129, 7 captured (5%);
3 teammates 59, 22 captured (37%). Bring-back is absent on 91 of them (33%), captured 16%.

## Reading

Two teams' pipelines, two selectors (coverage-194 and the tail ladder / DEMAX family), two corpora: the
lineups that reach 200+ and especially 220+ are disproportionately **broad** (≥5–6 games, ≤3–4 from any
game, ≤2 QB teammates), and both pipelines select the **concentrated** phenotype several times more often.
The retention fix (PREREG-057 STRUCT sleeve: retain low-concentration candidates from the same pool) failed
because the candidates it retained were the low-simulated-value ones. The untested lever is at
**generation**: build the per-world optimum *within* the broad phenotype so the candidates are both broad and
strong in their world. The optimizer has carried an inert `MAX_PER_GAME` constraint since 2026-08-03
(winner census: 28 mapped Milly winners average 2.96 from their most-loaded game).

## What this licenses (and does not)

- Licenses: PREREG-091's `D800_SPREAD4_DEMAX` arm (MAX_PER_GAME=4, same worlds, same budget, house law
  intact) with a gate frozen before any read; a live frozen shadow book with `--max-per-game 4` from Week 1.
- Does not license: any change to the paid book, any selector tuning, or any claim about causal effect —
  the enrichment is selection-conditioned and both cohorts are opened outcomes.

## Provenance

Queries run 2026-09-12 ~18:05Z against `bolt://127.0.0.1:7687` (auth none). Cohort A nodes:
`CandidateOccurrence:Prereg083Entity` (14,400) → `Roster` (12,960; `unique_games`, `max_game_count`,
`position_counts`). Cohort B: `HistoricalCorpusEntity{kind:'LineupCandidate'}` (279) with
`properties_json.structural_phenotype` and `selected_final_book_count`. No graph mutation.

## Addendum (19:50Z) — generation depth on Cohort A: the marginal boom world is as good as the first

Same read class (outcome-viewed development data, design evidence only). `candidate_rank` orders each
200-candidate arm in generation order (ranks 0–24 are essentially the leverage family: 8% selected, higher
served projection; ranks 25–199 the boom worlds in visit order). Realized tail hits per 900 candidate-slates
by rank bucket of 25:

| bucket (ranks) | control ≥187 / ≥200 | treatment ≥187 / ≥200 | selected share (control / treatment) |
|---|---:|---:|---:|
| 0 (0–24) | 3 / 0 | 3 / 0 | .08 / .06 |
| 1 (25–49) | 8 / 2 | 5 / 0 | .24 / .26 |
| 2 (50–74) | 2 / 1 | 5 / 1 | .51 / .56 |
| 3 (75–99) | 8 / 2 | 8 / 3 | .46 / .48 |
| 4 (100–124) | 6 / 3 | 7 / 3 | .49 / .46 |
| 5 (125–149) | 4 / 2 | 3 / 1 | .48 / .47 |
| 6 (150–174) | 7 / 2 | 5 / 1 | .44 / .47 |
| 7 (175–199) | 4 / 0 | 7 / 3 | .48 / .43 |

No decline with depth: the boom worlds visited last produce 187+/200+ candidates at the same rate as the
first, while the simulator's own tail figure (`sim_q99`) drifts down by only ~1.5 points across the range.
The slate's realized-best candidate came from ranks 150–199 on 9 of 36 control slates and 11 of 36 treatment
slates (ranks 0–49: 6 and 2). This is the per-visit view of PREREG-047's count-match null (400→800 gained
by volume, not by better candidates) and is the design evidence behind the dose ladder PREREG-090 (1600)
and PREREG-093 (3200, nested stream): as long as the duplicate rate stays negligible (0.0000 at 1600 on
2023-W1), supply of 200+ candidates should scale roughly linearly with solves. It says nothing about
selection, which converts only part of that supply (PREREG-047: ~1.2 raw points per doubling).
