# Payout retro-test on the real Week-1 Millionaire field (2026-09-14)

Question: does choosing lineups by their *finish* against the real field pick a different book than expected-max
selection does, and would it have done better? First test ever run on the finish axis in this project.

Setup. The final Week-1 build's 800-candidate pool (`20260913T160405364118Z`), its 10,000 simulated worlds (incumbent
law, players × worlds), the real Millionaire field (831,028 lineups from the standings export, 99.88% of slots matched
to the simulation frame; unmatched slots are inactive players scored 0), and DraftKings' actual 34-tier payout table
($1,000,000 to 1st, $8 at place 173,275). For every world, every field lineup is scored and the world's payout cutoffs
are read off; each candidate's world score maps to a payout; averages over worlds give expected payout, P(cash),
P(top-1,000), P(top-100). Actual results use official points and the actual field ranks. Scripts and data:
`/home/erich/week1-sunday/payout/` (`payout_retro_test.py`, `candidates_payout.csv`, per-world cutoffs).

## Results, K=30 (the operator's entry size) and K=80

| book (K=30) | overlap with DEMAX-30 | sim E[payout]/entry | P(cash) | P(top-1,000) | P(top-100) | actual best | actual $ | best rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEMAX first 30 (the machine's order) | 30 | $26.43 | 26.3% | 0.56% | 0.087% | 203.84 | $71 | 13,594 |
| top 30 by P(top-1,000) | 12 | $32.98 | 25.8% | 0.78% | 0.128% | 203.84 | $71 | 13,594 |
| top 30 by P(top-100) | 6 | $42.55 | 23.6% | 0.71% | 0.146% | **224.54** | **$133** | **1,558** |
| top 30 by capped expected payout (top-100 tier value for every top-100 finish) | 9 | $24.88 | 29.6% | 0.74% | 0.121% | 185.70 | $64 | 54,767 |
| top 30 by E[log(1+payout)] | 2 | $7.29 | 37.5% | 0.39% | 0.044% | 191.60 | $148 | 36,098 |
| top 30 by raw expected payout | 5 | $111.31 | 20.7% | 0.41% | 0.081% | 187.84 | $50 | 47,327 |

| book (K=80) | overlap with DEMAX-80 | sim E[payout]/entry | P(cash) | P(top-1,000) | P(top-100) | actual best | actual $ | best rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DEMAX first 80 | 80 | $20.22 | 24.6% | 0.48% | 0.076% | 224.54 | $211 | 1,558 |
| top 80 by P(top-1,000) | 37 | $26.08 | 25.6% | 0.63% | 0.102% | 224.54 | $250 | 1,558 |
| top 80 by P(top-100) | 32 | $28.62 | 24.0% | 0.57% | 0.113% | 224.54 | $262 | 1,558 |
| top 80 by capped expected payout | 33 | $23.19 | 29.5% | 0.60% | 0.094% | 224.54 | $274 | 1,558 |
| top 80 by raw expected payout | 23 | $55.44 | 21.7% | 0.43% | 0.078% | 209.60 | $158 | 7,880 |

Whole pool: mean simulated expected payout $9.19 per $5 entry (the pool is +EV under its own simulator against this
field); 143 of 800 candidates actually cashed; best actual candidate 228.50 (rank 961). DEMAX rank correlates only
0.42 (Spearman) with P(top-1,000) across the 90-lineup book.

## Reading

1. **Raw expected payout is a lottery objective and cannot be estimated.** The top candidate's $202 comes from 2 worlds
   in 10,000 in which it wins the $1,000,000; the ordering is noise, and the book it picks did worst on the actual
   outcome. Ten thousand worlds cannot resolve a 1-in-10,000 event; do not select on it.
2. **The estimable finish objectives pick a materially different book.** Top-30 by P(top-1,000) or P(top-100) shares
   only 6–12 lineups with the machine's first 30 (32–37 of 80 at K=80) and has 25–40% higher simulated P(top-1,000)
   and 50–70% higher P(top-100), at slightly lower P(cash). It is the same pool; the difference is which candidates are
   retrieved.
3. **On the one real week, they did better.** P(top-100)-30 found the 224.54 lineup (rank 1,558, $133 vs $71); at K=80
   every finish objective out-earned DEMAX ($250–274 vs $211) with the same best lineup. One week: a sign, not a
   verdict.
4. Half-and-half books (DEMAX core plus finish fill) sit between, as expected.

## What this does and does not establish

Established: the finish objective, in its estimable form (probability of a top-N finish against the field), is a
*different* selector from expected-max, it can be computed from the tools we have, and on the first real field it
would have earned more. The August diagnosis ("the money path asks the selector the wrong question") survives its
first contact with data.

Not established: any historical or prospective edge. The field here is known after the fact; live, it must be modeled
before lock from projected ownership (72 weeks of real per-player ownership exist for 2022–2025, overlapping 54 of the
72 development slates). The test also used one law and one week.

## Next (proposed as PREREG-098)

Build an ownership-consistent field sampler (lineups drawn to match the week's real per-player ownership under the
salary cap and roster shape, with the real field's duplicate structure as a check on this week's data), then on the
54 development slates with real ownership run the P(top-1,000) and P(top-100) selectors against sampled fields versus
DEMAX, scored by realized finish rank against the *actual* ownership-implied field and by realized best score, three
banks, frozen GLOBAL_WEMAX_PROXY as a secondary so the result is comparable with the ledger. If it passes, the live
path gets a projected-ownership field model (the August contest-aware ownership model already passed its calibration)
and the selector switches objectives; the Week-2 book runs it as a shadow either way.
