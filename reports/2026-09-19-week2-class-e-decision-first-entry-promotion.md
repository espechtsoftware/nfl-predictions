# Week-2 class E decision: first-entry promotion by the mean rule (authorized 2026-09-19 22:27Z)

**Decision (Erich, in chat, 2026-09-19 ~22:27Z: "Yes please do the ranking that would move 5 to 1").** Apply the labs' frozen
first-delivered promotion rule (the *mean* rule) to the Week-2 final delivered book before upload. Order-only: the clean-or-soft
row with the highest selection-bank mean among delivered ranks 1-30 moves to rank 1 (the Millionaire entry); the rows above it
shift down one; membership and ranks 31-97 are unchanged. The rule is executed on Sunday's own final book, so the promoted rank
may differ from the 5 observed on the Saturday D6400 book.

**Identity.** Rule `reports/reviews/evidence/2026-09-19-first-delivered-promotion.py` (research branch `research/2026-09-paid-source-preflight`
>= `0da7fdf0`), sha256 `36ffcbcedc9b1b46d5aea5c9d04b425f0b842e3569a53c20802ef39f36af959f`. Consumer `promote_first.py` v1.1, sha256
`3590193e2483d4ee…`, published with receipts and refusal/guard tests at nfl2 `lab/workstation-reply-bank991-20260918` `ddc856a`
(`handoffs/tools/promote-first-v1.1/`); durable copies in `/home/erich/week2-sunday/`.

**Evidence (conditional-simulation, not NFL efficacy).** Labs' frozen eight-book packet sha `87262e06…`, result sha `9ffaa4a7…`
(`reports/2026-09-19-d6400-reselection-and-ordering-results.md`): on the fresh v4.3 D6400 book the rule promotes rank 5 / candidate
782: first-entry simulated mean 134.79 -> 143.30 (+8.51, MC95 [8.07, 8.94]); P220 0.435% -> 0.600% (+0.165 pp; a second audit
gives +0.075 pp with an interval crossing zero); labelled winner-score proxy +0.0036. Cost: contest block 2-24 (Flea Flicker) loses
0.195 expected-max points and 0.095 pp P220. Workstation cross-reads: portable replays frontier 4,496 / reselection 35,819 / tail
9,144 fields with zero differences; the promotion reproduced on the packet with Δ 0.0 (float32 sums in frame-row order).
Alternative (labs `ed3a4b8a`): proxy/P220 head rules pick rank 2; superiority over the mean rule unresolved. Erich chose the mean rule.

**Execution (Sunday, after the cleared after-build chain; the chain itself is unchanged).** `/home/erich/week2-sunday/run_promotion.sh
AFTER_DIR RUN_DIR OUT_DIR TAG`: staging copy of `paid-vetted-replaced/` -> cleared `vet_book.py` on the FINAL book -> `promote_first.py`
(bindings: frame sha, replace.json output shas, reconstructed vetter input rows, flags by position/salary/name, every row a run
candidate; fresh DK/report designations raise weights; fresh OUT / report Out / gated QB forced ineligible) -> unchanged
`emit_dk_upload_csv_v1.py` on the promoted dir -> `upload-<tag>-promoted-paid-vetted-all.csv` + `lineup-sheet-<tag>-promoted-paid-vetted-30`;
`promotion/PROMOTION-RECORD.md` records both upload sha256s, the permutation, the rank->contest moves, and the rollback.

**Rollback.** The chain's `upload-<tag>-paid-vetted-all.csv` is untouched; uploading it instead reverts everything.

**Monitoring.** The Week-2 evidence record reports the first-entry outcome and the displaced Flea-block row, adverse or not. One week
cannot establish efficacy; continuation is governed by the in-season adoption track v2 (candidate-specific, reversible).
