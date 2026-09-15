# Preregistration — the admission cap as a retrieval lever, and the paid sources re-tested behind it

**Frozen 2026-09-15 21:15Z, before any new outcome is read.** Operator instruction (same day): "fix the admission
bottleneck first, then re-run the ladder." Author: the agent operating both teams. Instrument: the direct paid-source
runner (`scripts/paid_source_ladder_direct_v1.py`, branch `production/paid-source-ladder-direct-20260915`) and its
2026-09-15 per-slate records, which already hold every cell's player annotations, so the component producer is not
re-run; only admission, selection and grading are recomputed. New script: `scripts/paid_source_admission_cap_v1.py`.

## Why

The ladder run (`reports/2026-09-15-paid-source-influence-ladder-direct.md`) found the admitted ceiling ≈ 181 in every
cell against a pool ceiling of 202.7: admitting the top 200 candidates by mean matchup edge discards the tail
two-thirds of the time, independent of the vendor data. A source cannot show value through that gate. This cohort
asks (1) whether lifting or changing the gate recovers the tail on realized points and finish, and (2) whether the
paid sources matter once the gate no longer dominates.

## Design (frozen)

Slates: the same 54 (2023–2025 W1–18). Candidates and worlds: the same byte-identical corpus and discovery matrices
(re-downloaded; header candidate order checked against the artifact). Player annotations: read from the 2026-09-15
records (`player_annotations` per cell; sha256 of each record captured in the new manifest). Lineup support:
`_lineup_support` recomputed from those annotations (identical inputs → identical qualification and edge means).

Factor A — **admission rule** (all with the qualification gate kept: QB depth-1, ≥ 2 supported players, completeness
≥ 0.5):

| id | rule |
|---|---|
| `cap200` | control: top 200 by mean matchup edge (the frozen ablation) |
| `cap400` | top 400 by mean matchup edge |
| `cap800` | top 800 by mean matchup edge |
| `capall` | every qualifying candidate (no cap) |
| `tail200` | top 200 by discovery tail count (number of the 40,000 worlds ≥ 194), ties by mean world score — the coverage selector's own utility used as the admission score, sources unused |

Factor B — **sources**: on-on and off-off (the two extreme cells; FP/SIS conditionals are secondary and reuse the
existing on-off / off-on annotations where the rule needs them).

Selection: coverage-194-v1 to K80 in selector order, unchanged. `tail200` is source-free by construction (its
admission does not read annotations), so B does not apply to it.

Endpoints per slate × cell: K20/K40/K80 prefix maxima and thresholds on realized micro-DK points; finish = −best_pct
against the same 200,000-lineup ownership field (same sampler, same seed per slate → identical field); events; the
admitted ceiling.

## Estimands and decision rule (frozen)

Primary (family 0.9875, four contrasts, paired weekly, seasons clustered, 20,000-draw bootstrap seed 47, plus the sign
test reported alongside because three clusters make intervals narrow):

1. `capall` − `cap200` on K20 realized max, sources on-on (does lifting the cap recover points?)
2. `capall` − `cap200` on K20 −best_pct, sources on-on (does it recover finish?)
3. `tail200` − `cap200` on K20 realized max (is a source-free tail-aware gate better than the paid-source gate?)
4. on-on − off-off on K20 realized max **at `capall`** (do the sources matter once the cap no longer dominates?)

PASS iff interval > 0, every season ≥ 0, every LOSO > 0 and sign-test p < 0.05. NEAR_MISS: mean > 0 with the lower
bound within half the mean. Otherwise NO_EFFECT. Secondaries, never gating: the same at K40/K80; `cap400`/`cap800`
dose response; finish versions of 3 and 4; the admitted ceiling per rule; the share of slates whose admitted set
contains a 194+ candidate; FP and SIS conditionals at `capall`.

## Consequences (frozen)

- 1 or 2 PASS → the frozen retrieval strategy's cap is a real bottleneck; propose the lab preregistration that
  moves the money-path retrieval to the uncapped or tail-aware rule (the lab's live path uses `dual_emax`, not
  coverage-194, so this is a research routing decision, not a Sunday change).
- 3 PASS → the paid-source gate is worse than a free one; the sources' retrieval use is closed regardless of 4.
- 4 PASS at `capall` → the paid sources carry retrieval value that the cap was hiding → SIS/FP family decomposition
  and a prospective shadow; not before.
- 4 NO_EFFECT at `capall` with 1 or 2 PASS → the sources do not help even without the gate → do not renew.
- Nothing passes → the retrieval regret is not in the gate; close this lever.

No live change follows from this cohort; Week 2 is unaffected.

## Mechanics gate

One slate (ordinal 0) outcome-blind: five rules × two source states produce exact K80 (or a recorded infeasibility
where fewer than 80 qualify), admission counts monotone in the cap, `tail200` independent of the source state,
candidate order equal to the artifact, field receipt identical to the 2026-09-15 record's (same seed → same sampler
receipt values).
