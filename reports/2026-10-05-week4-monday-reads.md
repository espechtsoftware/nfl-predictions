# Week 4 Monday reads (2026-10-05)

Written for the operator and the reviewer. This is the Monday order (HANDOFF "AGENT SCHEDULE"; 10-02 14:34 / 16:58;
the 10-03 dashboard entries), run on 10-05 from 09:13 CT. Every read here is one week and descriptive. The frozen rules
(O1, A3, B2) decide only after Week 5 (interim) and Week 7 (final). There are no dollars or user names here. The raw
printouts are private, in `~/private/week4-monday/`.

## 1. Standings imported (all 26 contests)
- **Coverage:** the 25 plan contests, plus 196305080, an unplanned showdown satellite the operator entered by hand
  (label `extra-showdown-sat`). 174,767 entries in `nfl_raw.contest_entries`, plus ownership.
- **Procedure:** `capture-dk-standings` validated first, then `--apply`, with `--contest-name` = the `contests.json`
  labels.
  - `--expected-entries` came from the final field sizes in the operator's entry-history export. The 09-30 details
    file is pre-lock, so its counts are not final.
  - The operator's zips were extracted in Python with their modification times kept, so `captured_at` is the
    download time.
- **Millionaire:** 161,764 file rows, 161,516 scored. The 248 others are entries with an EMPTY lineup (0 points, tied
  last at rank 161,517): lineups that were never set. It is not a data gap, so it gets no deficiency row (the reviewer
  agreed).
- Ranks, ownership and settlement were all reproduced by the importer's checks.

## 2. Ownership (O1, the frozen reader `score_o1.py`)
FP's T-70 capture vs our lag model, on the 321 players both price who were drafted:

| arm | Spearman | gain over LAG | MAE (raw / rescaled) | top-15 overlap |
|---|---|---|---|---|
| LAG | 0.919 | – | 1.65 | 8 |
| FP | 0.940 | +0.021 | 0.78 / 1.18 | 10 |
| BLEND_FP (mean of LAG and FP) | 0.955 | +0.036 | 1.01 / 1.27 | 11 |

FP is better than lag in Week 4 and the blend is better still. Both gains are below O1's +0.06 interim bar, so nothing
is decided until after Week 5.

## 3. Article mentions (A3)
- 18 articles came before the lock: 5 counted under M and 1 under M_DFS.
- Multiplying ownership by mentions moves almost nothing (gain ≤ +0.001). Adding points for mentions HURTS (−0.025 to
  −0.058).
- This is one week; the frozen rule waits.

## 4. Projections
**B2 (FP in the blend; frozen reader).** MAE against actual DK points on 215 players:
- ours 5.30;
- the equal-weight blend with FP 5.24;
- the 0.45/0.275/0.275 blend 5.26.

The improvement is small: QB and DST improve, RB is flat.

**B1 (descriptive; each source alone).**
- On the players each covers: ours 5.30, our model alone 5.40, FP 5.25, the market 6.00 (171 players).
- On the common 171: ours 5.99, the market 6.00, FP 6.07.
- The three are essentially tied.

**B3 (disagreements: |FP − ours| ≥ 4, or 0 vs ≥ 8).**
- Only 4 players qualified, and FP was closer on 3: Emanuel Wilson (ours 7.6, FP 11.9, actual 27.0), Zay Flowers
  (11.7, 17.0, 28.8) and Kene Nwangwu.
- We were closer on Jalon Daniels.
- The sample is small, but it fits B3's purpose: role changes are where FP helps.

## 5. The unchanged comparison (adoption track v2): did FP ownership beat what it replaced?
The entered T-70 union `20261004T155904961082Z-union-32cdb61` was rebuilt on paper with `union_paper_rebuild.sh`, with
CLONE = the live clone and the output in scratch.
- `same` reproduced the entered `book.csv` BYTE-FOR-BYTE (sha `010df6c0…`), so paper-vs-entered comparisons are
  valid.

Every book was scored PRE-R4 against the real Millionaire field (field mean 118.65; the top 1% 192.94):

| book | rows | mean realized points | book ownership term |
|---|---|---|---|
| entered union (FP ownership, tilt 0.20) | 110 | **115.68** | FP |
| lag rebuild (lag ownership, tilt 0.10) | 110 | 114.97 | LAG |
| no term (the union's own control book) | 105 | 113.76 | none |
| no-term rebuild (field row on lag) | 110 | 113.80 | none |

- In Week 4, FP's term beat the lag term by 0.7 points per lineup and no term by about 1.9.
- Every book finished below the field's average.
- It is one week, so this is not evidence of a lasting edge.

**Row 106, the field-modelled row:**
- the entered FP row scored 96.98 (rank 128,910 of 161,516, about the 80th percentile from the top);
- the lag-built row scored 132.28 (rank 44,911, the top 28%).

It is one lineup, so this is noise. It is reported because the order asked for it.

**The played book (post-R4, 152 entries; from the dashboard dry run):** mean 115.07 points. Two cashes, in supersat15
and supersat16 (148.78 against lines of 140.58 and 137.42), matching the money gate.

## 6. A2 paper books (ownership source → book)
- The LAG, FP (entered) and no-term books are in §5.
- Two arms could not run:
  - TabPFN: there is no Week-4 TabPFN ownership file (the TabPFN rows need LineStar);
  - BLEND_LS: LineStar filled only its free 60-player cap, with no Saturday capture.
- Both are recorded as unavailable, not imputed. A2 is a no-harm guard: FP's book did not fall below lag's in Week 4.

## 7. C1 / C3 (major-contest rows)
- **C1:** the Millionaire field row is graded in §5 (row 106).
- **C3** (the field model's predicted vs realized payout lines, LAG vs FP targets) is NOT done today. It needs the
  lab's field sampler run on the W4 frame with both targets, and it is queued for Tuesday. The realized lines are in
  the dashboard dry run: Millionaire 136.22; the satellites from 137.42 to 184.28.

## 8. Dashboard publisher
- **The dry run passed** (`publish_dashboard_week.py --snapshot`, snapshot `20261005T143149Z`): 297 pool_exposure rows,
  112 arms_weekly rows, 25 contest_lines. The reviewer checked it and approved `--apply`.
- **The `--apply` failed before writing anything:** the `nfl_dashboard` dataset does not exist yet. `sql/dashboard/ddl.sql`
  says the operator applies it once. The command is in HANDOFF; after it runs, `--apply` is re-run from the same
  snapshot.
- **The reviewer's follow-up:** arms without a contest id are measured against the MILLIONAIRE's cash line. So "book
  0.19" means "rows at or above the Millionaire line", not a cash rate. The dashboard label should say so before next
  week.

## 9. Also today (from the operator's requests)
- **Study 1b** (the entry-level player cap) read, reproduced by the reviewer: no adoption (Addendum 123).
- **Study 15** (QB + 1 pass catcher + bring-back) is frozen; the census is running.
- **Study 16** (the operator's thesis portfolio) is frozen; it is built and in test.
- **The B4 panel does NOT run tonight.** It is not preregistered.
  - The 10-03 audit (`reports/2026-10-03-b4-audit-d1-overlap-map.md`) found that Route Share is the only FP Data
    Suite feature with a model column. Its panel is effectively the Route Share shadow, which is already deployed.
  - XFP, Bell Cow, weighted opportunity and PROE have no column yet. FP's XFP history starts at week 5–6.
  - O-21, the `xfp_l4` train/serve skew, must be seen by the reviewer before any B4 preregistration.
  - So B4 waits for that preregistration. Tonight's local compute goes to studies 15 and 16 (one heavy job at a time).
