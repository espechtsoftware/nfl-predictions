# SIS pass-tail 2026 — Amendment 1 (recorded 2026-10-04 CT): split contract, current-policy books, weekly decision record

Amends:
- `reports/2026-09-22-sis-pass-tail-2026-pass-bar.md` (sha256
  `58597b2b11e4cb68eadf9339a1de906c3d5c496bdb1a0336e7f6c04fdb80fab8`);
- the prospective gate `reports/2026-09-21-sis-pass-tail-2026-prospective-gate.md` (sha256
  `fbf2a56b06c0c42ab68498913a2407466bdc720590ebaa2210d2d3281c6034fd`);
- the protocol `reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md` (sha256
  `858ac4b5c0d373f5ab24f94a015114889e0b946eb9c987694b8b9770170909b5`).

All three hashes are taken before their pointer lines were appended. Recorded before any Week-5 outcome exists (first
Week-5 kickoff Thu 2026-10-08; Sunday main locks 2026-10-11). No cache or book of this pair exists for any 2026 week.
The file name carries 10-05 because the checker cites it. Implementation: `production/o3-sis-pass-tail-arm-20261005`
@ `4906f019`. Reviewer cleared it 2026-10-04 on condition this file is committed before the image build.

**Operator decision (2026-10-04, verbatim):** "we absolutely can change things mid-season because if we don't get
things working in the next week or two, there's going to be not another week."

## What happened
The registered build (CODE_SHA `15de40206963b5db9e6a4acff0f865833678d44d`, both images built 2026-08-15) has never run
and could not have:
1. the cache image required a `salary` column `player_week_inference` has never had;
2. the paired image read `source_week_start` from `fantasy_points_alignment_team_l4`, which has none (`72261a27`, never
   deployed);
3. it predates `193e1b44`, so a Sunday run after a Thursday game would read the stale full-week DK draft group.

The frozen acquisition's "existing logical rows byte/provenance-identical" also cannot hold at Week 5: 2026 Weeks 1–4
are first loaded by the weekly team-context pull adopted 2026-09-18, from other files.

Weeks 2–4 of 2026 were never collected (the schedulers were PAUSED; OPEN-DEFECTS O-3), so they are lost.

## What the frozen pass bar decided, and why it ends
Its only decision rule is book-level: criteria 1–4 count clears of the 194 line and compare mean book maxima. The 194
line was calibrated on the August boom-40 generation. The pass bar holds no distribution-level criterion. Once the
books move to the current generation, that rule grades nothing we run. **The frozen gate therefore ends unadjudicated:
no PASS or FAIL will be reported; the Week 8/13 interim reads end with it.** Both parts of the pair are graded instead
by the weekly decision record below (adoption track v2, `reports/2026-09-19-in-season-adoption-track.md`).

## The split
1. **Distribution arms: contract `pass-tail-v1-a1`.** Settings sha256
   `7693d3709e7b60f66d638b07881851e27220a39fdb01f1e789512360798509d8`. The two TabPFN caches exactly as frozen: the
   shared-33 baseline (features.txt sha256 `52cc95c5…`), +3 SIS fields in the treatment, context 28,000, seed 7,
   4 estimators, 13 quantile levels, active-only labels. Changed only by:
   - **Repair 1.** Target-row `salary` comes from `nfl_features.dk_salary_week` on (gsis_id, season, week), the
     training table's own join.
   - **Repair 2.** A live cache runs only if every 2026 REG team-game in weeks 1..W−1 has a SIS row. Otherwise the week
     is an explicit, recorded no-run that counts against the floor; never a partial window.
   - **Auto target.** The single 2026 inference week, and it must equal the schedule's upcoming REG week.
2. **Paired books: contract `pass-tail-v1-a1-companion`.** Settings sha256
   `5133879471760ce0c606b3a8a4562c704f06153440a11be40ddb87718216dd1b`. The adopted money-path generation, derived from
   `ClassicProductionPolicy.engine_environment()`:
   - GEN_TOTAL_BUDGET 172, N_LEV 40, N_CE 0, N_EPISTEMIC 12, N_BOOM 160, N_GUMBEL 0, REPLACEMENT_SLOTS 12;
   - role_draws, CE_SEED 1701, BLEND 0.45, LIVE_SIMS 30,000, possession;
   - SERVED_POSITION_SCALES QB:0.970,RB:1.005,TE:0.940,WR:1.070, K=1, MIN_LINEUP_SALARY 49000;
   - the adopted construction preset, tail_k1 / tail_k1_role, exact-80, tail line 194.

   One single-seed book per registered seed pair R0–R4 (the money path's own five pairs) per arm. **The arms differ
   ONLY in the TabPFN marginal table** (control vs SIS-treatment cache). No Dirichlet usage, ASOE or protocol
   schedules: the money path has none.
3. **The August book generation: `pass-tail-v1-a1-frozen-2026-08`.** Settings sha256
   `0f03a67b81324eb13f13555ac90957fce0cfbc63aebda7f1455e7491378e7555`. Refused for live books from 2026 Week 5;
   selectable only for dry runs and replays.

The three jobs carry ONE CODE_SHA, an integration commit that contains `193e1b44` and `72261a27` (the checker enforces
both).

## Operational rules (all three jobs)
- **One feature snapshot.** All ten books read one live slate-feature snapshot, fingerprinted with the DK draft groups
  it came from; a selectable row from a game that has already started is refused.
- **Marginal reads counted.** Every TabPFN marginal read is counted; an empty read (the silent empirical fallback) is
  recorded and makes the week incomplete.
- **Dry runs.** `SHADOW_DRY_RUN=1` writes only `_dryrun` tables, `<identity>_dryrun` GCS roots, `*_dryrun` run types
  and `dryrun-` panels, and is never graded.
- **Vendor revisions.** First seen wins. A vendor revision of a row already held is never written over it, never fails
  the import, and is logged to `nfl_raw.sis_vendor_revision_log`. It needs a README deficiency row and is flagged in
  the weekly record if it touches a graded week's window.

## Weekly decision record (frozen here, before Week 5; implemented in `src/nfl_dfs/research/sis_pass_tail_weekly_record.py`)

**Complete week:**
- Distribution: both live caches were written before the week's Sunday-main lock and pass the cache-pair identity
  (same keys, sources and contract sha), with a complete source window.
- Books: additionally, the first complete live companion manifest before lock (selected by content sha256) holds all
  ten books, exact-80, with zero marginal fallbacks. Candidate rows come only from that manifest's panels,
  deduplicated by candidate id.

**Distribution metric.** For each Sunday-main QB/WR/TE player-week with an active outcome: QS = 2 × mean over the 13
levels of the pinball loss of the cached quantile against realized DK points (a discrete CRPS).
d = QS(treatment) − QS(control). The week statistic is D_w = mean d; negative means the SIS fields are better. RB and
each position are reported.

**Book metric.** Per seed pair, the realized maximum of each exact-80 book (an inactive player scores 0). The week
statistic is L_w = mean over the five seeds of (treatment max − control max); positive is better. Counts at
187/194/200/210/220/230/240 are reported, never decisive.

**Rule (each part separately, week-clustered).** t = mean / (sd / √n) over complete weeks, Student t with n−1 df.
- **Interim:** one read after Week 11 is scored, needing n ≥ 7, two-sided α = 0.001.
- **Final:** after Week 18, floor 10 complete weeks of 14, α = 0.05.
- **Verdicts:** BETTER or WORSE when |t| reaches the critical value in that direction; at the final read BETTER also
  needs every leave-one-week-out mean to keep its sign. Otherwise NO DIFFERENCE; below the floor, NO VERDICT.
- **Weekly values** are displayed as they land and are descriptive; only these two looks decide.

**What a verdict means.**
- A distribution verdict is the SIS renewal evidence.
- A books verdict is the in-season value at the current policy.
- Neither changes the money path by itself: adoption is a class C/S package under adoption track v2, and the operator
  decides.

**Week-5 no-run rule.** If the Week-4 SIS rows (32 team-games) are not loaded before the Week-5 cache run, Week 5 is
an explicit, recorded no-run that counts against the floor (Repair 2).

## Never pooled
Companion books are never pooled or compared with any August-generation result: the 2026-08-14 historical result, the
frozen generation's dry runs or replays, or any earlier pair. Their identities never share a prefix.

## Unchanged
The distribution arms, seeds and cache law; graded Weeks 5–18; the 10-week floor; the Wednesday acquisition (Weeks 1–4
at target Week 5, then W−1). The frozen August generation stays defined for replays.
