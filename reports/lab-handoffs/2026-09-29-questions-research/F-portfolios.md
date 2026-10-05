# Theme F — Portfolios, volume and persistence (PRELIMINARY, 2026-09-29)

**Status: PRELIMINARY.** A fast read for the operator so numbers exist today. The laptop's full Q11 study (portfolio anatomy + emulation) is due Wednesday and supersedes this. F4 is another analyst's. Read the new
`reports/2026-09-29-winners-study-and-consistency.md` (branch `origin/review/winners-study-20260929`) first: it owns
the rates (top placers lose 83–85% of other weeks; skill sd ≈ ±5 points/lineup; best-fifth traits; per-contest
break-even). This note adds only what that study does not give: **named** repeaters, the **core-count / which-slots-vary**
anatomy of the heavy top-100 users against a matched mid-field sample, and the **per-winner decomposition** against our
pool and book. Where my numbers overlap the study's I say whether they agree.

**Information time of every input: realized / post-lock.** `nfl_raw.contest_entries` and `nfl_raw.contest_ownership`
(2026 W1–3, captured after settlement), `nfl_raw.dk_salaries` (team/position/salary by main-slate draft group
151307 / 153428 / 153769), `nfl_raw.schedules` (game ids). Our pools are the pre-lock candidate files
(W1: union of the twelve `e7255e9` builds of 09-12/09-13, 7,233 distinct candidates; W2: the 12,559-candidate build of
09-16; W3: `cands_scored.pkl`, 12,559) — pre-lock artifacts, but joined to realized outcomes here. Our entered
Millionaire rows were identified in `contest_entries` from the W3 seat (rank 79,343, players from `our_book.pkl`; the screen name is redacted in `F/ours.csv`):
**57 entries in W1, one seat in W2, one seat in W3.** Contests: W1 `193028206` (831,028 parsed entries), W2 `195648007`
(172,692), W3 `195905122` ("milly20", 161,682). Cash = rank within the top 20% of the field (the recorded W2 line 138
and W3 line 149.5 both sit at exactly the 20.0% / 19.8% rank; W1 assumed the same). Scripts and CSVs: `q/F/`
(`q1_userweek.sql`, `q3_shape.sql`, `q4_portfolios.sql`, `q_winners.sql`, `q_ours.sql`, `f1_persistence.py`,
`f2_anatomy.py`, `f5_winners.py`, outputs `f1_out.txt`, `f2_out.txt`, `f5_out.txt`). Single-threaded, no simulation,
no optimizer, read-only.

---

## F1. Do top finishers persist?

### F1.1 Persistence across all three pairs (users with ≥20 Millionaire entries in both weeks)

| pair | users | Spearman of mean finish percentile | of mean points | of best-entry percentile | P(top-20% in B \| top-20% in A) vs base 20.1% |
|---|---:|---:|---:|---:|---|
| W1→W2 | 721 | **+0.116** (p 0.002) | +0.124 | +0.144 | 22.8% (33/145), lift **1.13×** |
| W2→W3 | 607 | **+0.269** (p 2e-11) | +0.271 | +0.310 | 32.8% (40/122), lift **1.63×** |
| W1→W3 | 702 | **+0.237** (p 2e-10) | +0.248 | +0.279 | 24.8% (35/141), lift **1.24×** |

- W1→W2 reproduces the 09-22 review §2.5 exactly (+0.116, 721 users) and the study §2 range (+0.12 to +0.27) is what I
  get too: **agreement.** The two $20 weeks (W2, W3: same fee, same ~55–60k user population) correlate much more than
  either does with the $5 831k-entry W1. Part of that is population (W1 had 173k users, many casual), part may be that
  W2 and W3 rewarded the same process (a chalk core: JSN/Lamb/Schultz, then Gibbs/G. Wilson/Geno/Sadiq).
- Two-by-two: being in the top fifth of heavy users in one week raises the chance of being in the top fifth the next by
  13–63%. That is a real but small edge — a 1.6× lift on a 20% base still leaves two-thirds of last week's best fifth
  outside this week's.

### F1.2 The top 10 of each week, by name (user, entries, best rank; then the other weeks)

W1 top 10 (10 users): User22 #1 (3 entries) → W2 rank 148,405 / 85.9th pct (1 entry), W3 rank 31,133 / 19.3rd pct
(1 entry). User21 #2 (8) → W2 #8,311 (3 entries), no W3. **User23 #3 (120 entries) → W2 #580 (100 entries),
W3 #3,243 (8 entries)** — the only W1 top-10 user in the top 1% of both later weeks. User13 #4 (12) → 60th / 67th
pct. User35 #5 (50) → #4,385 (5), #9,221 (6). User29 #5 (30) → #6,611 (6), #25,585 (9). User32 #7 (150) and
User19 #8 (150): did not play W2 or W3 Millionaires. User31 #9 (20) → 36th / 42nd pct. User08 #10 (15)
→ 72nd / 73rd pct.

W2 top 10 (10 users, **eight with 150 entries**): User15 #1 (150) → W1 #13,479 (150), W3 #1,691 (150), mean pct
47.8 / 49.0 / 43.0 — his three portfolio means were 143.6 / 116.8 / 134.0 against field means 142.1 / 115.5 / 128.5:
**the $1M winner's portfolio was at or barely above the field average every week.** User17 #2 → W1 #2,058,
W3 #443. User06 #3 → #5,009 / #882. User33 #4 → #5,044 / #1,298. User10 #5 → no W1, W3 #4,074. User20
#6 → #1,816 / #845. User07 #6 (13 entries) → W1 64th pct (69 entries), W3 67th pct (20). User12 #8 →
#2,468 / #2,679. User30 #9 (3 entries) → 50th / 50th pct. User27 #10 → W1 #5,927, W3 #5,378 (mean pct 17.9 in
W2, 59.2 in W3). **All eight 150-entry W2 top-10 users were in the top 1% of W3 and seven in the top 1% of W1** — with
150 entries at a ~1% per-entry rate the chance of at least one top-1% row is ~78% by volume alone, so this is
mostly volume; their *mean* percentile (37–50) is where the skill shows, and it is modest.

W3 top 10 (10 rows, 9 users): User01 #1 (10 entries) → W1 68th pct (1 entry), W2 #1,663 (8 entries).
User14 #2 and #8 (4 entries, mean 214.7) → W1 61st pct (10 entries), W2 39th pct (2). User18 #3 (150) → **W2 #12,
W1 #4,137**; mean pct 39 / 40 / 30. User03 #4 (150) → W1 #5,901 (150), W2 62nd pct (1 entry). User34 #5 (150) →
W1 #18,862, no W2. User26 #5 (150; identical lineup to User34) → no W1/W2. User05 #7 (1 entry) → W1 #17,040
(126 entries), W2 49th pct (1). User24 #9 (150) → **W2 #27**, no W1. User36 #10 (5) → W1 #16,127 (11), W2 63rd pct.

### F1.3 The top 100, by name where it matters

- **Users in the top 100 of two different weeks (9):** User02 (W2 #24, W3 #11; 150/150; W1 #13,564),
  User18 (W2 #12, W3 #3), User24 (W2 #27, W3 #9), User25 (W2 #25, W3 #14; W1 #4,690), User28 (W2 #29,
  W3 #73; W1 #18,363), User11 (W1 #20, W3 #33; W2 #209; 150/81/84 entries), User09 (W1 #73, W3 #74 with 150 then
  4 entries; W2 #20,079 with 6), User04 (W1 #87, W2 #89 with 25/10 entries; W3 #10,251 with 5), User16 (W2 #50,
  W3 #99; 7/30). Expected under independence: 0.12 (W1&W2), 0.17 (W2&W3), 0.12 (W1&W3); observed 1 / **6** / 2.
  The W2↔W3 pair is 35× chance and is entirely 150-entry users except User16.
- Top-100 users' other weeks (all users, not only heavy): W2 top-100 → W3: top-1% again **41%** (base 2.0%), top-1,000
  again 32% (base 1.3%), top-100 again 7% (base 0.16%), mean percentile below 50 in 71% (base 44%); median entry count
  41. W3 top-100 → W2: 27% / 23% / 8% / 71%. W1 top-100 → W2: 18% / 15% / 2% / 46% (median 6 entries). The study's
  "83% lose money in other weeks" is the dollar view of the same people; both are true because the per-entry rate of a
  top-1% row is ~1–2% even for the best.
- **Per-entry rates by entry count** (top-100 rows per 1,000 entries; top-1% rate per entry): 150-entry users 0.12 /
  1.38 / 0.95 and 1.3% / 1.9% / 1.4% (W1/W2/W3); single-entry users 0.09 / 0.30 / 0.33 and 0.7% / 0.6% / 0.6%.
  Per entry the heavy users reach the top 1% at 2–3× the single-entry rate (agrees with HANDOFF L10477 "+9.26 points
  1-entry → 51–150"; my portfolio-mean gap is 138.3→145.1 in W1, 111.7→122.5 in W2, 125.1→133.9 in W3).

### F1.4 Is the edge players or shapes?

"Persistent" = top-20% of heavy users in **both** weeks of a pair, described in the later week; "others" = the rest
(shape via `dk_salaries` teams + `schedules`; ownership via `contest_ownership`, summed over slots).

| described in | n | own. sum | sub-5% players | ≥20% pieces | max own | stack (QB+WR/TE) | 2-deep rate | bring-back | games | max/game | $7k+ | QB salary | distinct QBs | mean pts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| W2 (from W1), persistent | 33 | **137.3** | 1.78 | 2.22 | 39.9 | 1.45 | 0.48 | 0.51 | 5.83 | 3.31 | 2.14 | 5,989 | 8.5 | 136.2 |
| W2, others | 688 | 117.9 | 2.45 | 1.60 | 36.5 | 1.30 | 0.37 | 0.53 | 5.82 | 3.18 | 1.94 | 5,933 | 12.2 | 117.9 |
| W3 (from W2), persistent | 40 | **130.9** | 1.78 | 2.23 | 33.7 | 1.50 | 0.53 | 0.47 | 5.64 | 3.32 | 2.17 | 5,771 | 10.8 | 146.3 |
| W3, others | 567 | 113.9 | 2.24 | 1.55 | 31.4 | 1.36 | 0.42 | 0.51 | 5.75 | 3.22 | 2.06 | 5,913 | 12.9 | 131.4 |
| W3 (from W1), persistent | 35 | **139.5** | 1.40 | 2.44 | 35.2 | 1.47 | 0.48 | 0.48 | 5.70 | 3.28 | 2.26 | 5,600 | 9.1 | 148.6 |
| W3, others | 667 | 115.3 | 2.22 | 1.59 | 31.8 | 1.34 | 0.40 | 0.49 | 5.78 | 3.19 | 2.07 | 5,924 | 12.2 | 131.3 |

- **Players, mainly: +15 to +24 ownership points per row, 0.5–0.8 fewer sub-5% players, +0.6–0.9 chalk pieces.**
  Agrees with the 09-22 review §2.5 and the study §2 (ownership 62nd vs 44th percentile).
- **A small shape tilt exists that the 09-22 review's "identical stacking" understated:** 2-deep stacks 48–53% vs
  37–42% (+0.1–0.15 per row), 3–4 fewer distinct QBs, ~$150–300 cheaper QB in two of three pairs. Bring-back, games
  per row, max-per-game are identical. The study's trait table (QB-stack 1.24→1.35, +0.14 correlation) agrees with
  this refinement. The disagreement with the 09-22 review is one of definition (top-20%-both vs top-20%-one-week).
- Note the persistent users' **mean is +15–18 above others in the described week** — that is selection on the same
  outcome (they are defined partly by that week), so it is not an estimate of skill; the +6–7 in the study's
  other-week design is.

## F2. Portfolio anatomy — every user with ≥20 entries who finished top-100, vs a matched mid-field sample

149 top-100 user-weeks (W1 46, W2 58, W3 45; median 150 entries) matched one-to-one on week and entry count to 149
user-weeks with mean percentile 35–65 and best rank >1,000 (`q4_portfolios.sql`, `f2_anatomy.py`, 98,680 rows).
"Cores" = greedy clusters where a row joins the first cluster whose seed shares ≥6 of 9 players.

| pooled (mean) | top-100 | matched mid |
|---|---:|---:|
| entries | 99.3 | 99.2 |
| portfolio mean points | **140.0** | 127.4 |
| cash share (top 20%) | **35.3%** | 18.1% |
| top-1% share of rows | 4.9% | 0.6% |
| exposure of the most-used player (share of rows) | 0.561 | 0.580 |
| mean exposure of the top-3 / top-5 players | 0.481 / 0.427 | 0.490 / 0.435 |
| distinct players | 94.8 | 91.1 |
| players on ≥50% / ≥25% of rows | 1.35 / 8.0 | 1.48 / 7.9 |
| distinct QBs | 14.8 | 13.4 |
| "cores" (≥6-shared clusters) per 100 rows | 81 | 73 |
| largest core's share of rows | 5.9% | 7.0% |
| mean pairwise overlap (players of 9) | 1.90 | 2.01 |
| share of row pairs sharing ≥6 | 1.7% | 3.0% |
| rows unique in the field | 93.4% | 94.2% |
| slot variation: distinct QB / RB / WR / TE / FLEX / DST | 14.8 / 16.0 / 34.4 / 12.8 / 25.1 / 14.4 | 13.4 / 16.5 / 32.8 / 12.8 / 26.2 / 13.0 |
| modal share: QB / top-2 RB / top-3 WR / TE / FLEX / DST | 0.23 / 0.41 / 0.31 / 0.32 / 0.20 / 0.28 | 0.24 / 0.40 / 0.32 / 0.31 / 0.20 / 0.32 |

Per entry-count bucket the picture is the same: 20–49 entries 141.4 vs 127.6 (exposure top-1 0.57 vs 0.58, 22 cores
per 27 rows in both); 150 entries 137.4 vs 126.2 (0.53 vs 0.55; 123 vs 111 cores per 150 rows; overlap 1.76 vs 1.88).

**Readings (preliminary):**
1. **Shape does not separate the top-100 heavy users from the mid-field heavy users.** Every construction statistic —
   exposure concentration, distinct players, QB count, cores, overlap, uniqueness, which slots vary — is within noise
   of the matched sample. The 12.6-point mean gap and the doubled cash share come with the same shape. This is the
   same verdict as F1.4 and the study: **which players, not which shapes.** It also answers Q11's "process or draw":
   the process is visible only in player choice.
2. **"Cores" do not exist in 150-entry portfolios.** The post-mortem's "60–73% of rows on three or four players" is
   correct as *exposure*, but the rows are near-orthogonal: mean pairwise overlap 1.7–2.0 of 9, under 2% of pairs
   share 6+, and a ≥6-shared clustering yields ~120 clusters per 150 rows. That is the signature of an optimizer with
   exposure targets and a minimum-uniqueness constraint, i.e. exactly what our own builds look like (our W1 57
   Millionaire rows: top-1 exposure 0.77 [Jaguars DST], top-3 0.45, overlap 1.51; our W3 144-row book: 0.35 / 0.34 /
   1.16). **Core+variation is a small-book pattern:** User14's 4 rows (mean 214.7) and User01's 10 (Gibbs 9/10,
   Wilson 8/10) — see W3 post-mortem §1; not in this ≥20-entry sample.
3. **The exceptions are informative.** User27 W2 (#10, 150 entries) is the one true core builder in the named
   set: 29 clusters, top-1 exposure 0.87, top-3 0.78, overlap 3.7, mean 147.3, **67% cash**; in W3 the same user built
   131 clusters (overlap 1.7) and posted mean 120.3, 7% cash. User18 (top 1% all three weeks, W2 #12, W3 #3) runs
   exposure 0.82 / 0.73 on the top player with 24–25 QBs. User03 (W3 #4): top-1 0.71, 11 QBs, mean 151.6, 47% cash.
   User15 (W2 $1M winner): 164 distinct players, top-1 0.33, 149 clusters — the most diversified in the set — mean
   116.8 vs field 115.5, cash 17%: **the $1M came from one row of a field-average book.**
4. Within the pulled (selected) sample, the only construction statistic consistently correlated with the portfolio
   mean is **uniqueness, negatively** (Spearman −0.31 / −0.16 / −0.22 by week): users whose rows are duplicated in the
   field score higher, because duplicated rows are chalk rows. Concentration (top-1 exposure) helped in W1 only
   (+0.26), was nil in W2/W3. Cores and QB count: nil.

## F3. What an emulation would need (preliminary; do not build here)

Targets, from the top-100 heavy users and the persistent users above (all measured post-lock; the emulation must use
only pre-lock inputs to hit them):
- **Exposure profile (150 rows):** top player 0.50–0.60 of rows, top-3 mean 0.45–0.50, top-5 ~0.42, ~8 players at
  ≥25%, 1–1.5 at ≥50%, 90–115 distinct players; 14–17 distinct QBs for the median top-100 user but **9–11 for the
  highest-mean portfolios** (User03 11, User27 9, User20 9).
- **Chalk level:** ownership sum 130–140 (field 105–117; our W3 book 86), ≤1.8 sub-5% players, 2.2–2.4 pieces at
  ≥20%; QB stack ~1.5 (2-deep in ~half the rows), bring-back ~50% (we force 100%), 5.6–5.8 games per row (we 3.7–4).
- **Core count is not a target for a 150-row book:** target mean pairwise overlap 1.8–2.4 and ≥6-shared pairs ≤3%. For
  a 4–10-row book the target is the opposite: one core of 5–6 shared players, 2–3 varying slots (WR3 / FLEX / DST).
- **Slot variation:** modal QB ≤25% of rows, top-2 RBs ~40% of RB slots, top-3 WRs ~30% of WR slots, modal TE ~32%
  with a second TE at FLEX (study: 32% vs 23%), modal DST ~30%.
- **Scoring test:** portfolio mean vs the field's mean (+12.6 is the top-100 heavy-user gap; +6–7 the study's best
  fifth), cash share ~35%, top-1% share 4–5%. **Caution:** the W3 post-mortem already shows top-mean selection from OUR
  pool gives 151.2 mean / 50% cash (W3) and 169.7 / 55% (W1) — i.e. already in or above the top-100 heavy-user class
  on mean without any shape emulation. So the emulation should be run as **same pool, exposure-target selection vs
  top-mean selection**, both against the field; if they land in the same class, shape is not the explanation (F2
  says it will not be) and the remaining gap is which players.

## F5. Which players decided each winning lineup, and were they ours?

| week / rank | user (entries) | total | best player | top-3 (share) | ≥25 / ≥30 / ≥40 | own. sum | in our universe | in our pool (mean share per player, min) | in our entered Millionaire rows |
|---|---|---:|---|---:|---|---:|---:|---|---|
| W1 #1 | User22 (3) | 274.0 | D. Henry 38.3 | 112.7 (41%) | 5 / **5** / 0 | 101 | 9/9 | **9/9** (9.2%, Steelers 0.26%) | 7/9 of 57 rows: Gibbs 14, Swift 7, Moore 6, Henry 5, Goedert 4, Watson 3, Love 3; **Coker 0, Steelers 0** |
| W2 #1 | User15 (150) | 232.4 | JSN 45.5 | 112.8 (49%) | 5 / 2 / 1 | 97 | 9/9 | **9/9** (6.8%, Kittle 1.4%) | 1/9 (Schultz) in our one seat |
| W3 #1 | User01 (10) | 239.8 | Gibbs 41.4 | 109.8 (46%) | 5 / 3 / 1 | 122 | 9/9 | **9/9** (9.2%, Vikings 2.4%) | seat: Gibbs; 144-row book: 8/9 (Vikings 0) |
| W3 #2 | User14 (4) | 233.1 | JSN 38.4 | 98.1 (42%) | 5 / 2 / 0 | 91 | 9/9 | 9/9 (5.5%, Raiders 0.28%) | seat: none; book 8/9 (Raiders 0) |
| W3 #3 | User18 (150) | 225.9 | Gibbs 41.4 | 109.8 (49%) | 5 / 3 / 1 | 149 | 9/9 | 9/9 (9.6%) | seat: Gibbs; book 9/9 |
| W3 #4 | User03 (150) | 225.4 | Gibbs 41.4 | 101.1 (45%) | 4 / 2 / 1 | 112 | 9/9 | 9/9 (9.9%) | seat: Gibbs, St. Brown; book 8/9 |
| W3 #5 | User34 / User26 (150, same lineup) | 223.6 | Gibbs 41.4 | 109.8 (49%) | 6 / 3 / 1 | 173 | 9/9 | 9/9 (11.0%) | seat: Gibbs, Walker; book 9/9 |
| W3 #7 | User05 (1) | 222.6 | Gibbs 41.4 | 109.8 (49%) | 6 / 3 / 1 | 167 | 9/9 | 9/9 (10.7%, Ayomanor 0.6%) | seat: Gibbs, Walker; book 8/9 |
| W3 #8 | User14 (4) | 221.4 | Gibbs 41.4 | 101.1 (46%) | 5 / 2 / 1 | 95 | 9/9 | 9/9 (8.9%) | seat: Gibbs; book 8/9 |
| W3 #9 | User24 (150) | 220.8 | Gibbs 41.4 | 101.1 (46%) | 6 / 2 / 1 | 129 | 9/9 | 9/9 (9.5%, Colts 0.06%) | seat: Gibbs, Walker; book 8/9 (Colts 0) |
| W3 #10 | User36 (5) | 219.9 | Gibbs 41.4 | 109.8 (50%) | 6 / 3 / 1 | 159 | 9/9 | 9/9 (9.8%) | seat: Gibbs; book 9/9 |

Our W3 144-row book's exposure to the deciding players (rows of 144): Gibbs 45 (31%), Walker 47 (33%, he scored 21.3
at 44% owned), G. Wilson 19 (13%), JSN 9 (6%), Kittle 8 (6%), **Geno Smith 7 (5%)**, **Sadiq 4 (3%, all from Sunday's
scratch swap)**, Warren 3 (2%), J. Love 2; Titans DST 51 (35%, scored 7), Bengals 47 (scored 3), St. Brown 31 (11.9).

**Readings:**
- **Not one 40-point boom.** The 2026 winners are 5–6 players at 25+, 2–3 at 30+ (W1's 274 had five at 30+), and the
  top three players carry 41–50% of the total. Addendum 38's historical bar (3.4 at 30+, ~1.0 at 40+) is met by W1 and
  roughly by W3 (mean 2.6 at 30+, 0.9 at 40+ across the top 10); W2 needed only two 30s because the field was low
  (mean 115.5). The W3 top 10 is one lineup: Gibbs (9/10), Geno (10/10), G. Wilson (10/10), Sadiq (10/10), JSN (7/10)
  plus one or two variations — 105–110 points from a five-player chalk-plus-Sadiq core, then 25-point pieces.
- **Identification is complete at the player level: every player of every winning lineup was in our pool all three
  weeks** (81 of 81 player-slots), extending Addendum 38's 67% (best-of-40 era) to 100% at pool scale. The pool's
  exposure to them averaged 5.5–11% per player, with the DSTs and one-off pieces at 0.06–1.4% (Colts, Steelers,
  Raiders, Kittle W2, Ayomanor).
- **The book, not the pool, was the miss, and it was two players each week.** W1: Coker (36.8, 7.5% owned) and the
  Steelers (18.0) were in the pool at 3.6% / 0.26% and in zero of our 57 rows; everything else was held at 5–25%. W3:
  Geno Smith (30.0, 7.5% owned, 66 of the top-100 QBs) at 5% and Sadiq (26.5, Sunday news) at 3%, against 35% on the
  Titans DST (7.0) and 33% on the Bengals (3.0) — the DST allocation cost more than any skill slot.
- The seat-level record (one seat in W2 and W3) cannot be decomposed meaningfully; it is a single draw of a book that
  was below the field's mean (study §3.1).

## Agreement / disagreement with the 09-29 study

- Agree: persistence magnitude (+0.12 to +0.27); edge is player choice, not construction; heavy users' per-entry
  edge is 2–3× at the top 1%; the $1M winners' portfolios were field-average (User15's three means 143.6 / 116.8 /
  134.0 vs field 142.1 / 115.5 / 128.5).
- Refinement, not disagreement: the 09-22 review's "identical stacking" holds for bring-back and game concentration but
  the persistent users run 2-deep stacks ~10–15 points more often and 3–4 fewer QBs; the study's own trait table shows
  the same direction.
- New: **no cores in heavy portfolios** (overlap 1.7–2.0; ≥6-shared pairs <2%); core+variation is a 4–10-row pattern.
  The Q11 emulation's "core count" target should therefore be a pairwise-overlap target, not a cluster count.
- New: **100% of winning players were in our pool every week**; the book's exposure allocation, not generation, missed
  them (W1 Coker/Steelers at 0; W3 Geno 5% / Sadiq 3% vs Titans 35% / Bengals 33%).

## Confidence and unknowns

- Three weeks, one contest per week; W2 and W3 share a ~$20 population and W1 is a different ($5, 831k) field — the
  W2→W3 correlation may be population, not skill stability. Moderate confidence in the direction of every finding;
  low in any magnitude.
- The persistent-vs-others table (F1.4) selects on the described week's outcome; only the direction of the shape
  differences is usable. The study's other-week design is the correct estimator of skill size.
- The matched mid-field sample was drawn by hash from users with mean percentile 35–65 and best rank >1,000; the
  best-rank exclusion slightly favours less concentrated portfolios in the mid group (a concentrated portfolio is more
  likely to carry one top-1,000 row), which would bias F2 *toward* finding a concentration difference; none was found.
- "Cores" via a greedy seed rule with a ≥6 threshold is approximate; at threshold 5 the counts fall but the
  top-100-vs-mid parity is unchanged in the pairwise-overlap statistic, which is threshold-free.
- W1 pool = union of twelve pre-lock builds (7,233 candidates), the entered build alone was 800; W2 pool is the
  Wednesday 12,559 build, not the Saturday D12800 that produced the entered book (the composite dirs hold only the 97-row
  books). Pool-membership claims are therefore "in a pre-lock pool we built", not "in the entered build's pool" (for W1
  the entered build also held all 9).
- Ownership is the Millionaire's realized ownership; stack/bring-back use `dk_salaries` teams (0 unmatched names of
  10.5M player-slots) and `schedules` game ids.

## Immediate actions (this week, no new model)

1. **Move exposure from DST/chalk-RB to the pieces the winners share** — the book's miss was allocation, not
   generation (F5: 100% pool coverage; W1 Coker/Steelers at 0 of 57; W3 Geno 5%, Sadiq 3% vs Titans 35%). Concretely:
   cap any DST at ≤25% (already armed for Week 4 per the study §3.2) and require the top-mean rows' QBs to reach ≥10%
   each when the projection ranks them top-3 at the price. Confidence: moderate (two weeks of evidence, direction
   consistent with the study's §4.1 ownership term).
2. **Stop treating "cores" as a lever for the main book.** The heavy winners build near-orthogonal rows with exposure
   targets — our shape already. Spend the Q11 emulation effort on player choice (chalk level, projection rank) and on
   the exposure-target vs top-mean comparison in F3, not on cluster construction. Confidence: high for the descriptive
   fact (149 matched pairs, three weeks), moderate for the implication.
3. **Enter the chalk-core profile the persistent users show:** ownership sum ≥125 (we ran 86–99), ≤2 sub-5% players
   (we ran 3+ in 79–88% of rows), a second TE at FLEX in ~30% of rows. This is the study's recommendation 1 in
   selection-only form and needs no solver change: filter the existing pool by projected-ownership sum before
   top-mean selection. Confidence: moderate; it is the one trait that repeats in the 09-22 review, this note and
   the study.
4. **For any 4–10-entry contest, build core+variation on purpose** (5–6 shared players, vary WR3/FLEX/DST) — that is
   what the small-entry W3 winners did (User14 4/4 rows ≥ 214). Confidence: low-moderate (two users, one week); cheap
   to do and reversible.
5. **Do not chase the named repeaters' lineups.** Their edge per entry is 2–3× at the top 1% and their mean is +6–12
   over the field; the study finds no information in their player weights beyond ownership (+0.05 partial). Track the
   nine repeaters' W4 results as a free out-of-sample check of persistence, nothing more. Confidence: high.
