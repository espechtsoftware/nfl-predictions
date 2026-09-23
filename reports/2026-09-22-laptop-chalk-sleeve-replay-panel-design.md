# Design (NOT frozen): the chalk-core sleeve's preregistered replay panel

Production's condition for the sleeve (`b2895875`): paper-only this week; **adoption only from a preregistered replay
panel against real Millionaire ownership.** This drafts that panel so it can be frozen when the laptop CPU frees
(L01 ends ~Thu 03:30). Freezing and the decision rule are production's and the operator's call.

## What is missing today: historical sets files
`scripts/ownership_sets.py` writes live weeks only (`sets --week W --group G`). The replay needs **walk-forward sets per
historical slate**: for season S, fit on seasons < S, predict every S slate from the replay panel's pre-lock inputs, and
assign LOW/CHALK by the same rank rule. Proposed: a `replay-sets --season S --out DIR` mode writing one
`<season>-w<WW>.csv` per slate with the live file's schema, keyed by `gsis_id` so the nfl2 frames join. The laptop can
write it on a branch if production prefers; the model and the rank rule stay production's.

## Proposed design
- **Slates:** the development slates with Sunday Millionaire ownership, 2023–2024 (2022 has no prior fold for the
  ownership model; 2025 is sealed in nfl2). PREREG-098 found 53 ownership-matched slates in 2022–24, so about 35 are
  expected in 2023–24. **Outcome-blind support census first** (rule: preflight support): sets coverage of every frame
  and the LOW/CHALK counts per slate.
- **Arms at D3200, `dual_emax` K80, `--max-per-game 4`** (the live Week-3 construction): CTRL; SLEEVE_L1 (≤ 1 LOW,
  ≥ 1 of top-15 by `pred_own`, salary ≥ \$49,500, 25% of boom solves); SLEEVE_L2 (same with ≤ 2 LOW). Same generation
  and selection banks per slate; the sleeve replaces solves, so totals are equal. The vacuity check is a book overlap
  below 100%.
- **Primary endpoint (finish, not points):** the share of an ownership-consistent synthetic field above the book's best
  lineup, from the PREREG-098 IPF sampler, which is gated on both real 2026 fields (W1 PASS, W2 PASS: laptop `d7c3cc2b`).
  Lower is better; paired per slate-bank.
- **Co-reported:** realized book best and mean, ≥ 194/220 clears, the LOW- and CHALK-count shape of pool and book
  (\`shape_receipt\`), and duplication against the synthetic field.
- **Decision rule (proposed, in-season form):** flip-eligible iff the pooled primary improves with a season-cluster
  90% interval excluding 0 **and** no season is worse. Otherwise close at this form. A permanent adoption still needs the
  lab's standard six-season bar.
- **Cost:** 3 arms × ~35 slates × banks. L01 measured ~95 min per three-arm D3200 slate-bank on 8 workers, so 2 banks ≈
  70 slate-banks ≈ 14 h of laptop CPU. That fits between Thursday and the Week-4 build.

## Open questions for production
1. Will production write the historical sets (the `replay-sets` mode), or should the laptop?
2. Is the IPF-sampler finish endpoint acceptable as the primary, given its known one-signed soft bias (2–3 points)?
3. Is D3200 acceptable, as for L01?

*Side note:* \`ownership_sets.py\` trains on 2022–25, one row per player, so \`MAX(pct_drafted)\` is correct there. **If the
2026 live Spearman (0.640/0.628) read 2026 \`contest_ownership\` the same way**, flex players' actual ownership was
understated (2026 rows are per slot; sum them). It's worth a re-check. The rank correlation likely moves only a little.
