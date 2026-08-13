# Current-stack extreme-selector replication

Status: frozen after the original corrected-history selector result was known,
but before this current-stack panel is queried under the extreme selector.
This is an explicitly labeled replication, not an independent discovery.

## Question and source

Does the already-fixed 220->210->200 selector improve the current terminal
PIT-clean active-label book, even though it rejected on the older 107-slate
corrected role-union panel?

Use exactly panel `20260812-pitclean-e80-selected-tabpfn-active-v2` from
`replay_candidates`. It contains the terminal active-only TabPFN labels,
finite `K=28.154043586960896`, walk-forward position scales, direct-role
candidates, 40 boom candidates, 80 persisted selections, and all 54 Sunday
main slates from 2023--2025. Candidate generation, actuals, worlds, masks and
the pool oracle remain fixed.

First reproduce the persisted line-194 coverage book exactly. Then apply the
unchanged `extreme_lexicographic_order`: new world coverage at 220, then 210,
then 200; individual 220/210/200 probabilities, simulated mean and candidate
index are the unchanged tie sequence. Select exactly 80 unique lineups.

## Decision and Monte Carlo safeguard

Compare realized weekly maximum counts at 240, 230, 220, 210, 200, 194 and
187. The first difference decides direction. A loss or tie closes this
replication. A positive result is only a candidate for promotion: because the
outcome-free audit found extremely sparse 210/220 support at 10,000 worlds, it
must also survive the already-queued multi-seed/higher-world mask-stability
check before any live selector change. No threshold, ordering, tie rule or
panel may change after this replication is read.

Report exact mechanics, weekly paired wins/ties/losses, mean/median and season
slices as diagnostics. The known rejection on the older panel must remain
disclosed and is not pooled away.
