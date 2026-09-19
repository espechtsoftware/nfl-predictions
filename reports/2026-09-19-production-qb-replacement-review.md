# Independent review of this weekend's QB and replacement changes

Review opened 2026-09-19; initial review completed at 20:04 UTC. Production shared handoff head `b370cff`, replacement `vet_replace_v3.py`, vetter v2, flags query v1, projection branch `2855cba1`. Production accepted the initial findings at shared commit `4f53a4b` and is preparing v4; that revision has not yet been reviewed here.

**Recommendation: proceed promptly with the corrected replacement implementation; do not install the original v3.** Replacing unusable lineups from an existing pool is worthwhile this weekend. The defects below are specific, reproducible and repairable; they do not justify a blanket delay of scoring improvements. The separate projection gate can be prepared for release once its corrected classifier and downstream effects have been reviewed. Production is obtaining the operator's explicit Rung 2 decision; the recorded Rung 1c GO already covers the replacement preparation.

## 1. The removal rule confuses risk with confirmed unavailability

The actual D6400 rehearsal removes Michael Pittman Jr. because of `market:VANISHED`. Its own evidence lists DK Questionable, report Questionable and a foot-related DNP, not confirmed OUT. The old vetter used this flag to demote a lineup; v3 converts the same weight into mandatory removal. These are different decisions. A missing prop may be useful information, but does not establish that a player will score zero.

V3 also zeros every quarterback with an own `DOUBTFUL` flag in both saved banks. The receipt includes Tua among those zeroed, while retained material-status lineups are otherwise described as operator decisions. This is an additional model assumption, not just removal of unavailable players. Production's accepted correction keeps Questionable, Doubtful, practice and vanished-prop signals as risk information, with an explicit shared exclusion rule for confirmed unavailable players and the declared backup-QB policy.

The claim that the component forecasts are fully conditional on playing also needs qualification: active-row component fitting is part of the pipeline, but the deployed ensemble includes TabPFN inactive zeros and other transformations. Oversized backup projections are supported by the trace; a deterministic zero is a practical model approximation, not an exact conversion to an unconditional expectation. Historical nonzero backup production does not prohibit a reversible trial; it limits that claim.

## 2. Exclusion must apply to the retained book and the entire candidate pool

V3 derives rows to remove exclusively from the old vetting result, then separately constructs a wider exclusion set. The wider set filters replacement candidates but does not necessarily remove affected retained rows. The early no-HARD return also skips the requested minimum replacement count.

Independent synthetic execution against the exact v3 file confirms:

| Boundary | Observed result |
|---|---|
| Old vetting clean; whole-slate flags newly exclude the book's QB | Exit 0, original excluded QB still emitted |
| Old vetting clean; archived frame says book player OUT | Exit 0, original OUT player still emitted |
| No removals with `--min-replacements 1` | Exit 0, zero replacements |
| Valid legal replacement control | Exit 0, correct alternative emitted |

A single ID-keyed exclusion set must drive both operations. Fresh injury/role evidence must cover candidates outside the old book too. Candidate admission is not certified by flags computed only for old selected players.

## 3. Classifiers disagree and original projection tests miss ambiguous depth

The vetter treats a Questionable primary as healthy, the flags query labels it `STARTER-QUESTIONABLE`, and the projection gate chooses the shallowest non-OUT QB. The flags query uses display names and drops QBs below four projected points. Once the gate zeros projections, that threshold hides the very players an old saved corpus still needs excluded. Four name mismatches are already logged in the rehearsal.

All **11 existing cascade tests pass** on `2855cba1`. Additional synthetic probes show:

| Boundary | Observed result |
|---|---|
| Depth 2 and 3 present, no depth 1 | Depth 3 gated, contradicting the handoff's promised no-op |
| Two primary-depth rows, one Doubtful | Merely swapping their lexical GSIS IDs changes whether depth 2 is gated |
| Missing team on unrelated depth-1/depth-2 QBs | They are grouped and depth 2 gated |
| Unique healthy primary / known OUT primary / Doubtful primary controls | Stated behavior reproduced |

The missing-team case is helper hardening: the live projection path already rejects null structural fields before this function. It is not evidence that unrelated teams were combined in the real batch. The depth ambiguity is a classifier defect independently of the real batch's incidence.

Use one classifier across consumers, preserve identifiers, require supported unambiguous primary evidence, handle Q/D consistently, and retain all relevant QBs without a projection cutoff. Production has accepted this direction. Source freshness and the distinction between the saved build's batch and a newly captured status update must be recorded.

## 4. Validate before publishing and show flags for the actual output

The original replacement helper assumes inherited candidate legality but does not validate it. Two independent counterexamples both exit successfully and publish `book.csv`:

- a nine-slot row containing the same RB twice (only eight distinct IDs);
- a row with total salary **$58,000**.

These synthetic tests demonstrate missing boundary checks; they do not claim the archived real candidate pool was illegal. Checks must cover both changed and unchanged paths, with the required K taken from the named operating contract, nine distinct IDs, valid slots, salary, roster uniqueness, exclusion compliance and complete replacement. Validate before publication; reject exhausted or duplicate candidate alternatives cleanly. A failed replacement must be visible to the operator, with the affected rows and previous validated bundle identified.

The shell patch still reads flags from the old vetted book even after replacing rows. The existing successful rehearsal replaced only positions 95–97, so it did not test the first-30 display. Rehearse a replacement within that prefix and verify the actual emitted IDs, displayed player names and flags all agree. A derived receipt should bind the final book and every input used; the copied original receipt remains source provenance, not a certificate for the changed book.

## 5. What the rehearsal does and does not establish

The original D6400 v3 result reports three replacements and an expected maximum of 201.93503 → 202.08244, P220 19.83% → 20.13%, under its modified equal-component bank. Those are selection-bank diagnostics under the zeroing assumptions above, not an independent forecast of NFL improvement. The raw incumbent component falls while raw hsim rises. That disagreement is information to report; it is not a universal-dominance veto.

For a repaired replacement step, prioritize correct IDs, supported eligibility, legal complete output, truthful display and a documented restore path. Preserve both books for later evaluation. For the projection change, also measure the effect through generation and selection, especially the primary-QB assignment when a former backup is promoted. The root trace already shows that nonprimary QBs can retain small rushing scores in hsim; zeroing served means does not alone prove every downstream draw is zero.

## Evidence and ownership

- Reproducible outcome-free counterexample reader: [Python](reviews/evidence/2026-09-19-qb-replacement-independent-probes.py).
- Recorded results and exact source hashes: [JSON](reviews/evidence/2026-09-19-qb-replacement-independent-probes.json).
- Root owns independent tests and release preparation; production owns v4 host changes and its projection branch. Running D12800 source remains untouched.
- Initial findings and acknowledgment are pushed in the shared lab handoff branch (`2b56569`, `4f53a4b`). Review continues on the corrected files; this report is not approval of an unseen revision.

## In-season policy v2 and the route-share companion

Policy v2 at `c91d1872` incorporates the main independent recommendations: candidate-specific reversible trials, no fixed multi-week sign-count wait, no universal component/prefix dominance veto, and separate scientific conclusions versus adoption decisions. The rules now support prompt current-season work while preserving outcome access, identity and legality checks.

The draft route-share companion is useful, but its K80, 40/160 generation and `greedy-tail-coverage` consumer is **not** the current lab K97, 2560/10240, equal-component expected-max consumer. Grade it under its distinct registry key as evidence about its actual consumer. Before claiming improved selection for the entered book, add a frozen current-consumer comparison (fixed saved candidates first; generation effects separately). This can be prepared now, without waiting for the original final scientific gate. Verify image defaults before enabling schedules, not after the first run.

The QB design's proposed later probability refinement should use a proper participation mixture. Scaling the mean by participation probability is valid for a zero/nonzero mixture. Multiplying quantiles by that factor is generally not; a positive-threshold tail probability can be multiplied only when it actually describes the matching conditional law. Sample mutually exclusive team QB roles, then conditional production, so uncertain-primary teams do not receive two full starters. That is a separate, useful follow-up experiment rather than a reason to delay the narrow corrected replacement.

## 20:09 UTC follow-up: zero mean still leaves generator upside

The live lab consumer at `2dc116c` reads `proj_points`, then applies `shift_draws_to_means` to its own sampled rows. It does not read the projection gate's zeroed quantiles or standard deviation. The shift preserves dispersion; no projection-based availability filter removes the QB from generation. For $4,000 players, `proj_tourney_production` uses the greater of the mean and generated p90.

Using those exact helpers on the archived morning selection bank, zero-centering Bagent leaves mean approximately zero, **p90 10.4611, p99 22.8068**, and positive scores in **42.75%** of worlds. The punt helper returns 10.4611. Keenum, Mills, O'Connell and Lance also retain roughly 10-point p90 values. This is an algebraic counterexample using saved draws, not a new generation run or a claim about the revised selected book. Rush is an algebraic control, not a recommendation to gate him.

[Reader](reviews/evidence/2026-09-19-zero-mean-qb-tail-counterexample.py) and [numeric evidence](reviews/evidence/2026-09-19-zero-mean-qb-tail-counterexample.json) preserve exact input identities and allowlisted frame columns. No outcome column is decoded.

**Implication:** a projection-only patch does not fully remove the backup's simulated upside or guarantee that solve budget stops being spent on him. Carry the supported, ID-keyed eligibility decision through generation and both banks for a complete deterministic gate, or explicitly classify the narrower projection-only trial and retain v4's final-admission protection. The latter can still be useful, but must not be described as the complete downstream repair. This finding was pushed to production in shared handoff `ffe9e12`.
