# TD competitive-WR allocation protocol

Frozen 2026-08-14 CDT after reconciliation of the invalid TD-ledger
rank-coupling run, but before implementing or computing the treatment below.
This is a new adaptive, retrospective, score-free dependence mechanism. It is
not another retry of the closed global TD-ledger arm. It may use realized
player outcomes only to grade the preregistered dependence scores; it may not
generate, select, query or score a lineup.

Amended before launch or treatment output after review in
`2026-08-14-td-competitive-wr-allocation-protocol-review.md` to bind the clean
reference identity, mandate an ungated multiplicity `>=4` diagnostic, and
state the deliberate QB-TE scope boundary. None changes the treatment or gate.

## Motivation and mechanism boundary

The repaired simulator has a shape error rather than a global dependence
shortfall. Its QB-to-WR boom lift is too low, while WR-WR, QB-RB, RB-RB and
supported three-player multiplicity are already too high. The closed global
ledger moved QB-WR in the desired direction but worsened every competing
over-coupled cell. A new treatment must therefore be receiver-specific and
competitive: strengthen the QB hub for WRs while discouraging simultaneous
same-team WR extremes, without altering QB, RB or TE draws.

QB-to-TE is deliberately out of scope. Most supported team groups have no
same-position TE competition for this construction to exploit, and changing
TE ranks would invalidate the mechanical negative control. The designated
follow-up is a separately preregistered **TE-only QB-hub rank** evaluation on
the Stage R repaired path. It must pass its own score-free gate before any
composition with this WR mechanism can be considered; neither a WR pass nor
the stale pre-repair G2 fit licenses it.

The sole treatment is the deterministic centered allocation rank defined
below. There is no strength parameter, grid, interpolation, partial blend,
winner-count choice or post-result repair. TD-ledger values supply ranks only;
every served player marginal remains the incumbent marginal.

## Stage R: clean repaired-path reference

Before treatment can run, a separate score-only reference execution must:

1. pin an immutable full-test image digest and full code SHA;
2. pin active cache `tabpfn_active_label_treatment_v2`, finite Dirichlet usage
   `K=28.154043586960896`, the accepted strict-prior 2023--2025 served-position
   schedule, 45/55 model/market blend, 10,000 worlds and seed 0;
3. use evaluation panel
   `20260812-pitclean-e80-selected-tabpfn-active-v2` and historical splice
   `20260811-pitclean-e80-k1-role12union-a12ab31`;
4. generate the unchanged terminal book twice and require bit-exact frames,
   draws and terminal identities;
5. recompute the complete repaired-path G0/G1 score book; and
6. reproduce every value in the `control` object embedded in immutable report
   `reports/td-ledger-rank-coupling-runs/20260814-td-ledger-rank-coupling-v1/report.json`
   (SHA-256
   `6342eab48c2a3b7f417f60d18a2c58111388b03a60a7917e4ad5fee3c833c0c1`)
   within absolute tolerance `1e-12`, with exact structure and nonnumeric
   values.

That prior report's treatment and invalid disposition are not evidence for
this arm. Its repaired current-control payload is used only as a frozen
cross-check. A passing Stage R report becomes the sole clean comparator for
Stage T. Failure is terminally invalid/inconclusive and prohibits Stage T.
The Stage R report must carry its immutable run ID and full 40-character code
SHA, and those values must match its launch manifest.

## Stage T: sole centered competitive allocation

Stage T must pin the passing Stage R report and manifest hashes plus the same
immutable cache, schedule, panel, usage, blend, world count and seed. Its
launcher and runtime must assert that the report's Stage R run ID and full
code SHA equal the values in the pinned Stage R manifest. It
generates four aligned books: incumbent control and its independent repeat,
and `TD_LEDGER=1` rank source and its independent repeat. The TD-ledger source
uses `td_alloc_k=None`; no TD value is copied into output.

Eligibility is determined without outcomes. Within each
`(season, week, game_id, team)` group, treatment is allowed only when the G0/G1
supported population contains exactly one QB and at least two WRs. Supported
means position in QB/RB/WR/TE and unchanged served mean at least 4.0. Ambiguous
or insufficient groups and all unsupported rows remain bit-exact control.

For every eligible group:

1. convert the unchanged control QB row to stable percentile ranks over world
   index `0..9999`;
2. convert every eligible WR's independent `TD_LEDGER=1` source row to stable
   percentile ranks over the same worlds;
3. for each world, compute the arithmetic mean TD percentile across eligible
   WRs;
4. for WR `j`, compute the sole allocation priority
   `QB_control_percentile + (WR_j_TD_percentile - team_WR_mean_percentile)`;
5. stable-sort worlds ascending by that priority, retaining ascending world
   index for exact ties; and
6. place the stable-sorted unchanged control marginal for WR `j` into that
   world order.

The common QB percentile supplies the desired hub. Centering each WR's
TD-ledger percentile against the same-team WR mean supplies competition and
prevents a team-wide positive factor from raising every receiver together.
The centering coefficient and QB coefficient are both exactly one by
definition. Do not change them, substitute a maximum, select a hard winner,
bin ranks, tune by season, or add randomness.

## Population, score book and invariants

Use the exact 2023--2025 Stage R population: active QB/RB/WR/TE rows with
unchanged served mean at least 4.0. Boom thresholds remain each player's
unchanged control q90. Recompute all nine G0 cells, every G1 relationship,
aggregate joint-q90 Brier and p=0.5 variogram, supported G0/G1
absolute-log-error sums, season disclosures, and the paired whole-slate
bootstrap with 2,000 replicates and seed 1703.

Multiplicity `>=4` is a mandatory ungated diagnostic. Report its realized
event count, independence-expected event count, realized estimate, control and
treatment simulated estimates, absolute log errors, and whether treatment
moves toward or away from realized. It remains unsupported at the current
seven realized events and therefore cannot determine pass/fail. Its movement
must nevertheless be stated in the terminal disposition report because it is
the largest current-path point error and is directly relevant to extreme
lineup outcomes.

Stage T is valid only if all of the following hold:

1. Stage R disposition is exactly `td-competitive-wr-reference-passes` and
   both reference file hashes match the launch manifest;
2. the newly generated control score book reproduces Stage R within absolute
   tolerance `1e-12`;
3. control/repeat and source/repeat frames, draws and terminal identities are
   bit-exact;
4. player keys, outcomes, mean, team, opponent and game alignment are exact;
5. every treatment sorted draw row is bit-exact to its own control row;
6. output is finite and maximum float64 player-mean drift is at most `1e-10`;
7. every QB, RB, TE, unsupported WR and WR in an ineligible group remains
   bit-exact control;
8. every changed row is an eligible WR, at least one eligible group and WR
   row exists, and at least one eligible row/world cell changes; and
9. the independently repeated TD source produces bit-exact priorities,
   eligibility, audit counts and treatment output.

## Frozen score-free scientific gate

Conditional on every invariant, Stage T passes only if all requirements hold:

1. aggregate joint-q90 Brier strictly improves;
2. aggregate variogram p=0.5 strictly improves;
3. G1 QB-WR broad absolute-log error strictly improves;
4. G1 WR-WR broad absolute-log error strictly improves;
5. G0 QB-WR absolute-log error strictly improves;
6. G0 WR-WR absolute-log error strictly improves;
7. supported G0 multiplicity `>=3` absolute-log error strictly improves;
8. supported G0 multiplicity `>=2` error does not increase by more than
   `1e-12`;
9. supported G0 absolute-log-error sum strictly improves;
10. fixed-weight supported G1 absolute-log-error sum strictly improves; and
11. QB-TE, QB-RB and RB-RB scorecard values and broad simulated lifts, plus
    G0 QB-TE, QB-RB and RB-RB simulated estimates, remain unchanged within
    absolute tolerance `1e-12`.

The last requirement is a mechanical negative control because the treatment
does not alter any QB, RB or TE draw. Season results and paired-bootstrap
intervals are disclosed but do not impose a season-stability gate. No lineup
outcome, score threshold, roster composition or ROI result enters this gate.

Valid Stage T dispositions are
`td-competitive-wr-allocation-gate-passes`,
`td-competitive-wr-allocation-gate-fails` and
`td-competitive-wr-allocation-invalid-or-inconclusive`. No tolerance,
priority, population or result may be changed after treatment output.

## Consequences

A valid pass licenses exactly one separately frozen paired five-seed exact-80
control/treatment comparison under the current finite-K incumbent. It does not
authorize a production change or composition with SIS, ASOE, pass-tail, G2/G3,
K=1 or another dependence treatment. Historical scoring remains adaptive
evidence and any eventual production use requires a labeled 2026 prospective
shadow.

The named TE-only QB-hub follow-up is independent future work. It is not
licensed for lineup scoring by this result, and WR-plus-TE composition requires
both mechanisms to pass separate score-free protocols followed by a separately
frozen interaction test.

A valid failure closes this centered competitive-allocation mechanism on the
historical panel. An invalid result closes it as unadjudicated. Neither branch
licenses parameter tuning or a repair on the same outcomes.
