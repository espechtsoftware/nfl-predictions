# The admission cap as a retrieval lever — result (read 2026-09-16 00:45Z)

Preregistration: `reports/2026-09-15-prereg-admission-cap-lever.md` (frozen f9ed9475 before any read). Runner:
`scripts/paid_source_admission_cap_v1.py` (branch `production/paid-source-ladder-direct-20260915`, 5cfadd78), reusing
the 2026-09-15 ladder records' player annotations; 54 slates, 9 cells each (cap200 / cap400 / cap800 / capall by mean
matchup edge × sources on-on and off-off, plus the source-free tail200), coverage-194-v1 to K80 unchanged, same
realized points and the same ownership field (identical seeds). Evidence: `reports/admission-cap-lever-20260915/`
(manifest, verbatim read, per-slate table). Mechanics smoke on 2023 W1 passed before the outcome run; 54/54 slates,
no failures.

## Result (verbatim read in `read.txt`)

| primary (K20, family 0.9875, sign test required) | mean | interval | W/L/T | sign p | verdict |
|---|---|---|---|---|---|
| 1 points, capall − cap200 (sources on) | −0.68 | [−2.17, +0.29] | 23/28/3 | 0.58 | NO_EFFECT |
| 2 finish, capall − cap200 (sources on) | +0.005 | [−0.034, +0.030] | 23/28/3 | 0.58 | NO_EFFECT |
| 3 points, tail200 − cap200 | +1.16 | [−0.13, +2.04] | 24/28/2 | 0.68 | NEAR_MISS |
| 4 points, sources on − off at capall | −1.03 | [−4.31, +3.15] | 23/24/7 | 1.00 | NO_EFFECT |

Secondaries: capall − cap200 at K80 +1.49 [+0.49, +3.02], 28/21, sign p 0.39 (near miss); tail200 − cap200 at K80
+1.98 [+0.38, +2.87], 28/23, p 0.58 (near miss); cap800 − cap200 at K20 +0.51 (near miss); all finish contrasts null;
sources at capall null at every K.

| rule (sources on) | admitted | admitted ceiling | slates whose admitted set holds a 194+ | K20 max | K80 max | K20 best-finish pct | weeks K80 ≥ 194 |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap200 (control) | 200 | 181.1 | 13 | 165.1 | 176.7 | 10.40 % | 10 |
| cap400 | 400 | 187.0 | 17 | 165.1 | 177.2 | 10.75 % | 10 |
| cap800 | 800 | 191.9 | 24 | 165.6 | 179.1 | 10.70 % | 14 |
| capall | 3,317 | 202.1 | 36 | 164.4 | 178.2 | 9.88 % | 10 |
| tail200 (source-free) | 200 | 184.8 | 14 | 166.3 | 178.7 | 8.70 % | 9 |

Pool ceiling 202.7; 36 of 54 slates hold a 194+ candidate. With both sources off, capall admits only 951 (the
qualification gate needs two annotated players) yet its books are indistinguishable from the on-on books.

## Reading

1. **The cap was the admission bottleneck, and removing it changes nothing downstream.** Admitting everything lifts the
   admitted ceiling from 181 to 202 — the tail is now in front of the selector in 36 slates instead of 13 — and the
   K20 book does not improve at all (164.4 vs 165.1); K80 gains 1.5 points, a near miss. The regret moved from the
   gate to the selector: coverage-194 over 40,000 simulated worlds does not recognise the realized-best lineups when
   they are offered. This is the "selection is closed for the current simulator" finding of Addendum 95 reproduced on
   a fresh instrument: the world model's ordering carries too little information about realized tails.
2. **A source-free tail-aware gate is as good as the paid-source gate, or slightly better** (tail200 near miss at K20
   and K80, best finish percentile of any rule at 8.7 %). The paid data does not earn its place even as an admission
   score.
3. **The sources do not matter once the gate is lifted** (contrast 4 null at every K), which closes the question the
   ladder left open: it was not the cap hiding vendor value.

Instrument checks: admission monotone in the cap (200 → 400 → 800 → all), tail200 independent of the source state,
candidate order equal to the artifact in every slate, field receipts identical to the ladder run's (same seeds).

## Consequences (from the frozen table)

- Primaries: nothing passes → **close this lever**: the retrieval regret is not in the admission gate.
- Paid sources: contrast 4 null at capall, on top of the ladder's nulls → **do not renew Fantasy Points or SIS on the
  evidence held**; the exact retrieval use is closed for both; the only remaining route to a value claim is a
  prospective 2026 shadow with a live source capture, which nobody has built and which this result does not justify
  building.
- Where the remaining ~20 points of retrieval regret live: in the selector's world model, not in admission or in the
  vendor data. The next lever, if any, is a better-calibrated tail (the post-mortem measured the simulator's 200+
  over-prediction at 3×) — a modelling question for the lab, preregistered before any outcome is seen.

## Deviations

Same as the ladder run (direct runner, sha256 identities, three-season cluster bootstrap with sign tests reported);
`capall` with sources off admits fewer candidates than with sources on because the qualification gate is itself
source-dependent — recorded, not corrected, since the design froze the gate.
