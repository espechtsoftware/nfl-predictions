# CBWU-OI construction-result review reconciliation

Date: 2026-08-15 CDT
Source reviewed: `reports/2026-08-16-cbwu-oi-construction-result-review.md`

## Decision

The review's central interpretation is accepted. CBWU-OI is the first measured
fixed-budget improvement at candidate layer C: mean weekly C rises 5.66 points,
and the 194/200/210 counts rise by 7/6/4 across 54 slates. The treatment reaches
41% more unique player pairs and 52% more QB stack cores despite retaining all
nine exact-P players on fewer slates. This is strong evidence that combination
breadth, rather than merely individual-player breadth, is an actionable
construction lever.

The main limitations are also accepted:

- the 220/230/240 C counts are exact ties, so the measured historical gain is
  concentrated in the 194--210 shoulder rather than the extreme tail;
- C-to-selected-book conversion is unknown because the frozen diagnostic
  correctly prohibited scoring the OI-selected 80; and
- a pool sharing only 40.72% of canonical identities cannot inherit the
  canonical pool's selector-stability measurement without revalidation.

Two boundaries are added.

1. Equal-budget improvement proves that composition matters; it does not prove
   that capacity is irrelevant or that more same-law candidates could not
   help. The exact-P capacity curve is deprioritized, not scientifically
   answered.
2. "Expected gains at 200--210" is recorded only as a descriptive hypothesis.
   It cannot turn a modest prospective result into a pass or alter the standing
   `240/230/220/210/200/194/187` first-difference law. The complete grid and
   all costs remain mandatory.

## Action taken

A paired, outcome-free selector-stability protocol is frozen separately in
`reports/2026-08-15-cbwu-oi-selector-stability-protocol.md`. It reconstructs
canonical and OI pools from the same five immutable books, applies identical
stratified world splits/resamples, and compares their exact-80 membership and
ordering stability. It cannot adopt, reject or tune a selector and does not
read realized scores.

The diagnostic runs after the already-launched ATLAS score-free job. ATLAS's
parameters and gate remain unchanged; this review arrived after they were
frozen and therefore cannot modify that experiment.

Production remains `classic-k1-role12-boom40-poscal-cbwu-v4`. CBWU-OI remains a
separately identified prospective 2026 shadow until prospective evidence and
the full P/C/S plus selector revalidation exist.
