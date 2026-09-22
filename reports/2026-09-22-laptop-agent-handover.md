# Handover for the incoming laptop agent — 2026-09-22

Read this first. It is written for an agent with no memory of this project.
For deep background, `reports/2026-09-21-production-handover.md` (on branch
`production/in-season-rules-20260919` @ `52acb4ab`) is still accurate about
architecture and history; this document supersedes it on **current state, roles and
what to do next**.

---

## 1. Roles this week — read this before doing anything

**The operator's instruction, 2026-09-22: for Week 3, the production agent is in charge.**
That is this session, working in `~/projects/nfl-predictions`. This changes next week.

So for the rest of Week 3:

- **Production decides.** If you and production disagree on a money-path change, production's
  call stands for this week. Say so plainly if you think it is wrong — being overruled is
  fine, being silently right is not.
- **You are the second party**, which is the valuable part. The single most useful thing you
  can do is **verify claims rather than accept them**. On 2026-09-21 two commits titled
  "corrected" left every reported defect live, and one test passed only because its fixture
  used values production cannot emit. Run the suites before believing a pass.
- **The previous lab agent is gone** (the operator lost access to that model on 2026-09-22).
  Every decision that was "open with the lab" was taken over by production and ruled on in
  `reports/2026-09-22-decisions-taken-after-the-lab-closed.md`. Do not wait on the lab for
  anything; there is no lab.

## 2. The clock

**Week 3 locks Sunday 2026-09-27 17:00 UTC. Draft group 153769.** That group has 633 skill
players (group 153768 is a different, larger classic group — do not confuse them).

## 3. Where everything is

| what | where |
|---|---|
| production repo (**PUBLIC**) | `~/projects/nfl-predictions` |
| production working branch | `production/week3-integration-20260921` |
| production worktree in use | `~/projects/.nfl-predictions-worktrees/week3-readiness-20260921` |
| lab repo | `~/projects/nfl2` — **main checkout is mid-merge with an unresolved conflict; do not work in it** |
| **money-path clone** | `~/projects/.nfl2-worktrees/week3-live-center`, detached at **`69f98a7`** |
| Week-2 release worktree | `~/projects/.nfl2-worktrees/week2-release-2dc116c` — **must stay CLEAN at `2dc116c`** |
| nfl2 fix branch | `fix/doubtful-eligibility-20260922` @ `69f98a7`, pushed |
| operator inputs (**never commit**) | `/home/erich/week3-sunday/{contests.json,chosen-dose.env}`, mode 0600, also in `gs://nfl-predictions-503414-raw/week-inputs/2026/w03/` |

`HANDOFF.md` on the integration branch is the authoritative running record, newest entry
first. A SHA written into any report is stale the moment someone commits; read `HANDOFF.md`
for the live tip.

## 4. What changed in the money path today — verify this yourself

**Doubtful players are now excluded at DK-status eligibility.** `nfl2/src/nfl2/live.py`
`DK_INACTIVE_STATUSES` was `{"O","OUT","IR"}` and is now `{"O","OUT","IR","D"}`.

Why: in Week 2 the receipt read `retained_designations: {"Q": 10, "D": 3}` — Doubtful was
retained *by design* and priced exactly like a healthy player. Zay Flowers was Doubtful at
build time, held **48 of the 97 entered rows including the Millionaire seat**, and scored
**0.0**. All three Doubtful players scored zero; none played. 51 of 97 rows carried one.

It is an **availability** rule, the same class as OUT and IR, not an exposure cap: the
objective, the draws and the construction rules are untouched, so the book and the
prospective shadows move together and stay mutually consistent.

**Questionable is deliberately NOT excluded.** Week-2 rows holding a Questionable player
averaged 98.3 against 98.4 for the rest, and the two with posted props were among the better
outcomes (Olave 22.6, Burrow 16.2). The asymmetry is specific to D.

How it reached the money path: a real nfl2 commit, not a patch on a dirty clone. The clone
was moved to `69f98a7` and `EXPECT_SHA` in `scripts/week_env.sh` moved with it, so the
runtime preflight still verifies an exact identity instead of being overridden. Both roles
pass:

```
week runtime preflight ok: role=build    ... clone=69f98a752be4... group=153769 book_entries=198 layout=sequential
week runtime preflight ok: role=watchers ... clone=69f98a752be4...
```

**Worth your independent check**, because it is the only behavioural change to the Sunday
path this week. Three players is not a sample; the argument is structural (OUT/IR are
excluded because they cannot play, Doubtful is ~75% likely not to play, DK prices them close
to normally). If you think that is wrong, say so — there is still time.

## 5. Remaining Week-3 work, strictly ordered — all Cloud Run

1. **`build-features` for week 3.** Tuesday 2026-09-22 at the earliest: `project-slate`
   resolves its week as `MIN(week) WHERE gameday >= CURRENT_DATE()`, so a Monday game makes
   that the PREVIOUS week.
2. **Re-run `tabpfn-gen` with `TABPFN_UPCOMING=2026:3`, AFTER build-features.** The cache
   currently holds **51 rows** for week 3 and it is wrong — see §6.
3. **`project-slate`.**

Then the gate should go green:
```
cd ~/projects/.nfl-predictions-worktrees/week3-readiness-20260921
PYTHONPATH=$PWD/src <venv>/python scripts/check_build_inputs.py --season 2026 --week 3 \
  --draft-group 153769 --chosen-dose /home/erich/week3-sunday/chosen-dose.env \
  --contests /home/erich/week3-sunday/contests.json
```
Right now it FAILs on projections, market_monitor and tabpfn — all three expected until the
sequence above runs.

## 6. Traps that have already cost this project real weeks

- **The TabPFN cache lies about completeness.** A `tabpfn-gen` run made *before*
  `build-features` wrote 51 rows and the old gate went green on `rows > 0`. The gate now
  derives a floor from the slate (`51 < 506 = 80% of 633`) and fails. It also **truncates
  and rewrites**: 2026 week 2's rows are *gone*, destroyed by that bad run. Order matters.
- **`dk_salaries.week` is NULL on every row.** A slate can only be found by
  `draft_group_id`. That is why `--draft-group` exists and is not optional in practice.
- **Worktree imports.** The venv is an editable install pointing at the MAIN checkout, so
  `import nfl_dfs` from a worktree silently loads main's `src`. Always set
  `PYTHONPATH=<worktree>/src`. Scripts invoked *by path* do come from the worktree, which is
  what makes it deceptive.
- **Never `git checkout --` a file carrying uncommitted work.** That silently discarded a
  real change mid-mutation-test on 2026-09-21. Commit first, then mutate, then restore.
- **Never put a script name in `pkill -f` / `pgrep -f`** — the pattern matches the checking
  command's own command line. That created an infinite loop on 2026-09-22.
- **Never pass `-q` to pytest here**; addopts is already quiet and `-qq` drops the summary
  line the commit gate reads.
- **The production repo is PUBLIC.** `contests.json` is the stake plan and must never be
  committed. Licensed vendor data (`/sis/`, `fantasy-points/`) and raw DK entries/standings
  must never be committed.

## 7. Standing operational state

- **DK ingest is the sole source of DK salaries.** Cloud Run `ingest-dk` has failed 60+ runs
  on a DraftKings 403. A tracked host loop carries it: pid in
  `/home/erich/week1-sunday/host_ingest_dk_loop.pid`, hourly, healthy, zero `pair failed`.
  Its log mixes UTC banners with LOCAL-time python lines (CDT = UTC−5), so the newest logger
  stamp always looks five hours stale — **never restart on that stamp alone.**
- **`s-cfb` / `s-cfb-sat` are PAUSED** (deterministic DK 403, zero NFL readers). The re-arm
  procedure is in `status.py`: resume both, confirm one pull returns 200, *then* restore
  `alert=True`. `alert=False` with the schedulers paused would make CFB permanently
  uncollected **and** permanently silent.
- **Prospective gates:** `PYTHONPATH=$PWD/src <venv>/python scripts/check_prospective_gates.py --week 3`.
  Expected output is now **one `ok` line and a clean verdict**. The previous four
  `sis-pass-tail` WARNs are gone — that pair was ruled DORMANT, with the reasoning recorded
  in the registry. **Their reappearance is now the departure to report.**
- **The exposure-cap sheet emits every Sunday** as step 6 of `sunday_build_host.sh`
  (`scripts/exposure_cap_book.py`). It enters nothing. **Decision taken: the capped book is
  NOT uploaded for Week 3** — the pre-lock shadows grade the selector's book, and a
  multi-week instrument outweighs a one-slate edge. Read the sheet before upload anyway.

## 8. Do not do these

- Do not launch **PREREG-101**.
- Do not re-run or re-read **PREREG-099**; it is READ and CLOSED. Verdict: doubling 2.011
  [1.883, 2.228]. Its K80 secondary FAIL rests on a season-clustered bootstrap degenerate on
  one season, so only "no detectable improvement" survives; prelock findability of 220+
  supply is **not** established, and 099 cannot license a dose change.
- Do not read **bank 991** — complete but deliberately unread, needs an operator protocol
  decision.
- Do not redo the **sleeve pilot** (delivered) or the **route-share gate** (done).
- Do not touch `~/projects/.nfl2-worktrees/week2-release-2dc116c`.

## 9. Open, and honest about it

- **Laptop review item 1** needs a re-run at the serving commit; **item 2's per-bug
  consolidation** is unwritten. Both are reporting, not repair — good first tasks.
- **Queued deliberately until after Week 3:** re-freeze the runtime contracts against Python
  `3.14.4-1ubuntu0.2`; point `ci.yml` at `scripts/test_lanes.sh` so a CI failure email carries
  signal; resolve evidence-graph pins at the recorded commit (nothing has been re-pinned to
  head — that would assert today's code produced August's evidence).
- **Exploration sleeve** has three reproduced fail-open paths (a nine-player lineup
  containing a kicker is accepted; `qb_safe_ids=None` silently disables the QB gate; a DST
  row without `opp` skips the RB-vs-DST rule). Research-only, not the money path, parked.
- **Week 2 settled: $245 in, $26 back.** Week 1: ~$400 in, ~$140 back. That is the baseline
  any continue-or-stop argument has to beat.

## 10. How to reach production

Write a report under `reports/` and push to `production/week3-integration-20260921`.
Production polls that branch. If you need an nfl2 fix, production owns the money-path clone
this week — send the patch plus a failing test under `reports/lab-handoffs/` rather than
moving the clone yourself.
