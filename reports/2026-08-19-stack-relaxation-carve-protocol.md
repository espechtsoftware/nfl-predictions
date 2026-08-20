# Stack-relaxation carve (A3) — protocol

**Protocol id:** `20260819-stack-relaxation-carve-v1`. Operator direction
2026-08-19: relaxation of the construction mandates approved ("I'm in
favor of relaxing them"); carve size delegated and decided at k=8
absolute per seed (rationale in the draft's decision record — the
modest dose deliberately limits how much the law's measured
generic-coupling bias can steer the book). Comparator: the INCUMBENT
production configuration, per the all-boom S null (boom-deep pool
shelved). One shot; 54 cells.

## Question

Production mandates confine 100% of generated volume to a shape region
(QB stack ≥2 + bring-back ≥1, mechanically 4+ players in one game) that
holds 16% of real Milly winners. Does carving 8 of the 40 boom solves
free of the stack/bring-back minima — everything else identical —
(a) actually produce winner-shaped candidates, (b) get any into the
book, and (c) score?

## Arms

- **Control:** the ATLAS reproduction path (dose-zero regeneration +
  verbatim role injection; exact source reproduction gate) — identical
  to the S arm's control, re-validated per cell against the ATLAS
  attempt-2 receipts (C and S, 1e-6).
- **Treatment:** identical environment plus exactly ONE lever:
  `OPEN_BOOM_SOLVES=8`. Open solves drop `qb_stack_min`/`bring_back_min`
  only; RB prohibitions and salary bounds unchanged; stride spreads
  them across the boom order; candidates keep primary tag `boom` with a
  secondary `open` tag. Budget parity enforced by the all-boom
  truncation machinery (equal candidate counts per seed).

## Endpoints and gates

1. **Vacuity gate (fail-closed):** zero surviving open candidates
   across all seeds kills the cell — a dead lever must never report a
   score.
2. **Mechanism (census-quantified):** structure census of open-tagged
   candidates (stack/bring-back/concentration distributions;
   `n_outside_mandate`) — the carve must occupy the winner-mode region
   (stack ≤1, no bring-back, concentration ≤3 territory). Plus
   `open_selected_count`: how many open candidates the unchanged
   exact-80 selector actually takes.
3. **Primary:** paired realized S over 53 slates with the co-primary
   block and the selected threshold grid.
4. **Anatomy instrument:** selected-book winner overlap versus the
   chance null, both arms.
5. Cross-run binding: control C/S must reproduce the ATLAS receipts;
   identity-capture must reproduce canonical S (1e-6 each).

## Preregistered reading

- ΔS positive with mechanism (open candidates selected AND overlap
  gain): the mandate relaxation earns a prospective shadow design; any
  production change only via the prospective record.
- ΔS null with open candidates selected: shapes reached the book and
  did not score — the mandate is not the binding constraint at this
  dose; the residual blocker is the law/selection lane.
- ΔS null with open candidates NOT selected: the selector rejects open
  shapes under the current objective — the finding moves to the
  selection lane (the coverage objective, not the mandate, is the
  gatekeeper).
- ΔS negative: the ledger's old wholesale-deletion warning generalizes
  to the carve; closed at this dose.
- NO dose sweep on this corpus, ever; the next dose is a new frozen arm
  or a prospective shadow.

## Governance

Outcome-aware; one active historical-score arm at a time (nothing else
runs); create-only receipts; reused Cloud Run job (rule 5); clean-
archive image from the exact commit; runner/chain/protocol shas in the
launch manifest. No production change licensed by any outcome.

## Reality smoke (rule 1, outcome-blind — required before this freeze)

2023 W1, full mechanics: both arms generated, reproduction and budget
gates, open-candidate census, exact-80 selection both arms, receipt
serialized; no actuals query. Disposition recorded verbatim below
before launch.

- Smoke disposition: PENDING — this protocol is NOT FROZEN and the
  chain must not launch until the real smoke output is recorded here.
