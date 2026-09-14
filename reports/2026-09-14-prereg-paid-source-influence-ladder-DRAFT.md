# DRAFT preregistration — the paid-source influence ladder: Fantasy Points × SIS retrieval ablation with a stage-influence sidecar and a finish endpoint

**Status: DRAFT for operator sign-off (2026-09-14). Nothing is frozen, built, or launched. No outcome has been read.**
Author: the agent operating production and lab since 2026-09-12. Companion documents: the read-only review
`reports/2026-09-10-neo4j-fantasy-points-sis-influence-review.md` (whose P0/P1 this draft turns into a protocol),
`PREREG-098.md` on the lab branch `lab/prereg098-finish-objective-20260914` (the field sampler this draft reuses), and
the HANDOFF entries of 2026-09-11/12 on the corpus-R6 paid-source chain (defects 1–8).

## 0. Correction, and the decision only the operator can make

An earlier verbal summary (2026-09-14) said the FP×SIS ablation "fails closed because the live policy moved 11
environment keys". That is wrong. The 11-key drift breaks the *extreme-tail factorial* test chain
(`reports/2026-09-11-frozen-factorial-policy-drift.md`), which is a different chain and is not on this path.

The FP×SIS 2×2 ablation (`fp-sis-retrieval-only-cross-v1` in `src/nfl_dfs/research/paid_source_ablation_registry_v1.py`)
is blocked by **defect 8** (HANDOFF 2026-09-12): its request must bind a GCS-published `source_v3_release_identity`,
and the containerised source-v3 publication worker is protocol-deadlocked — the frozen G0 evidence is located through
absolute host paths that the image cannot read, and the file that would have to change is pinned immutable by the
same replay. Its other input, the 54-slate discovery-matrix terminal identity, is done and reopen-verified
(`23184230…`, run `exp5-discovery-matrix-20260911e`).

Three ways out; the choice is a protocol decision:

| option | what it is | cost | my recommendation |
|---|---|---|---|
| **B. Host-run publication** | run the source-v3 worker/verify/publish on the workstation, where the absolute paths resolve; only the publication step leaves the cloud | a host driver around an existing controller; no lineage change | **Try first.** It touches no frozen authority. If the controller cannot be driven off-cloud within a bounded effort (one working session), fall to A. |
| A. Re-establish the fixed-G0 authority at a new commit | repair the path literals, re-pin, re-publish G0 → capture plan → discovery matrix → ablation | invalidates the candidate-v2 lineage the capture plan, discovery matrix and ablation all bind; the 54-task discovery matrix (≈ 30 min cloud) re-runs | Acceptable; two to three cloud cycles. |
| C. Retire the chain | accept "source value not evaluated" as the standing answer | none | Not recommended: the question is the operator's own ("do we know the impact of each data point?"), and the instrument is 90 % built. |

Sign-off needed on: the option above; the endpoint family in §4 (points and finish co-primary at K20); and the
season set (§2: the ablation's 54 slates are 2023–2025, not the lab's 2022–2024 panel).

## 1. Questions, as a ladder (each rung is answerable only if the one below it moved)

1. **Wiring.** When a vendor's raw slices are physically removed, do any modelled components, player means or
   tails, or joint-law memberships change? (If nothing changes, the source is not being consumed; debug consumption
   before discussing value.)
2. **Erasure.** Where along the chain does a change stop propagating: component → player distribution → candidate
   support → admission rank → selected book? (The August route-share result was erased at the served-marginal
   transform; the coverage result changed 33 selected slots and no score.)
3. **Value.** With candidates and worlds byte-identical across cells, does the source change the selected book's
   realized points (the ledger's axis) and its realized finish against an ownership-consistent field (the money
   axis)? Reported as conditional effects and the interaction, never as an additive vendor split.

Out of scope, stated up front: whether a source helps *generate* a lineup absent from all four candidate pools
(generation/completion is a separate follow-up, review P2); per-field attribution (review P3: only on a winning
source, hierarchically, with multiplicity control, and only as explanation or a fresh prospective test).

## 2. Design (unchanged where it already exists; frozen at sign-off)

- **Cells.** The registered four: FP+/SIS+, FP−/SIS+, FP+/SIS−, FP−/SIS−. "Off" = raw slices physically removed
  before component construction (never zero-filled); joint FP×SIS components unavailable when either is off.
  Retrieval strategy `coverage-194-v1`, admission cap and entry budget as registered. Candidate corpus and 40,000
  worlds per slate byte-identical across cells (the discovery matrix). This isolates retrieval, admission and
  selection.
- **Slates.** The discovery matrix's 54: 2023 W1–18, 2024 W1–18, 2025 W1–18. All 54 have a real Sunday Millionaire
  ownership record in `nfl_raw.contest_ownership` (2023: 18 weeks / 149 contests; 2024: 18 / 203; 2025: 18 / 834),
  so the finish endpoint covers every slate. The ownership record for each slate is chosen by the same rule as
  PREREG-098 (largest Sunday-main Millionaire; joined mass to the slate's player universe ≥ 800 of ~900, else the
  slate is excluded from the finish endpoint only, and the exclusion is listed before any read).
- **Books.** Per cell and slate: the frozen K80 selected book in its selection order; K20 = its first 20 (bankroll
  primary), K80 diagnostic.
- **Field.** Per slate: 200,000 lineups from the PREREG-098 sampler (`experiments/prereg098_field_sampler.py` at
  its frozen sha256; stack 0.70, salary floor band [48,500, 50,000], six IPF rounds), targets = the slate's real
  ownership, seed = a registered function of (season, week) recorded in the manifest. One field per slate, shared by
  all four cells (the field is a property of the week, not of the cell). Realized field scores use the same
  realized-player-points body the grader already joins.
- **Sidecar (review P1).** One normalised record set per cell × slate, written by the existing execution's facts:
  source observation (vendor, family, missingness, as-of, lock time), component deltas, player mean / q90 / q99 /
  threshold deltas and joint-law membership, candidate support deltas, admission rank and cutoff margin, selection
  order / exposure / turnover / marginal new worlds, and the grade. Dense matrices stay in immutable objects; the
  sidecar carries their identities. Neo4j indexes identities and stage relationships only, after the read.

## 3. Estimands (paired within slate; seasons are the clusters)

For slate s, cell (a, b) with a = FP on, b = SIS on, and Y one of the endpoints in §4:

```
FP | SIS on   = mean_s [ Y_s,11 − Y_s,01 ]
FP | SIS off  = mean_s [ Y_s,10 − Y_s,00 ]
SIS | FP on   = mean_s [ Y_s,11 − Y_s,10 ]
SIS | FP off  = mean_s [ Y_s,01 − Y_s,00 ]
interaction   = mean_s [ Y_s,11 − Y_s,10 − Y_s,01 + Y_s,00 ]
```

## 4. Endpoints and decision rule (frozen at sign-off)

**Co-primary (four contrasts, family level 1 − 0.05/4 = 0.9875):** `FP | SIS on` and `SIS | FP on` on each of

- **points:** selected K20 weekly max (the grader's `mean_selected_weekly_max_points`), and
- **finish:** −best_pct at K20 (share of the synthetic field, scored on realized points, above the book's best
  lineup; sign flipped so positive = better finish; PREREG-098's definition).

A contrast **PASSES** iff its season-clustered bootstrap interval (20,000 draws, registered seed) excludes zero on
the favourable side, every season's mean has the same sign, and the leave-one-season-out estimates (three) are all
favourable. **Near miss**: point estimate favourable and the interval's unfavourable bound within half the point
estimate. Anything else: no effect at the tested form.

**Secondaries (never gating):** the same contrasts at K80; the `| off` conditionals and the interaction; threshold
counts 194–240; top-1,000-fraction and top-100-fraction events against the field; admitted- and candidate-pool
ceilings and selector regret (already in the grader); the sidecar's stage-change counts (rung 1 and 2 answers).

**Ladder reading (frozen; from the review):**

| observed | conclusion | next |
|---|---|---|
| no component / player value changes in a cell pair | the source is not consumed | debug consumption; no value claim either way |
| player values change; candidate / admission / selection do not | erased in between | locate the erasing transform; no score-heavy expansion |
| selection changes; no co-primary passes | the exact retrieval use has no value at this form | close it; keep the source only if a frozen prospective information-value argument exists |
| one source passes on either co-primary, stable across seasons | promising | family decomposition (P3) and a 2026 prospective shadow (P4); **no deployment from this result** |
| interaction dominates | the pair is one information product | price and test jointly; never allocate the interaction to one vendor |

Consequences are diagnostic and research-routing only. No live consumer, projection, or paid-selector change
follows from this cohort; the finish objective's live use is governed by PREREG-098's consequences clause.

## 5. Mechanics gates before any outcome read

1. **Identity binds.** The request binds the discovery-matrix terminal identity `23184230…` (reopen-verified), the
   published source-v3 release identity (after §0's decision), and the runtime build attestation. Task 0 stops on
   any candidate/world byte mismatch, post-lock source observation, or unequal resource budget.
2. **Defect-shape sweep.** Before the first build, sweep the chain for the eight never-completable shapes recorded
   in HANDOFF 2026-09-11/12 (repository-root binding, untracked-artifact-then-clean, create-once self-refusal, task-0
   parallelism, jq without `-n`, secure-read observation contract, remote-ref census, absolute-path immutables).
3. **Outcome-blind smoke on real artifacts (frozen-chain rule 1).** One slate, four cells, outcomes disabled: exact
   K80 per cell, sidecar records present for every stage, field receipt present (ownership error ≤ 0.75, salary,
   stack rate), per-world cutoffs present, zero candidate/world turnover in every cell.
4. **Field gate.** The sampler's frozen parameters are carried unchanged from PREREG-098 §Gate; no re-tuning on
   these slates.
5. **Vacuity check.** Cells whose selected books are byte-identical are reported as such; an identical pair is a
   dead lever at that stage, not a tie.

## 6. What is measured and what is not

Measured: retrieval, admission and selection value of each vendor bundle, conditional on the other; where in the
chain a source's influence is erased; its effect on points and on finish. Not measured: source-driven candidate
discovery; per-field value; live 2026 value (a shadow is the only path to that); bankroll value beyond finish
(duplication and payout tiers are not modelled here).

## 7. Cost

Four cells × 54 slates on the existing research job (one execution per cell, the registered job reused, no new
jobs); the sidecar adds bytes, not compute; the field endpoint adds ≈ 4 s sampling + ≈ 1–2 min scoring per slate
against the 40,000 worlds (chunked). Preceded by the §0 publication chain.

## 8. Sign-off checklist

- [ ] §0 route: B (host-run publication) first, A on failure — or another instruction.
- [ ] §4 endpoint family: points and finish co-primary at K20, family 0.9875 — or points primary / finish secondary.
- [ ] §2 seasons: the ablation's 54 slates (2023–2025) — accepted as the panel for this cohort.
- [ ] Ownership-record selection rule and ≥ 800 mass exclusion — accepted.
- [ ] Nothing here changes the live path; the finish objective's live use stays governed by PREREG-098.

Once signed, the document is copied without the DRAFT marker to the corpus-R6 report tree, the sampler sha256 and
seed function are written into the registry request, and the ladder (§0 route → smoke → four cells → grade →
sidecar → read) is queued behind the current lab cohorts.
