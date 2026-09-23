# §6.5 — the PREREG-098 field sampler passes its frozen gate on the Week-2 field; and a 2026 ownership-schema trap

Delegated by production (`e67103d7`, external review §6.5). Report only; nothing adopts. Script
`reports/lab-handoffs/2026-09-22-sampler-gate-week2.py <dir holding the frozen prereg098_field_sampler.py>`.

## Gate result (frozen v4 sampler from nfl2 `7e8126b`, unmodified; criteria exactly as PREREG-098 §Gate(a))

Real field: the 2026 Week-2 Millionaire, 172,692 entries (172,450 = 99.9% scorable in the frame's worlds). Worlds: the
Week-2 Saturday run's incumbent bank (10,000). Sample: 200,000 lineups, seed 98, stack 0.70, salary floor band
48,500–50,000, 6 IPF rounds. Cutoffs at the frozen fractions of an 832,342-entry reference field.

| criterion | bar | Week 2 | Week 1 (frozen record) |
|---|---|---:|---:|
| per-world cutoff corr, top-100 / top-1,000 | > 0.95 | **0.982 / 0.987** | 0.982 / 0.987 |
| top-1,000 mean \|diff\| | < 3 | **2.98** | 2.63 |
| realized top-1,000 cutoff vs real | within 5 | **194.8 vs 199.0** | 226.0 vs 228.2 |
| realized cash cutoff vs real | within 5 | **135.1 vs 137.2** | 163.5 vs 165.5 |
| ownership error sum | < 0.5 | **0.313** | 0.291 |

**PASS on all criteria in both weeks.** The one-signed soft bias recurs: the sampled field's per-world cutoffs sit 2.3 / 2.6 /
1.5 points *below* the real field's at top-100 / top-1,000 / cash (real lineups are optimizer-built and sharper than an
ownership-matched sample), and the top-1,000 margin is thinner in Week 2 (2.98 against a bar of 3). As PREREG-098 noted, a
uniform shift does not change what a ranking objective selects; absolute finish probabilities read slightly optimistic.

## The trap I hit first: `contest_ownership` changed grain in 2026

My first run **failed** (ownership error 1.05, plus a fill-loop shortfall). The cause was mine: 2026 ownership rows are **one
per player per roster slot** (a WR has a WR row and a FLEX row; mass per contest ≈ 899% = 9 players), while 2022–2025
rows are one per player (0 FLEX rows). I had taken `MAX(pct_drafted)` per player, which drops the FLEX share, so the target
carried 8 players of mass. With `SUM` over slots the gate passes and the frozen fill loop fills 200,000 without issue.
Neither the "failure" nor the fill shortfall is a sampler defect.

**Swept the class** (rule 4):
- **My scripts:** the tilt study, the sort-key study (both scripts) and this gate used `MAX`. All are fixed to `SUM`. The
  re-runs change nothing material: W2 tilt ρ −0.284 → −0.282, partial −0.214 → −0.207; sort-key `own_real` W1/W2 ρ
  +0.032/−0.247 → +0.030/−0.270 (still flips; no key qualifies). Production's Week-1 tilt run used the `MAX` script, so
  its "slate noise" verdict is on the same footing and very likely unchanged.
- **Production, for 2026 data:** `src/nfl_dfs/analysis/leaderboard.py:232` takes `AVG(pct_drafted)` per player (roughly
  halves a flex-eligible player). `src/nfl_dfs/models/ownership.py` de-duplicates on (contest, player), which keeps
  **one** slot row, then averages. History is unaffected. If either is ever fed 2026 standings, it understates the
  WR/RB/TE ownership.
- **README → Data deficiency log:** a row added.
