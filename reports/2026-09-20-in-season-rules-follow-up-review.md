# Follow-up review of the v2 in-season adoption rules

Reviewed production rules at `8f590212` (`production/in-season-rules-20260919`), including the adoption track, its `CLAUDE.md` precedence note, and the fail-closed prospective-gate checker. The v2 document correctly implements the operator's priority: a reversible, candidate-specific repair or trial can be recommended as soon as its evidence package is ready, while scientific verdicts and operator adoption remain separate. It removes the old fixed historical-count and automatic loss-count barriers without weakening point-in-time, legality, identity, independent-audit, or rollback requirements.

The class definitions are coherent:

* R repairs require a proved intended correction and propagation through the final consumer, with no outcome wait for correctness.
* C calibration/weighting changes require final-consumer proper scores and fixed-book replay, with point MAE reported separately from distribution CRPS.
* S selection/objective/construction changes require a paired prelock-frozen shadow and an explicit primary utility; component and prefix losses are costs, not a universal veto.
* E entry-side changes require legal mechanical rehearsal and a restore path; the operator retains the final contest decision.

The unchanged integrity rules are also appropriate: one read per arm, frozen readers, current-policy gate arming, no silent failed-task exclusion, independent audit worlds, single writers, and no current outcomes in development screens.

## Concrete follow-ups

### 1. Align the scheduler registry with its own classification

In `scripts/check_prospective_gates.py`, `DORMANT` contains
`s-shadow-cbwu-oi-paired-early` and `s-shadow-cbwu-oi-paired-late`, but the reason strings say “ENABLED and running.” A scheduler cannot be both a deliberately dormant classification and a live enabled shadow without an explicit state distinction. Either move these two names into a real gate with a frozen document, or keep them in `DORMANT` and change the reason to state why the enabled-looking jobs are not currently graded. Otherwise the registry can report a formally clean classification while the operator cannot tell whether the pair is expected to run.

### 2. Resolve SIS pass-tail before its look-ahead window

The `sis-pass-tail-2026` registry entry points `doc` at the implementation module rather than a frozen gate contract, sets `require_env=None`, and says that Week 5 is inferred from a four-week context. The handoff says the SIS/Fantasy Points shadow schedules are paused. That is a valid research decision, but it should be represented explicitly: either write the gate document with its information cutoff, source coverage, earliest usable week, and risk class, or move all three SIS pass-tail schedulers to `DORMANT` with the pause reason and a named reactivation condition. Leaving them as a future gate with no contract creates a warning at the look-ahead boundary and invites an invalid partial week.

### 3. Separate the Route Share research instrument from the 2026 money-path gate

`fp-route-share-2026` is correctly labeled `in_season_value=False` because it adjudicates only after Weeks 2–18 for a next-season decision. It should not consume current-season urgency or block a 2026 build. Keep it in the registry for scheduler integrity, but make the output and handoff explicitly say “research instrument; no 2026 entered-book authority.” If the operator does not want to fund it while SIS/Fantasy Points are paused, classify the schedulers dormant with that reason instead of allowing a future gate warning to be mistaken for a production defect.

### 4. Preserve the current rule precedence in every new handoff

New experiment records should name the earliest week of possible use, the class, the frozen control, the primary utility, material-harm limits, and the restore path. A simulated selector improvement cannot authorize a live change; an S candidate must enter the weekly realized scorecard. This is especially important for the D12800 `dual_emax` versus `cap_prefix_then_fill` shadow: simulated P220/P230 gains remain mechanism evidence until the paired realized max-of-K and 200/210 read is available.

These are documentation/registry repairs, not reasons to delay today's production build. They should be corrected before the next prospective-gate audit so a paused vendor shadow cannot be mistaken for a failed experiment and a dormant research instrument cannot silently claim 2026 authority.
