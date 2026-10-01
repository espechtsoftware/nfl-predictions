# Thursday review: the day's defects, and what could still fall through the cracks before Sunday

Reviewer, 2026-10-01 14:1x CDT. Branch `review/ownership-term-20260929`. Asked by the operator after the lazy-cuts
acceptance was found to have been missed and the smoke found two Sunday defects: "make sure nothing else falls
through the cracks." Read: integration `b586edee` and every HANDOFF entry since the L26 freeze.

## 1. The defects the smoke found today, and one I missed

| Defect | Found | My reading |
|---|---|---|
| `UNION_SATURDAY_RUN=auto` never resolved: an if/else mis-nesting replaced the picked Saturday dir with `Path('auto')`, so every armed union would have failed on Sunday — no capped main, no routing, no sleeve cap, no ownership term | the smoke, 13:58 | **Critical, and I share the miss.** I read that exact block on 09-29 while writing the ownership-term patch and did not see it. The rehearsals all named the Saturday dir explicitly, so `auto` had never run. The fix (`resolve_saturday_run`) is right and tested. |
| The build's contests pre-check compared the layout's rows (main + sleeve) with the main rows only, refusing every two-track plan at second 0 | the smoke, 09:58 | Correct fix; the defect-class sweep over the other book-size consumers is the right response. |
| The exposure-cap sheet and the refinement-2 paper book counted the main rows only | the smoke, 13:58 | Same class, fixed. Report-only tools, but the operator reads that sheet before upload. |
| The lazy-cuts acceptance owed Monday 09-28 was never done | the laptop's own audit, 13:50 | Now running on the workstation at full size, exact-match against the Week-3 archive. The right test. |

**The pattern:** every one of these lives on a path that no rehearsal had exercised with the Week-4 settings (two
tracks, `auto`, the sleeve). The smoke is doing its job; the question is what else only Sunday will exercise.

## 2. Paths that Sunday will exercise and no rehearsal has

| # | Path | Why it is untested | What would close it |
|---|---|---|---|
| 1 | **The ownership term on Week-4 data** (TabPFN, then the blend) | LineStar held 60 Week-4 players this morning; 100 are needed. Today's smoke could only run the no-capture path. | The term's smoke the moment LineStar fills (the laptop's 12:13 / Fri 12:17 / Sat 08:23 checks). If it has not filled by Saturday 08:23, **decide then** whether to run with no term, rather than find out at 10:50. |
| 2 | **The Saturday D12800 supply's duration on the laptop** | Never built on this machine. The take-over doc says about 6 h; Week 2's workstation rehearsal measured 16 h 17 min; Week 3's archive shows 12 h. Started 10:30 Saturday, the finish is somewhere between 16:30 and 03:00. | The lazy-cuts acceptance (if it passes, a timed run Friday). If it does not pass, start the supply as early as the Saturday refresh allows and keep the operator's start-time setting. |
| 3 | **No automatic fallback supply.** The union takes one dose (`UNION_SAT_DOSE=2560/10240`). If the D12800 is not finished by the 09:10 build, the 10:35 D6400 exists but is never picked; the union refuses and the T-70 book stands alone — the same outcome as this morning's `auto` defect. | The code never had a second dose. | Let `UNION_SAT_DOSE` take a list (`2560/10240,1280/5120`): the newest run of the first dose that exists, else the second. One function, one test; or, by hand, a written Sunday-morning rule: if the D12800 is not done at 08:30, export the D6400 dose before the 09:10 build. |
| 4 | **The real Saturday dose through `pick_saturday_run`** (group, window start, `superseded`, sidecars) | The smoke's supply is a boom-only 0/3200 build, so the receipt-matching path for 2560/10240 on a real D12800 receipt runs first on Sunday. | Friday's re-smoke on the lazy-cuts pin: name the dose the timers will use, or run the picker alone against a copy of the Week-3 D12800 receipt. |
| 5 | **`ENTER_SMALL_OVERLAP_MAX_ENTRIES=10` and `UNION_SLEEVE_CAP=0.5`** in a published, swapped bundle | Both merged after the Week-3 rehearsals; the operator's condition for the 10-entry extension is that the smoke covers it. | Today's publish + swap steps with both set; the layout record and `small_overlap` in the receipt checked. |
| 6 | **A pin move on Friday** (`EXPECT_SHA` → the lazy-cuts commit) | Every validator that embeds the pin re-arms; the Week-3 lesson was that a pin or constant change breaks the next run. | The full smoke again on the new pin, not a partial one, and `check_prospective_gates.py` after the move. If there is no time for the full smoke, no pin move: Week 4 stays on `826d8de6`. |
| 7 | **R4's post-lock edit upload with a real DraftKings file** | Never rehearsed; the Thursday entry that would have produced a real export was withdrawn. | The laptop's scratch rehearsal today on the smoke bundle plus the FINAL export copy — confirm it ran and what it checked. |
| 8 | **The Saturday reminders** | Wednesday's 09:33 and 09:41 reminders never fired because the session was busy. | The laptop keeps Saturday morning free of foreground work (its own note); the operator checks the 09:47 refresh and the 10:30 build himself. |
| 9 | **Week-3 Monday scoring** | No completion record (the laptop's audit). | Verify and run today; it is the last settled week's record. |

## 3. Two small changes worth making before the 18:00 freeze

1. **A lag-only fallback for the term, instead of no term.** Today the chain's order is TabPFN → blend → nothing, and
   the blend needs the same LineStar capture TabPFN does, so "no LineStar" means "no term". Saturday's lag file
   (`ownership_lag.csv`, built anyway) is a provably pre-lock predictor that L20 read SUPPORTED on its own
   (LAG_010: +22.7% tickets at p89, 34–23). Order: TabPFN → blend → **the lag file at tilt 0.10** → nothing. It is one
   more branch in the same fallback block with the same loud banner.
2. **The fallback supply** (item 3 above), by code if it fits before 18:00, by a written rule if not.

Everything else in §2 is a check, not a change.

## 4. What is right and should not be touched

The term's fallback banners fired exactly as designed in the smoke; the overlap limit never refuses; the frozen-bundle
swap keeps the published rows; L19, L25, L26 and L07 are read, re-run byte-identical and in the ledger; the chalk-core
sleeve is a Week-5 build with a frozen read ahead of it; the late swap is paper. The decisions taken (M = 5, sleeve cap
0.5, TabPFN armed with a loud fallback, the 10-entry extension conditional on the smoke) stand.
