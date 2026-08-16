# ATLAS historical diagnostic high-tail guard amendment

Date frozen: 2026-08-16, before any mechanically valid ATLAS matched-diversity
grid completed and before any ATLAS historical score result was produced or
opened.
Applies to: `20260816-atlas-historical-score-diagnostic-v1`

## Reason

The original signal rule requires two additional selected-book weeks at 200,
no selected-book decline at 210, and no candidate-pool decline at 200. That is
not symmetric with the operator's tail-first objective: treatment could lose a
220-, 230- or 240-point selected week and still receive a positive label.

The 200 anchor is intentionally retained because it prevents a single rare
crossing from deciding the 54-slate diagnostic. The existing
`single-event-extreme-tail` label is also retained. This anchor differs from
the standing 240-to-187 first-difference law and was informed by the already-
known CBWU-OI result on the same panel, where movement concentrated at
194--210 and counts at 220/230/240 tied. It is therefore a prior-panel-informed
diagnostic rule, not an untouched application of the standing law. It remains
prospective with respect to ATLAS because no ATLAS score result exists.

## Exact amendment

Keep every original condition and add all three of these mandatory guards for
the selected exact-80 book `S`:

- net treatment-minus-control slate crossings at 220 must be at least zero;
- net crossings at 230 must be at least zero; and
- net crossings at 240 must be at least zero.

The result receipt must report `selected_220_net`, `selected_230_net` and
`selected_240_net` even when all are zero. A loss at any one of those lines
forces `historical-tail-signal-not-positive`; gains do not relax the original
+2-at-200 requirement. Candidate-pool high-tail counts, season signs, means
and all other thresholds remain diagnostics and cannot rescue a failed guard.

No roster, source row, realized score, selector, candidate budget, upstream
gate or consequence changes. The diagnostic remains retrospective and cannot
license production. Any future scorer image must bind the SHA-256 of this
amendment in its report and strict harvester.
