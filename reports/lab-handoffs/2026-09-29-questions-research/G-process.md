# Theme G (research process) and Theme H (H1, H3, H4) — 2026-09-29

Analyst: research panel, read-only. Scripts and intermediate files in `q/G/` (`bootstrap_fast.py`, `comparisons.py`,
`g2_power.py`, `bootstrap_verdicts_fast.csv`, copied L-series result files under `q/G/res/`, the ledger rows in
`ledger_Lrows.txt`, the winners study in `winners_study.md`). Compute: single-threaded numpy/pandas on 72-row frames.
No dollar figures. Nothing about the coming week.

Sources read: nfl2 `LEDGER.md` (laptop rows branch, L01–L18), the L09–L14/L17/L18 result JSONL and reader outputs,
`scripts/l13_report.py` / `l17_report.py` (the rule), system-study Addenda 12–120 (closed verdicts), the 09-12 review
package §2, the 09-25 outside-the-box report and plan, the 09-22 unturned-stones audit, the Week-2 §14 and Week-3 §10a
proposal lists, the 09-19 adoption track v2, HANDOFF (16:54 panel-vs-field entry; the class-selector withdrawal), the
09-20 data-source map §5, Addendum 65, `scripts/linestar_ownership_capture.py`, PREREG-O1 + amendment 1, the Week-4
operating handoff §9, and the new winners study (`origin/review/winners-study-20260929`).

## The objective has changed three times; most closures predate the current one

| period | objective the verdict was read on | where |
|---|---|---|
| Jul 26 – Aug 9 | weeks with best-of-40 (later 80) ≥ 194 on the 107-slate replay (tail clears), LOSO ≥4-of-6 | system study Add. 11–120 |
| Aug 27 – Sep 25 (lab) | share of a 200k sampled real-ownership field above the book's BEST lineup ("d", lower better) — still a tail-of-book functional | L01–L06, PREREG-09x |
| Sep 27 – 29 (lab) | tickets: rows of a K144 / K36 book at or above the realized sampled field's p89 (primary), p95/p99/p99.8 co-reported | L09–L18 |
| Sep 27 – 29 (live) | the book's mean per row against the field's mean (MEAN +23 / +31 per row over EMAX on W1 / W3); the winners study now proposes "the book's score against the field" as the weekly judge | W3 post-mortem §6, §11; winners study rec. 4 |

Everything in the July–August ledger was decided on the first row. The lab's L01–L06 were decided on the second.
Only L09 onward (nine reads, all on the same 36 slates) and the two live weeks were decided on anything resembling the
current objective. That is the whole point of G1.

---

## G1. Closed verdicts decided on another objective, and whether to re-read them

Legend for "re-read?": **YES** = the mechanism plausibly moves the mean track or shallow-line tickets and has no read
there; **PARTLY** = an L-series read exists on tickets but not on the mean track or vice versa; **NO** = the mechanism
cannot affect the mean track (it only touches the simulator's tail) or was already re-read.

| lever | verdict and objective it was read on | what the tail read actually said | re-read under mean track / p89–p99 tickets? | expected sign on the mean track (my judgement) |
|---|---|---|---|---|
| **Late swap (score-chasing)** | Add. 67: NULL (+0.9 mean-best, flat P(187)) on best-of-40 ≥187; 09-13 audit: swap220 +0.2–0.8 mean-best on K30/K80 | then **L11** on tickets89: +11.1 % both seasons (2023 452→484, 2024 527→604), paired 30–32 → NOT SUPPORTED by the frozen rule; realized mean per row +1.7 | **PARTLY** — already read on tickets, never on the book mean; the frozen paired clause is what failed (see G4: the direction survives 86 % of bootstrap draws) | small positive (+1–2 per row) — a tickets-first rule masks it |
| **Exposure caps (per player)** | Add. 36 MAX_QBS / cap8+var4: DECLINED for GPP because it lost the two ≥237 weeks; "concentration buys median and ROI at the tail's expense" | **L17/L18** on tickets89 at K36: X50 is the peak (looser HARMFUL, tighter NEUTRAL/HARMFUL); 09-21 isolated cap effect +11.3 mean, +26.6 best on the W2 pool | **NO for the level (done)**; **YES for the *composition*** (Q/D-status caps, DST cap dose, the Week-2 class-C 5/7) — never read on any objective | positive on the mean track; Add. 36 itself recorded "median and ROI up in every arm" — the decline was purely the old objective |
| **Stack mandate QB+2 + bring-back** | Add. 28 (bring-back −5.6 mean-best, −4 tail weeks), Add. 63 (QBS1 17 vs 25 tails, "loosening bleeds") — best-of-N ≥194 | L10 tested CAP5 (makes QB+3 buildable): tickets89 −1.6 %, seasons split (2023 −20, 2024 +3) → NOT FLIP-ELIGIBLE; the mandate itself has **no read on the mean track** | **YES** (B5). Field top-1 % has two-deep stacks 30 % / bring-backs 41 %; we are 100 %/100 %; 3.7 games per row vs 5.4. The cost of a *mandate* on E[row] is a correlation-neutral quantity the tail objective could not see | negative for the mandate (i.e. relaxing it raises the mean by 1–3 per row) — moderate confidence; the tail cost (Add. 63) is real and stays for the tail sleeve only |
| **p90 punt valuation** | Add. 28 punt mandate KEEP (−4.4 / −3), Add. 77 NOPUNT 26 vs 25 (deletion of mandate + boost fires), Add. 80 keeps the p90 *valuation* because "true-deletion tests cost tails" — all best-of-40 ≥194 | Q4b (p90 vs plain mean for the leverage batch) has **no read** on any objective; W3: 399 boom lineups held a sub-1-point player; punts valued at p90 while the mean track scores them at the mean | **YES** — cheapest and most direct: p90 valuation is a *tail* instrument sitting in the money path of a *mean* selector | negative on the mean track (valuing a 2.3-projection punt at its p90 buys row-level variance the mean track does not want): −1 to −3 per row in lev/boom rows that carry them |
| **Market blend weight (0.45 model / 0.55 market)** | Add. 14/15 (adopted on best-of-40 tails + MAE), Add. 106 A01 model-only unsupported-neutral (11 vs 11 at 194); **L04** on the lab's "share above the book's best": MODEL_ONLY and w0.70 both significantly worse; CLOSED for 2026 | L04 co-reported book mean 183.2 (live) vs 179.6 / 181.7 — the *mean* also favoured the live blend; winners study §3.2: the same K36 book with **no market prices (2022 replay)** sits BELOW the field (−0.17 sd) vs +0.08 sd with them | **NO for the direction (market helps the level too)**; **YES for w < 0.45** (nominated in L04, never run) and for the class-C "market-agreement pull" | more market weight: positive on the mean track, plausibly +1–2 per row — supported by L04's co-report and the 2022 holdout |
| **All-boom pool (L01 ALLBOOM_CEIL)** | L01: ≥194 clears 90 vs 92 FAIL, pool oracle 2024 −0.46 FAIL → NOT FLIP-ELIGIBLE (tail rule on 54 slates 2022–24) | W3: lev rows mean 137 vs boom 116 (lev is *better* on the mean track); L13's PMO shows a pure mean solve beats both batches at p89 | **NO in this form** — the question was superseded: PMO_X50 (a sequential mean solve, no boom/lev split) already beat the pool's mean track by 27.7 % tickets89 and +6.3 mean per row; the pool-batch mix only matters for the tail sleeve | n/a |
| **Salary floor 49k** | Add. 91 (26 vs 27), Add. 108 (11 vs 11, mean best 173.06→172.43) — tails; "stays on no-reason-to-change" | never read on the mean track; L17/L18 books keep the 49k floor inside PMO | **LOW YES** — cheap arm in the PMO harness (floor 0 / 47.5k / 49k); expected effect small either way | ≈ 0 |
| **MAX_PER_GAME = 4** | Add. 49 MPG4 20 vs 18 tails but worse mean/median → tested-neutral; L01 MAXGAME4 FLIP-ELIGIBLE on clears; **L10** CAP5 vs CAP4 NOT FLIP-ELIGIBLE on tickets89 | L10 *is* a current-objective read; the seasons disagree (2023 favours 4, 2024 favours 5) | **NO** (done; neutral) | ≈ 0 |
| **Cross-entropy worlds (N_CE)** | Add. 100 ADOPTED 29 vs 27 at fixed budget; later immutable confirmation 26 vs 27 → research-only, `N_CE=0` (all best-of-40 ≥194) | pure world-generator lever; on the mean track it changes which boom rows exist, not their valuation | **NO** — the mean track selects by projected sum; a different world sampler only matters through the tail sleeve | ≈ 0 |
| **TabPFN marginals** | Add. 49/50: +6 tails, best mean-best → adopted (best-of-40) | marginals shape the simulator's per-player distributions; the projected *mean* is unchanged by construction (Add. 107 audit: post-shaping means invariant) | **NO for the mean track**; relevant only to the tail sleeve and the P(≥line) tools (which L14 found lose to MEAN at every line) | 0 on the mean track by construction |
| **Model ensemble K (K=3 vs K=1)** | Add. 56 (26 vs 14, adopted), Add. 107/110 (K=1 wins aggregate tail, fails stability), Add. 118 K=1 promoted on the operator's aggregate-tail utility — all tails | K changes the *mean* projections (K=1 differs from the K=3 member mean by 0.28 points per player, Add. 107); prospective K=1/K=3 paired shadows were deployed (Add. 119) — I found no graded read of them on the mean track | **YES, cheap**: the paired shadows exist; grade them on book mean vs field, not on ≥194 | unknown; ensemble averaging should help a mean objective (lower variance) — K=3 favoured, low confidence |
| Chalk fade (LEV_PENALTY) | Add. 80 TRUENOFADE 23 vs 25 → kept (tails) | the fade never fired in 2026 (W3 §6.4); winners/field are chalkier than us | **YES, but reversed**: the current-objective question is an ownership *tilt toward* chalk (L12 inconclusive on lag labels; winners study §4.1 +4–6 per row with the blended predictor inside the optimizer) | the fade is negative on the mean track; a tilt is positive |
| Dollars / fixed-line objective (Add. 70), PEAK10, COVF89-type coverage selectors (Add. 65, L09) | dollars NULL at 4 entries (tails); coverage selectors negative | L09: COVF89 is the worst arm at p89 (−20 %, the most robust HARMFUL in G4) | **NO** — coverage/uniqueness selectors are now doubly closed (old and new objective) | negative |
| Finish objective (PREREG-098 FIN1000/FIN100 vs DEMAX) | NEGATIVE on realized finish and points (D800, K80) | this *was* close to the current objective, but at K80 EMAX and dose 800; it ranks by simulated P(top-N), which L14 later showed loses to MEAN at every line | **NO** — the mechanism (simulated finish probabilities) is what the current reads reject | negative |
| Gumbel / Schaake / EPI / GFlowNet / TD-ledger (Add. 84–99) | all tail generators, all negative | none touches the mean track | **NO** | n/a |

**Bottom line for G1.** Six levers deserve a read under the current objective and have none: the stack/bring-back
*mandate* (B5), the p90 punt valuation (B3/Q4b), market weight below 0.45 and the market-agreement pull, the
ensemble-K paired shadows, the cap *composition* (status caps), and the late swap on the book mean (a co-report the L11
files already contain: realized mean per row 122.07 → 123.73). Six are closed for good under both objectives (coverage
selectors, finish objective, the world-generator family, TabPFN/CE on the mean track, MAX_PER_GAME). Confidence: high
that the tail-era closures do not transfer (the ledger's own "post-selection law" says verdicts don't cross a changed
downstream stage; the objective is downstream of everything); moderate on my sign guesses.

---

## G2. Power of three live weeks, and a symmetric in-season rule

**The unit is the week, not the lineup.** Week 3's entered book: 144 rows, mean 120.45, per-lineup SD 23.7
(`lineup_by_lineup.csv`; boom rows 118.9 ± 23.6, lev 132.5 ± 20.7). Naively 23.7/√144 = 2.0 per week. But on the
panel the SD of a K144 book's *mean* across slate-banks is 12.0 (L13 MEAN) and 16–17 for the K36 books (L17/L18 X50):
a book's rows share the slate's level and a core, so the effective number of independent lineups per week is about
2–4, not 144. Per-lineup pairing between two selectors is not even defined (different rows); the paired quantity is
the per-week difference of book means on the same pool, whose SD I took from the panel (`g2_power.py`):

| comparison (same pool, same slate-bank) | mean d | SD of d per week | corr(A,B) |
|---|---:|---:|---:|
| L13 PMO_X50 − MEAN (K144) | +6.3 | 8.9 | 0.84 |
| L13 MEAN − EMAX (K144) | +3.7 | 6.4 | 0.85 |
| L09 MEAN − EMAX (K144) | +2.9 | 6.8 | 0.83 |
| L17 X67 − X50 (K36) | −0.2 | 5.2 | 0.96 |
| L18 X40 − X50 (K36) | −1.2 | 4.6 | 0.96 |
| L18 X25 − X50 (K36) | −2.5 | 8.3 | 0.86 |
| L11 swap − keep (K144) | +1.7 | 6.8 | 0.88 |
| L12 T10 − MEAN (K144) | +0.3 | 3.0 | 0.97 |
| L14 EMPP99 − MEAN (K144) | −0.2 | 3.1 | 0.97 |

Minimum detectable difference in book mean (two-sided α 0.05, power 0.80, t-based for small n):

| SD of weekly d | class of change | n = 1 | n = 3 | n = 6 | weeks to detect +5 | weeks to detect +10 |
|---:|---|---:|---:|---:|---:|---:|
| ~3 | re-rank of the same pool with a small tilt (L12/L14 type) | no test possible; a single week must exceed ~8 to be 2.8 SD | 9 | 4 | 3 | 1 |
| ~5 | cap-level change (L17/L18 type) | ~14 | 16 | 7 | 8 | 2 |
| ~6.5–9 | selector swap (EMAX↔MEAN↔PMO) | ~18–25 | 20–28 | 9–13 | 13–25 | 3–6 |

Reading: three live weeks detect only a ~20–28-point per-row gap between selectors on the same pool, or a ~9-point
gap from a small tilt; six weeks halve that. The live MEAN-over-EMAX reads (+23 W1, +31 W3) were each individually
larger than the panel's one-week bar (3–5 SD of the panel's weekly d), which is why entering on them was defensible;
a cap change (+1 to +3 per row on the panel) is undetectable live inside a season. **Tickets are worse**: at K36 the
X50 control pays 4.6 tickets89 per slate-bank with SD 5.5 and zero tickets in 21 of 36 slate-banks — a K36 book's
weekly ticket count is a coin with a fat zero.

**Proposed symmetric rule (one reader, both directions).**
1. *Unit and metric.* Every armed change keeps its control as a paper book built from the SAME pool at the same
   information time, both scored Monday on the realized field. Primary: the paired difference of book mean per row
   against the field's mean (the winners study's recommendation 4: "judge the system on the book's score against the
   field, not on the week's dollars"). Co-report: tickets at the realized p89/p95/p99 lines, cumulative.
2. *Statistic.* Cumulative paired difference D_n = Σ d_w over the n scored weeks, with a *prior* SD per week σ from the
   same-family panel comparison (3 / 5 / 7 for tilt / cap / selector; the table above), so SE_n = σ√n. Report z_n = D_n / SE_n
   and the running mean D_n / n every week (monitoring, not inference — the track's §3 words).
3. *Decision, symmetric.* ADOPT-and-keep (a candidate) when z_n ≥ +2 and the sign held in ≥ 2 of the last 3 weeks;
   WITHDRAW (an armed change) when z_n ≤ −2 by the same computation; otherwise HOLD the present state and keep the
   paired shadow running. The same evidence that arms a change is what removes it; a change entered on one +3 SD week
   is withdrawn the first time its cumulative z drops below −2, not on a single −1 SD week.
4. *Integrity failures* (identity, legality, leakage, a non-player in a row, a defective input week like W2) stop a
   trial at once and the week is excluded from both arms — this is already the track's rule and it is asymmetric
   on purpose.
5. *Sample-size honesty.* Under this rule a +5-per-row cap change needs ~8 weeks to reach z = 2; say so in the
   decision record, and do not switch cap levels on a one-week read (L17/L18 show the level is flat ±3 per row).

How the recent decisions fare under it: MEAN over EMAX (W1 +23, W3 +31, W2 excluded as defective): D = +54 over 2
weeks, σ = 7 → z = +5.5 → ADOPT stands. The class selector: adopted on W3 in-sample (30 vs 20 paid) and withdrawn on
one out-of-sample week (8 vs 31): the withdrawal was right for a different reason — the adopting evidence was
in-sample and therefore not evidence; under rule 1 it would never have been armed. Confidence: the σ table is the
panel's, not live (live weekly d may be larger: two selectors on a 12,800 pool diverged more than on 3,200); the
rule's thresholds are a proposal, not a measurement.

---

## G3. Representativeness: per-season splits, sign disagreement, panel vs live

Per-season primary reads (from the ledger rows, reader outputs and the winners study):

| read | metric | 2022 | 2023 | 2024 | seasons agree in sign? |
|---|---|---|---|---|---|
| L01 MAXGAME4 vs CTRL | ≥194 clears / pool oracle | +1.46 oracle | +1.80 (most of the clears) | +1.60 | yes (clears mostly 2023) |
| L01 ALLBOOM vs CTRL | ≥194 clears / oracle | — | — | oracle −0.46 (fails) | no (2024 alone fails) |
| L02 SLEEVE_L1 | d (share above best) | — | +0.0072 (worse) | −0.0028 (better) | **no** |
| L02 SLEEVE_L2 | d | — | −0.0055 | −0.0031 | yes |
| L03 MEDIAN_BONUS | d | — | −0.0025 | +0.0042 | **no** |
| L04 MODEL_ONLY / ALT_070 | d | — | +0.0106 / +0.0079 | +0.0060 / +0.0049 | yes (robust) |
| L05 LAG sleeve | d | — | +0.0006 | −0.0015 | **no** |
| L06 QBVAR | d | — | +0.0036 | +0.0023 | yes |
| L09 MEAN vs EMAX | tickets89 | — | 442 vs 363 | 564 vs 525 | yes |
| L09 PLF89 vs MEAN | tickets89 | — | 449 vs 442 | 576 vs 564 | yes (tiny) |
| L10 CAP5 vs CAP4 | tickets89 | — | 475 vs 495 | 560 vs 557 | **no** |
| L11 swap vs keep | tickets89 | — | 484 vs 452 | 604 vs 527 | yes |
| L12 T10 vs MEAN | tickets89 | — | 475 vs 456 | 555 vs 556 | **no** (2024 a tie) |
| L13 PMO_X50 vs MEAN | tickets89 / t99 | — | 609 vs 492 / 68 vs 52 | 777 vs 593 / 116 vs 54 | yes |
| L13 PMO vs MEAN | tickets89 | — | 526 vs 492 | 649 vs 593 | yes (but paired 27–40) |
| L14 EMPP99 vs MEAN | tickets99 | — | 54 vs 59 | 79 vs 69 | **no** |
| L15 LINESTAR / BLEND vs LAG | Spearman | — | +0.028 / +0.085 | +0.011 / +0.068 | yes |
| L17 X67 vs X50 | tickets89 | — | 138 vs 142 (≈ tie) | 158 vs 189 | yes, but the effect is 2024 |
| L18 X40 vs X50 | tickets89 | — | 135 vs 143 | 188 vs 188 | **no** (2024 a tie) |
| winners study §3.2 X50 book vs field | sd units | **−0.17** (no market prices in 2022) | +0.08 pooled 2023–24 | | **no** — the level flips sign on the holdout |
| winners study §4.2 spread rows | weeks with ≥1 hit | + | + | + | yes (all three) |
| winners study §4.3 later rows better at deep lines | top-5 % multiple | **reversed** (0.49× vs 1.57×) | ~2× | ~2× | **no** — withdrawn |

Count: of 21 season-split reads, **9 disagree in sign or have one season at a tie** (43 %); of the nine L-series
reads on the current objective, 4 of 9. Two seasons on 36 slates cannot establish a season-stable effect for anything
smaller than the PMO_X50 / L04 / COVF89 size; the winners study's 2022 holdout is the first third-season check of a
current-objective book, and it moved the book's level from above the field to below it, because 2022's replay has no
market prices — which says the *projection input*, not the selector, is what the panel's seasons differ on.

**Does the panel agree with 2026's live reads?** The 16:54 entry (share of rows over the realized p89 line divided by
the field's 11 %): EMAX 0.82×, MEAN 0.95×, PMO_X50 1.22× at K144; 1.16× at K36. Live: the entered EMAX-family books
sat at the field's 49th / 22nd / 50th percentile (W1–W3) — i.e. at or below the field's mean, ≈0.8–0.9× of it; the
mean re-selection of the same pools scored +23 / +31 per row. Direction agrees (EMAX < MEAN, both at or below the
field); magnitude does not: the panel's MEAN−EMAX is +3–4 per row (+13–21 % tickets89), the live gap was +23–31 per
row. Reasons the panel understates 2026, all recorded: dose 3,200 vs 12,800 (the selection regime differs — memory
"match the selection regime"), the live EMAX book chose tail-sleeve rows the panel's EMAX does not, W2 carried the
availability defect. PMO_X50 has no live read. Panel field is the L02 sampler on Millionaire ownership, not the real
field's rows; whether that is easier than the real field is testable on W1–W3 and has not been done (the 16:54
entry says the same). The 2021 FLEX field (Add. 65) was more contrarian; 2026 winners are chalkier than 2026's field;
the panel's 2023–24 seasons sit between. Confidence: high on the sign-disagreement count (it is arithmetic on the
rows); moderate on "input, not selector" as the cause of the 2022 flip (one holdout, one explanation offered by the
study itself).

---

## G4. Noise floor: bootstrap of the paired verdicts and bank-to-bank replication

Method (`bootstrap_fast.py`): the reader's rule verbatim (SUPPORTED iff total ≥ 1.05× control AND ≥ control in every
season AND paired wins > losses; HARMFUL the mirror; else NEUTRAL). Two resamplings, 2,000 draws each, seed 0:
(i) the 72 slate-banks with replacement (as asked); (ii) the 36 slates with replacement keeping both banks of a slate
together (the two banks share a slate's realized field, so the slate is the independent unit). "same" = share of draws
returning the recorded verdict.

| comparison | recorded | totals | paired W–L–T | same verdict (i) / (ii) | SUPP / HARM / NEUT under (ii) | 90 % interval of the relative effect (ii) | P(effect > 0) |
|---|---|---|---|---|---|---|---|
| **L13 PMO_X50 vs MEAN t89** | SUPPORTED | 1386 vs 1085 | 32–31–9 | **0.53 / 0.48** | .48 / .00 / .52 | [+5 %, +54 %] | 0.985 |
| L13 PMO_X50 vs MEAN t99 | SUPPORTED | 184 vs 106 | 24–19–29 | 0.66 / 0.62 | .62 / .01 / .38 | [+4 %, +166 %] | 0.96 |
| L13 PMO_X50 vs EMAX t99 | not a leader (paired 23–23) | 184 vs 106 | 23–23–26 | 0.54 / 0.58 | .41 / .01 / .58 | [0 %, +159 %] | 0.95 |
| L13 PMO vs MEAN t89 | NOT SUPPORTED | 1175 vs 1085 | 27–40–5 | 0.86 / 0.78 | .08 / .14 / .78 | [−18 %, +43 %] | 0.67 |
| L13 (co) MEAN vs EMAX t89 | SUPPORTED-shaped | 1085 vs 934 | 35–33–4 | 0.50 / 0.48 | .48 / .00 / .51 | [−1 %, +35 %] | 0.94 |
| L09 MEAN vs EMAX t89 | NOT CONFIRMED | 1006 vs 888 | 30–32–10 | 0.64 / 0.66 | .33 / .01 / .66 | [−4 %, +33 %] | 0.89 |
| L10 (co) MEAN vs EMAX t89 | replicates | 1052 vs 871 | 37–28–7 | 0.75 / 0.65 | .65 / .00 / .35 | [+2 %, +41 %] | 0.96 |
| L09 COVF89 vs MEAN t89 | HARMFUL-shaped | 806 vs 1006 | 26–41–5 | **0.90 / 0.81** | .00 / .81 / .19 | [−30 %, −5 %] | 0.02 |
| L10 CAP5 vs CAP4 t89 | NOT FLIP-ELIGIBLE | 1035 vs 1052 | 28–33–11 | 0.87 / 0.85 | .01 / .14 / .85 | [−7 %, +4 %] | 0.29 |
| L11 swap vs keep (MEAN) t89 | NOT SUPPORTED | 1088 vs 979 | 30–32–10 | 0.67 / 0.68 | .31 / .01 / .68 | [−3 %, +30 %] | 0.86 |
| L11 (co) swap vs keep (EMAX) | +14 % | 976 vs 856 | 36–27–9 | 0.72 / 0.59 | .59 / .00 / .41 | [−1 %, +31 %] | 0.94 |
| L12 T10 vs MEAN t89 | INCONCLUSIVE | 1030 vs 1012 | 28–27–17 | 0.89 / 0.82 | .16 / .02 / .82 | [−4 %, +7 %] | 0.70 |
| L14 EMPP99 vs MEAN t99 | NOT SUPPORTED | 133 vs 128 | 12–11–49 | 0.82 / 0.82 | .16 / .02 / .82 | [−7 %, +17 %] | 0.71 |
| L14 SIMP99 vs MEAN t99 | NOT SUPPORTED | 120 vs 128 | 11–18–43 | 0.65 / 0.65 | .00 / .34 / .65 | [−17 %, +7 %] | 0.18 |
| **L17 X67 vs X50 t89** | HARMFUL | 296 vs 331 | 17–20–35 | **0.52 / 0.47** | .01 / .47 / .52 | [−20 %, +0 %] | 0.05 |
| L17 X80 vs X50 t89 | HARMFUL | 281 vs 331 | 20–25–27 | 0.48 / 0.43 | .02 / .43 / .55 | [−32 %, +2 %] | 0.07 |
| L17 X100 vs X50 t89 | HARMFUL | 269 vs 331 | 19–28–25 | 0.72 / 0.68 | .01 / .68 / .31 | [−38 %, +1 %] | 0.06 |
| L17 X67 vs X50 t99 | co-report | 40 vs 57 | 3–9–60 | 0.61 / 0.63 | .00 / .63 / .37 | [−47 %, −6 %] | 0.02 |
| **L18 X40 vs X50 t89** | NEUTRAL | 323 vs 331 | 21–25–26 | 0.75 / 0.71 | .06 / .23 / .71 | [−9 %, +6 %] | 0.31 |
| L18 X33 vs X50 t89 | HARMFUL | 311 vs 331 | 24–30–18 | 0.46 / 0.44 | .05 / .44 / .51 | [−15 %, +7 %] | 0.20 |
| L18 X25 vs X50 t89 | HARMFUL | 305 vs 331 | 27–30–15 | 0.45 / 0.42 | .07 / .42 / .51 | [−21 %, +11 %] | 0.21 |

What this says:
- **The verdict labels are fragile; the directions of the big effects are not.** PMO_X50 > MEAN keeps its SUPPORTED
  label in only about half the draws, but the effect is positive in 98.5 % of them: what flips is the frozen rule's
  paired-wins clause (32–31 on 72 slate-banks with 9 ties), not the sign. The same for MEAN > EMAX (label 50 %, sign
  94 %). The rule's paired clause was designed for the tail objective's lumpy outcomes and is now the binding noise.
- **Adopted-lever calls that would flip on fresh banks:** X67 HARMFUL (the reason the cap stays at 50 %) survives
  in 47–52 % of draws and its 90 % interval touches zero; X33/X25 HARMFUL survive in 42–46 %; X40 NEUTRAL in 71–75 %.
  The honest statement is "the cap curve is flat within ±10 % of tickets89 from X33 to X67, and clearly lower at
  X100"; X100 HARMFUL (68–72 %) and COVF89 HARMFUL (81–90 %) are the robust negatives. "X50 is the peak" is a
  point-estimate statement.
- **The per-slate-bank SD of the ticket difference gives the same picture:** X67−X50 SD 2.1 per slate-bank → SE of
  the 72-sum 18 tickets vs the observed −35 (1.9 SE); X40−X50 −8 vs SE 15 (0.5 SE); PMO_X50−MEAN +301 vs SE 113
  (2.7 SE); PMO_X50−MEAN at p99 +78 vs SE 41 (1.9 SE).
- **Bank-to-bank replication of the control.** "X50 331 on both bank pairs" is a coincidence of totals: per bank
  it is 160 / 171 (L17, banks 1230/1231) and 171 / 160 (L18, 1240/1241); per slate the two panels' X50 sums agree on
  8 of 36 slates, correlate 0.90, and differ by 3.1 tickets on average (of ~9.2 per slate); no L17 bank is the same
  draw as any L18 bank (0 of 36 slate means identical under any pairing). The right replication statement: the K36
  control's per-slate ticket count replicates across independent world banks with r ≈ 0.9, and its 72-sum has an SE
  of about ±17 from the banks alone (X50 per slate-bank SD 5.5 → 5.5·√72/√2 ≈ 33 for one bank pair; observed
  difference between pairs 0 — luck).
- **The live example of this noise floor** is the winners study's §4.3: "later rows beat the top rows at deep lines"
  held at ~2× on the 36 slates with an interval that excluded zero, reversed on 17 slates of 2022, and is nil on all
  53. Same slates, same field sampler, one more season: a 36-slate interval is not a 53-slate interval.

Unknowns: the bootstrap resamples the 36 slates the L13/L17/L18 books were all built on, so it measures within-panel
sampling noise only, not the between-season drift G3 shows (which is larger); ties (up to 60 of 72 at p99) make the
paired clause nearly a coin at deep lines.

---

## G5. The never-tested queue, ranked by expected value per hour on the current objective

EV/hour is my judgement: (expected per-row gain on the mean track or expected change in shallow-line tickets) ×
(probability it is real, from the evidence cited) ÷ (hours to a frozen read on the existing PMO/L13 harness or the
live paper path). "Why skipped" is from the record.

| rank | item | proposed where | why it was skipped | EV/hour (judgement) |
|---|---|---|---|---|
| 1 | **Ownership term inside the capped optimizer's objective, blended pre-lock predictor (LAG+LineStar), λ 0.1–0.2** | winners study §4.1 / rec. 1; L15 reopening; L07 (frozen, unrun) | L07 waits on provably pre-lock LineStar captures (H3); L12's tilt was a re-rank, not in-solve | **highest**: +4–6 per row on 36 slates, both seasons, the ceiling replicating on 2022; the harness exists; caveat: LineStar history unproven pre-lock |
| 2 | **Dumb baseline book** (consensus projections, default rules, top-K by projection, no simulator) — B6 | questions B6; unturned-stones §D2 (cash shadow) is its cousin | never anyone's assignment; the program measured levers, never its own floor | very high as a *reference* (one afternoon on W1–W3 pools + 36 slates); tells whether any stage is net positive |
| 3 | **p90 punt valuation vs plain mean for the lev/boom batches (Q4b), with non-players at 0** | W3 §10a Q4b; B3 | Week-4 tempo; needs a generator rerun (hours of solves) | high: 3.7 punts per lev row; 399 boom rows with a sub-1-point player in W3; the p90 instrument is a tail tool inside a mean path |
| 4 | **Status/composition caps: Q_dnp / Q_limited exposure cap, DST cap dose** | PREREG-100 consequence 4 (never written); W2 §14 class-C 5; unturned stones §D1 | "named and never preregistered"; the per-player cap level absorbed the cap budget (L17/L18) | high: PREREG-100's Q_dnp −5.9 / Q_limited −2.9 residual is a measured leak; cheap on the PMO harness |
| 5 | **Deal each contest's rows spread across the sequence** | winners study §4.2 / rec. 2 | descriptive only; needs the layout rehearsal | high for *consistency* at zero solver cost: fewer empty weeks at every line in all three seasons; hits unchanged |
| 6 | **Stack/bring-back mandate on the mean track** (mandate vs ≤40 % two-deep / ≤50 % bring-back / 5+ games) — B5, class-C 8 | W2 §14 item 8; questions B5 | closed on the tail objective (Add. 28/63) and nobody re-opened it | moderate-high: the field's top-1 % shape is 30 %/41 %; needs a generator arm (hours) |
| 7 | **Market weight < 0.45 and the market-agreement pull (0.25/0.75 when served > market by 15 %)** | L04 nomination; W2 §14 class-C 6; Q6 market floor | L04 closed the *tested* directions; the untested direction needs its own PREREG | moderate-high: L04's own co-report and the 2022 holdout say more market = higher level; a re-projection + PMO re-solve, cheap |
| 8 | **Late swap on the book mean (co-report already in L11's files) + the news/field-state form (R11)** | L11; R11; Q7 two-cell swaps | L11 read on tickets89 with the paired clause; R11 planned for a later week | moderate: +1.7 per row realized on swapped books, 86 % P(>0); the mechanism exists; blocked live by H4 |
| 9 | **Ensemble-K paired shadows graded on the mean track** | Add. 119 (deployed shadows); Add. 107/118 | graded only on ≥194 / never on mean | moderate, very cheap (a reader over existing shadow books) |
| 10 | **Outcome-free diagnostics: minimum-edit path to the winner (E.6) and tail-driver credibility audit (E.1)** | unturned stones §E, §H.3 | no owner after the lab closed | moderate: cannot contaminate gates; decides supply vs retrieval; a day each |
| 11 | **Simulator level pinned to the market total / pace (Q10, R6 partial)** | W3 §10a Q10; E2 | simulator work; lab closed; "no heavy Cloud Run" | moderate for the tail sleeve only; ≈0 for the mean track (the mean track does not use the worlds) |
| 12 | **Cash / double-up paper shadow** | unturned stones §D2; winners study rec. 6 | never built; needs a cash-field strength measurement | moderate: the only mix that "wins most weeks" in §5.2, resting on an unmeasured field |

Below the cut, with the reason: **R3 GPD tail, R7 third critic, R8 dependence card, R6 entropy pooling** (all tail-
sleeve instruments; the mean track is indifferent; each is days of work); **R9 cross-season state** (2027); **R12
duplication** (conditional on chalk cores entering the book — it becomes relevant only after rank 1); **R14 LLM facts,
R16 betting splits, R17 inverse-optimisation field, R18 wind, weather/referee features** (each a feature arm the
ledger's "features are guilty until proven" law and the ablation noise floor (±0.005 MAE from column order) make
cheap to run but unlikely to move a row by a point); **orphaned PREREGs 051/061/062/072/075/077** — 051 (winner-shape
supply at fixed compute) is subsumed by rank 6; 062 (feature→outcome sweep) is panel mining under the reopening
condition; 061/072/075 are retrieval/corpus designs for a K80 tail book that no longer exists; 077 (prospective
UNION_EMAX law) is moot after MEAN replaced EMAX. **ETR as an input**: untested and cheap, but B6 (rank 2) subsumes it
— a consensus-projection baseline is the ETR test. Confidence: the ranking's top three are firm (each has a
measured effect size on the current objective or is a missing reference); ranks 4–12 are ordering judgements.

---

## H1. Historical field lineups

What the record establishes:
- **DraftKings exposes one artefact:** the contest's "Export CSV" (`draftkings.com/contest/exportfullstandingscsv/<id>`),
  linked from the operator's private links page (`scripts/dk_standings_links.py`); the operator clicks it by hand; DK
  **purges it about four days after the contest** (production handover 09-21; README known-gaps 2026-08-19). It is the
  only source of `contest_entries` (2026 W1–W3, ~1.1 M rows, `payout` NULL everywhere — H2's problem).
- **For contests the operator did NOT enter:** no record in the repo says whether the export is served. My
  understanding of DK's site is that the full-standings export is served for any *viewable* finished contest for the
  same ~4-day window, entered or not, but that is unverified here; W1's `contest-details-2026-w01.json` did fetch the
  public *contest details* (ladders, fields) for a qualifier that was "in the plan but not entered" — the details API
  works for non-entered contests; the export has not been tried. Cheap to verify: one click on a non-entered finished
  contest before its purge.
- **Third-party archives:** the only one in hand is the **2021 RTS-Little-Data-Bowl clone** (Add. 65): 74 contests,
  63 large, up to 408k entries each, *FLEX-6 format* (not classic DK), used for the per-entry leaderboard stratum
  ("only the winner is contrarian and unique; the top-1 % looks like the median"). The `leaderboard-analysis` module
  reads only the 2026 imports, so the clone's on-disk location is not referenced by code; I could not find it under
  the worktrees (unknown — the operator or the 08-05 session knows). Its construction rules do not transfer (FLEX);
  its behaviour universals (duplication, ownership by stratum) do. More seasons of that dataset: unknown; not in any
  repo note. Other public DFS-standings archives exist in the wild, but I did not search outside the box (rule) and
  none is cited in the record.
- **What can be done now:** (i) keep every weekly export, entered or not, for every large classic contest the
  operator can view (the purge is the only constraint); (ii) verify the non-entered case once; (iii) for persistence
  and duplication studies, three to six 2026 weeks of full fields are worth more than any purchased 2021 FLEX data.
  Confidence: high on what the record says; low on DK's behaviour for non-entered contests.

## H3. LineStar pre-lock capture — status and what "provably pre-lock" needs

- **Script:** `scripts/linestar_ownership_capture.py` (production worktree; 102 lines). It fetches the public
  `GetSalariesV5` endpoint, finds "Week W, SEASON", takes the Main slate's `Ownership.Projected`, refuses (exit 2, named)
  when the period/slate/projection is missing or fewer than 100 players carry a projection, and writes three files
  stamped with the machine's UTC time: `linestar-own-<label>-<UTC>.csv`, the raw payload JSON, and a receipt with
  `captured_at_utc`, period id, slate id, row counts and **sha256 of both the CSV and the raw payload**. Labels
  `saturday` / `t70`. PREREG-O1 amendment 1 (09-29 13:18) adds LINESTAR, BLEND_LS and BLEND_FP arms graded after
  Week 7 by L05's rule; production captures, the laptop grades Mondays. No capture receipt exists in the repo yet.
- **What the script does for provability:** content hash + a self-reported timestamp. That proves the file has not
  changed since the receipt was written; it does not prove *when* the receipt was written, because both come from the
  same machine clock and the same process.
- **What "provably pre-lock" additionally requires** (none of it is in the script; all cheap):
  1. an **external time anchor before lock**: push the receipt (or its hash) to a remote whose timestamp the capturer
     does not control — a git commit pushed to the private remote, or an upload to the private GCS bucket, whose
     object *generation*/creation time is provider-stamped (the repo's own `research/object_identity.py` convention:
     uri/generation/sha256/bytes);
  2. the **lock time recorded in the receipt** (first Main-slate kickoff from the DK draft group or schedules) so
     "pre-lock" is a computed inequality, not an assumption;
  3. the **server's own evidence** kept: the HTTP `Date` / `Last-Modified` headers and any "updated" field LineStar
     carries in the payload (the raw payload is saved, so this is a receipt field away);
  4. **chain of custody at grading**: the Monday reader must recompute the CSV hash and compare it to the anchored
     receipt, and refuse a mismatch (validators must re-derive — the memory rule);
  5. the same anchoring for the **FP** capture (PREREG-O1's original arm) — the reviewer's condition for L07's live
     use applies to both predictors, and L15's historical LineStar `Projected` field remains unprovable (ρ 0.78–0.81
     with realized, "behaves like a projection", which is evidence, not proof).
- Status in one line: the capture is *timestamped and hashed* but *self-attested*; adding the GCS upload with
  generation capture and the lock time to the receipt makes it provable. Confidence: high (read the code).

## H4. A mid-slate standings export on DraftKings

- **What the operating handoff says:** the late-swap chain's hard dependency is "the operator's mid-game
  Millionaire-style Export CSV click"; "whether DraftKings serves the export mid-slate is **unverified**" (§9 risk 1,
  and the chain text); the planned proof was a Thursday-night dry run on a cheap Thu–Mon contest, with a ~20:30
  mid-game click. Production was asked (HANDOFF 09-28) "Is `exportfullstandingscsv` downloadable mid-slate, with
  lineups and current points?" — I found no recorded answer. Without the export the swap tool refuses (exit 3) and
  the entries stand.
- **What would have to be verified on a Sunday**, in order, and recorded with a UTC-stamped, hashed receipt as in H3:
  1. the export URL returns a CSV (not a redirect or an empty file) while games are in progress, for a contest the
     operator is in — and, separately, for one he is not in;
  2. the rows carry the **lineup strings and current points**, not just rank/user/points;
  3. **which players are visible**: DK shows opponents' players only once their game has started; if unstarted
     players are masked, a mid-slate export gives partial lineups — sufficient to *measure late-swap behaviour*
     (diff the ~14:30 export against the final export: any late-game slot that changes was swapped), but not for a
     field model at that hour;
  4. whether the file reflects the swaps already made by others at that minute (edit-entries after lock are
     visible immediately in gamecenter, so the export should carry them — unverified);
  5. cadence limits: whether repeated clicks are throttled, so that two exports (≈14:30 and ≈15:20 CT) are
     possible in one slate.
- If (1)–(3) hold, the late-swap study the questions ask for is: for every user with ≥20 entries, the share of
  late-game slots changed between the mid-slate and final exports, by finish stratum — a one-week, one-export
  answer to "do the winners late-swap". Confidence: the handoff's "unverified" is the state; my item 3 is from
  general knowledge of the site, not the record.

---

## Immediate actions (with evidence and confidence)

1. **Stop deciding cap levels and small tilts on the paired-wins clause.** Report every current-objective read with
   the slate-cluster bootstrap interval of the relative effect and P(effect > 0) next to the frozen verdict (G4: the
   PMO_X50 SUPPORTED label survives 48 % of draws while its sign survives 98.5 %; X67 HARMFUL 47 %). One script,
   already written (`q/G/bootstrap_fast.py`). Confidence high.
2. **Install the symmetric weekly rule (G2)** as the decision record's statistic: same-pool paper control, book mean
   vs field as primary, cumulative z with a panel-derived per-week σ (3/5/7), adopt at +2, withdraw at −2, hold
   otherwise; integrity failures stop at once. Say in each record how many weeks the expected effect needs (a +5 cap
   effect: ~8 weeks). Confidence moderate (σ is the panel's; live σ may be larger).
3. **Re-read six tail-era closures on the mean track (G1):** the stack/bring-back mandate, the p90 punt valuation
   (Q4b), market weight < 0.45 / market-agreement pull, the status-cap follow-up of PREREG-100, the late swap's
   realized-mean co-report (already in L11's files, zero new compute), and the deployed K=1/K=3 shadows. Confidence
   high that the old verdicts do not transfer; moderate on each sign.
4. **Run the dumb-baseline book (B6) before any of the above** — a consensus-projection top-K on W1–W3 pools and
   the 36 slates. It is the missing reference for every stage. Confidence high that it is cheap; unknown result.
5. **Treat the 36-slate panel as two seasons of one projection regime.** 43 % of season-split reads disagree in
   sign; the 2022 holdout flipped the armed book's level (−0.17 sd without market prices) and reversed a 2× pattern
   (winners study §3.2, §4.3). Any Week-5+ adoption from the panel should carry a third season (2022 with market
   prices absent is a *different* regime — say so) or a live paired read. Confidence high.
6. **Make the LineStar and FP captures provable this week (H3):** add the lock time and the server headers to the
   receipt, push the receipt hash to the private remote or bucket before lock, and have the Monday reader re-hash.
   Until then L15's BLEND and the winners study's +4–6 per row rest on an unproven pre-lock assumption. Confidence
   high on the mechanism; small effort.
7. **Verify DK's exports once each, with receipts:** (a) a finished contest the operator did not enter (H1); (b) a
   mid-slate export on a contest he is in (H4, the planned dry run), checking that lineups and current points are in
   the file and which players are masked. Two clicks decide whether the persistence/duplication studies can grow
   beyond three weeks and whether winners' late-swap behaviour is measurable at all. Confidence high on the value;
   the outcome is unknown.
8. **Triage the orphaned preregs in one line each** (G5 tail): 051 → subsumed by the mandate arm; 062 → forbidden
   panel mining; 061/072/075 → K80 tail-book designs, moot; 077 → moot after MEAN replaced EMAX. Confidence
   moderate (from titles and the unturned-stones audit, not from re-reading each document).

Unknowns I could not resolve within the rules: the on-disk location and season coverage of the 2021 RTS clone; DK's
behaviour for non-entered and mid-slate exports; whether the Add. 119 K=1/K=3 shadows have ever been graded; live
per-week σ for the G2 rule (only the panel's is measurable today).
