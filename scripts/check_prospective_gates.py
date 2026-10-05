#!/usr/bin/env python3
"""Fail loudly when a frozen prospective gate is not armed to capture its weeks.

WHY THIS EXISTS (2026-09-18).  The 2026 Route Share prospective shadow gate grades
Sunday-main Weeks 2-18 and needs a control/treatment pair frozen BEFORE each lock.
Its two Cloud Scheduler jobs sat PAUSED and nobody noticed until Week 2 was two days
away.  Eighteen of the twenty shadow schedulers were paused.  Worse, the two jobs the
gate names still carried N_BOOM=28 while the adopted money path is boom-first
N_BOOM=160 / N_LEV=40, so resuming them would have burned a graded week comparing a
policy we no longer run -- an invalid week that looks complete is worse than a missing
one.  A prose reminder would not have caught either failure.  This check does.

It is deliberately fail-closed in three directions:

  1. A gate inside (or about to enter) its graded window whose scheduler is PAUSED.
  2. A gate whose target Cloud Run job contradicts the policy the gate declares.
  3. ANY shadow/freeze scheduler not classified in GATES below.  Silence was the
     original failure, so an unrecognised job is an error, not a shrug.  Classify it
     here -- as a real gate or as deliberately dormant, with a reason -- or it fails.
  4. (2026-10-05, O-25/O-27) A target job whose runs FAIL.  ENABLED and on-policy is not
     armed if every execution dies: the Route Share pair failed 8/8 runs in Weeks 3-4 at
     its image guard, and shadow-cbwu-oi-paired failed every run from 09-13 while this
     list called it "ENABLED and running" -- both invisible to checks 1-3.  For each
     graded (or upcoming) gate's target jobs, and for any DORMANT scheduler that is in
     fact ENABLED, the newest finished execution must have SUCCEEDED, and a gate graded
     last week must have finished an execution within its cadence.
  5. (2026-10-05, O-27) A target job whose IMAGE predates a fix the gate requires.  The
     CBWU-OI pair failed 8/8 Sunday runs because its job was still pinned to a 09-06 image
     that predates 193e1b44 (a DK draft group is enterable only until its first game
     starts): every Sunday after a Thursday game it read the stale full-week group and
     died at the inference-row guard.  A gate may list require_code_ancestors; the job's
     CODE_SHA must contain each one (git merge-base --is-ancestor), else it is an error.
  6. (2026-10-05, O-9/O-27) An ENABLED scheduler in DORMANT.  A dormant entry stops a job
     being audited, so a job that fires every week may not sit there; classify it as a
     gate (with its contract) or pause it.

Usage:
    python scripts/check_prospective_gates.py            # audit the current week
    python scripts/check_prospective_gates.py --week 5   # audit a future week
    python scripts/check_prospective_gates.py --json     # machine-readable

Exit 0 = every gate that needs to be armed is armed and consistent.  Exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = "nfl-predictions-503414"
LOCATION = "us-central1"
LOOKAHEAD_WEEKS = 2  # warn this far before a gate's first graded week
CADENCE_DAYS = 7     # the Sunday shadows run weekly; a gate may override with cadence_days
EXECUTION_LIMIT = 10 # newest executions read per job (read-only)

# Every scheduler whose name matches this is either a classified gate below or an error.
SHADOW_PATTERN = ("shadow", "freeze", "tail")
REPO_ROOT = Path(__file__).resolve().parents[1]

# A live-path fix every Sunday-main shadow image must contain (O-27 class). Before it, the
# projection pool kept a DK draft group while its LAST game was ahead, so after a Thursday
# game a Sunday run read the stale full-week group (already-played teams).
POOL_FIX_193E1B44 = {
    "193e1b44d2b43eed70cc9b5688b3700d2054046d":
        "projection pool: a DK draft group is enterable only until its FIRST game starts",
}
# O-3: the SIS pass-tail paired job's live ASOE reads the FP team alignment window; the
# table has no source_week_start/end columns, so the read must derive them (absent from
# the registered 15de4020 build, which therefore failed every Week 5+ run).
SIS_ASOE_TEAM_WINDOW_72261A27 = {
    "72261a27f44bc8e9a876dfc5c394517fa2847f32":
        "live ASOE derives the team alignment window (the table has no source_week_*)",
}

# --- The registry.  One entry per frozen prospective gate. ------------------------
# first_week/last_week are the Sunday-main weeks the gate GRADES (inclusive).
# adjudicates says WHEN a verdict can be read, and therefore when the gate could change
# anything.  A gate that adjudicates only after the final graded week cannot improve the
# CURRENT season no matter how well it runs -- losing one of its weeks costs the
# multi-season instrument, not this year's results.  Say so in the output, because
# conflating the two overstates urgency and misleads the operator about what his research
# is buying him this season.
# floor_weeks is the minimum complete paired weeks the gate needs, if it states one.
# require_env asserts what the target Cloud Run job must declare for the comparison to
# be the current policy.  None means "not yet ruled on" and is reported, never assumed.
# require_env_by_scheduler (2026-10-05, O-3) overrides require_env per scheduler when the
# gate's jobs legitimately differ (two cache arms and a paired job); same_env_across_jobs
# names keys every target job must carry with ONE identical value (e.g. CODE_SHA, so the
# three jobs of one pair cannot run different builds).
GATES = {
    "fp-route-share-2026": {
        "doc": "reports/2026-08-11-route-share-2026-shadow-gate.md",
        "first_week": 2,
        "last_week": 18,
        "floor_weeks": 12,
        "schedulers": [
            "s-shadow-k1-roleunion-early", "s-shadow-k1-roleunion-late",
            "s-shadow-k1-route-roleunion-early", "s-shadow-k1-route-roleunion-late",
        ],
        # 2026-09-22: the gate needs all four registries retrained weekly on one cutoff, and the
        # route treatment needs the Thursday feature rebuild after Wednesday's W-1 import. All
        # five sat PAUSED since August while the shadows were ENABLED -- the shadows would have
        # graded August models. A paused input is as fatal as a paused shadow.
        "input_schedulers": ["s-train-k1", "s-train-k1-role", "s-features-route",
                             "s-train-k1-route", "s-train-k1-route-role"],
        "require_env": {"N_BOOM": "160", "N_LEV": "40"},
        # 2026-09-22 (operator): focus is THIS season. The gate's own full-season verdict is
        # unchanged, but each scored paired week is read immediately under the in-season
        # adoption track (reversible trials, weekly reads) -- so a lost week now costs 2026 too.
        "adjudicates": "gate verdict after ALL of weeks 2-18 are frozen and scored; EACH scored "
                       "paired week is also read immediately for the in-season reversible-trial "
                       "track (operator directive 2026-09-22).",
        "in_season_value": True,
        "note": "Control shadow-k1-roleunion vs treatment shadow-k1-route-roleunion; the "
                "treatment must differ ONLY by the four Fantasy Points route features. "
                "Weekly paired reads feed 2026 decisions; the full-season verdict feeds the "
                "Fantasy Points renewal.",
        # 2026-10-05 (reviewer, O-25): from Week 5 the companion key alone audits the four
        # schedulers, so the same failure is not printed twice under two contracts. This
        # entry's contract and verdict text above are kept as the record.
        "superseded_from_week": 5,
        "superseded_by": "fp-route-share-2026-companion-v1",
        "superseded_reason": "superseded by fp-route-share-2026-companion-v1 from W5; W2 under "
                             "the old contract, W3-W4 failed (O-25); history kept",
    },
    # 2026-10-05 (operator chose option (a) for O-2/O-25): the same pair, under companion v1
    # -- the adopted money-path generation stated in full -- from Week 5 (Weeks 3-4 failed
    # 8/8 at the image guard and produced no books). The frozen contract above is unchanged.
    # require_env is EXACTLY what the jobs must carry, and equals
    # nfl_dfs.inference.tail_shadow.route_share_job_environment("companion-v1") -- every
    # value derived from ClassicProductionPolicy.engine_environment(); a test pins the
    # equality, so this registry, the image guard and the update command cannot diverge.
    "fp-route-share-2026-companion-v1": {
        "doc": "reports/2026-08-11-route-share-2026-shadow-gate.md",
        "policy_doc": "reports/2026-09-19-route-share-current-policy-companion.md",
        "first_week": 5,
        "last_week": 18,
        "floor_weeks": 12,
        # Weeks 5-18 offer 14 paired weeks against the gate document's 12-week floor, so at
        # most two may be lost. A third missed week makes the floor unreachable in 2026: the
        # gate then ends "insufficient" (retained per the gate document) -- not pass or fail.
        "max_missed_weeks": 2,
        "insufficient_rule": "a third missed paired week (of 14, W5-W18) leaves fewer than the "
                             "12-week floor: the 2026 read ends INSUFFICIENT, not pass/fail.",
        "schedulers": [
            "s-shadow-k1-roleunion-early", "s-shadow-k1-roleunion-late",
            "s-shadow-k1-route-roleunion-early", "s-shadow-k1-route-roleunion-late",
        ],
        "input_schedulers": ["s-train-k1", "s-train-k1-role", "s-features-route",
                             "s-train-k1-route", "s-train-k1-route-role"],
        "require_env": {
            "ROUTE_SHARE_CONTRACT": "companion-v1",
            "GEN_TOTAL_BUDGET": "172",
            "N_LEV": "40",
            "N_CE": "0",
            "N_EPISTEMIC": "12",
            "N_BOOM": "160",
            "N_GUMBEL": "0",
            "REPLACEMENT_SLOTS": "12",
            "BOOM_UNIQUE_FILL": "0",
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": "target_share_last,carry_share_last,snap_share_last,"
                                    "target_share_jump,carry_share_jump,snap_share_jump",
            "ROLE_BELIEF_SEED": "7331",
            "CE_SEED": "1701",
            "BLEND_MODEL_WEIGHT": "0.45",
            "LIVE_SIMS": "30000",
            "GAME_SIM_MODE": "possession",
            "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
            "MODEL_ENSEMBLE": "1",
            "MIN_LINEUP_SALARY": "49000",
        },
        # 2026-10-05 (O-27 class sweep): the pair builds from the same live pool query.
        "require_code_ancestors": POOL_FIX_193E1B44,
        "adjudicates": "final scientific read after Week 18 per the gate document; weekly "
                       "in-season decision record per Amendment 1 v2.",
        "in_season_value": True,
        "note": "Companion v1 of the frozen Route Share contract: control shadow-k1-roleunion vs "
                "treatment shadow-k1-route-roleunion under the adopted money-path generation "
                "(role 12 / boom 160 / lev 40 / CE 0, served position scales), single seed, "
                "exact-80. Its rows are NOT frozen-contract rows; the weekly record states "
                "which consumer it describes (production K80, not the lab union K).",
    },
    # 2026-10-05 (operator: fix O-27, do not pause). Listed in DORMANT until today with the
    # reason "ENABLED and running" while every Sunday run from 09-13 failed on its stale
    # 09-06 image. It IS a frozen prospective gate: the 2026-08-18 spec grades every 2026
    # regular-season Sunday-main week once after Week 18 (earliest frozen panel per week), on
    # the incumbent 160/40 population. Operator 2026-10-04: from Week 5 the pair runs the
    # CURRENT money path (companion v1, below); this frozen comparison ends with its one
    # panel (Week 1) and is not adjudicated. Kept as the record.
    "cbwu-oi-2026": {
        "doc": "reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md",
        "first_week": 1,
        "last_week": 18,
        "floor_weeks": None,  # the spec states none; interim read only at >=12 weeks
        "lost_weeks": {
            2: "every run failed (stale 09-06 image; O-27)",
            3: "every run failed (stale 09-06 image; O-27)",
            4: "every run failed (stale 09-06 image; O-27)",
        },
        "schedulers": ["s-shadow-cbwu-oi-paired-early", "s-shadow-cbwu-oi-paired-late"],
        "require_env": {"CBWU_OI_CONTRACT": "2026-cbwu-oi-v1"},
        "require_code_ancestors": POOL_FIX_193E1B44,
        "adjudicates": "was: once, after Week 18, on the frozen panels (spec). Superseded "
                       "from Week 5; not adjudicated.",
        "in_season_value": False,
        "note": "Control = adopted CBWU combine, treatment = frozen CBWU-OI-v1 union, on the "
                "identical five R0-R4 books of the incumbent 160/40 population.",
        "superseded_from_week": 5,
        "superseded_by": "cbwu-oi-2026-companion-v1",
        "superseded_reason": "operator 2026-10-04: moved to the current policy; the frozen "
                             "160/40 comparison ends (W1 only), not adjudicated",
    },
    # 2026-10-05 (operator 2026-10-04): the same pair under companion v1 -- the adopted
    # money-path generation and selector, treatment differing only by the CBWU-OI combine
    # law -- from Week 5, read weekly under the in-season adoption track v2. require_env is
    # EXACTLY what the job must carry and equals
    # nfl_dfs.inference.prospective_shadow.cbwu_oi_job_environment("2026-cbwu-oi-companion-v1")
    # -- every value derived from ClassicProductionPolicy.engine_environment(); a test pins
    # the equality, so this registry, the runner and verify_deployment cannot diverge.
    "cbwu-oi-2026-companion-v1": {
        "doc": "reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md",
        "policy_doc": "reports/2026-09-19-in-season-adoption-track.md",
        "first_week": 5,
        "last_week": 18,
        "floor_weeks": None,
        "schedulers": ["s-shadow-cbwu-oi-paired-early", "s-shadow-cbwu-oi-paired-late"],
        "require_env": {
            "CBWU_OI_CONTRACT": "2026-cbwu-oi-companion-v1",
            "GEN_TOTAL_BUDGET": "172",
            "N_LEV": "40",
            "N_CE": "0",
            "N_EPISTEMIC": "12",
            "N_BOOM": "160",
            "N_GUMBEL": "0",
            "REPLACEMENT_SLOTS": "12",
            "BOOM_UNIQUE_FILL": "0",
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": "target_share_last,carry_share_last,snap_share_last,"
                                    "target_share_jump,carry_share_jump,snap_share_jump",
            "ROLE_BELIEF_SEED": "7331",
            "CE_SEED": "1701",
            "BLEND_MODEL_WEIGHT": "0.45",
            "LIVE_SIMS": "30000",
            "GAME_SIM_MODE": "possession",
            "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
            "MODEL_ENSEMBLE": "1",
            "MIN_LINEUP_SALARY": "49000",
            "MULTISEED_SEED_PAIRS": "R0=0:7331;R1=1137260708:2690847602;"
                                    "R2=2875959182:1630284992;R3=253722715:3374646876;"
                                    "R4=1643280042:3977633467",
            "MULTISEED_WORLDS_PER_BLOCK": "10000",
            "MULTISEED_CANDIDATE_ENTRY_BASIS": "80",
            "SELECT_LSE": "0",
            "MULTISEED_PORTFOLIO": "CBWU_OI_SHADOW",
        },
        "require_code_ancestors": POOL_FIX_193E1B44,
        "adjudicates": "each scored paired week is read under the in-season adoption track v2 "
                       "(reports/2026-09-19-in-season-adoption-track.md); never pooled with "
                       "the frozen 160/40 panel.",
        "in_season_value": True,
        "note": "Control = the money path's CBWU combine, treatment = CBWU-OI-v1 union, on the "
                "identical five R0-R4 books of the adopted boom-first 40/160 generation; "
                "exact-80, tail 194, outcome-blind, production_enabled=false.",
    },
    # 2026-09-22 (operator): the pass bar was frozen before the pair ever ran and grades only
    # unplayed weeks 5-18, so it is not the retrospective design the earlier DORMANT ruling
    # guarded against.
    # 2026-10-05 (O-3, Amendment 1; operator 2026-10-04: "we absolutely can change things
    # mid-season because if we don't get things working in the next week or two, there's
    # going to be not another week."). The registered build CODE_SHA 15de4020 could not run
    # (cache: no `salary` in the inference table; paired: no source_week_* in the team
    # alignment table; and it predates 193e1b44). The contract is SPLIT:
    #   * this key -- the two TabPFN DISTRIBUTION caches, exactly as frozen plus two repairs
    #     (contract pass-tail-v1-a1). The frozen pass bar's decision rules are all book-level
    #     and end unadjudicated; the caches are read by the distribution rule of Amendment 1.
    #   * sis-pass-tail-2026-companion-v1 -- the paired BOOKS on the current money path.
    # require_env_by_scheduler == sis_pass_tail_shadow.job_environment(role) (test-pinned).
    "sis-pass-tail-2026": {
        "doc": "reports/2026-09-22-sis-pass-tail-2026-pass-bar.md",
        "amendment_doc": "reports/2026-10-05-sis-pass-tail-2026-amendment-1.md",
        "first_week": 5,
        "last_week": 18,
        "floor_weeks": 10,
        "schedulers": ["s-tabpfn-sis-pass-tail-control", "s-tabpfn-sis-pass-tail-treatment"],
        "require_env": {"SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1"},
        "require_env_by_scheduler": {
            "s-tabpfn-sis-pass-tail-control": {
                "SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1",
                "TABPFN_SIS_PASS_TAIL_LIVE_ARM": "control",
                "TABPFN_OUTPUT_TABLE": "tabpfn_sis_pass_tail_live_control_v1",
                "TABPFN_UPCOMING": "auto",
            },
            "s-tabpfn-sis-pass-tail-treatment": {
                "SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1",
                "TABPFN_SIS_PASS_TAIL_LIVE_ARM": "treatment",
                "TABPFN_OUTPUT_TABLE": "tabpfn_sis_pass_tail_live_treatment_v1",
                "TABPFN_UPCOMING": "auto",
            },
        },
        "same_env_across_jobs": ["CODE_SHA"],
        "require_code_ancestors": {**POOL_FIX_193E1B44, **SIS_ASOE_TEAM_WINDOW_72261A27},
        "superseded_require_env": {"CODE_SHA": "15de40206963b5db9e6a4acff0f865833678d44d"},
        "adjudicates": "distribution rule of Amendment 1 (paired quantile score, QB/WR/TE, "
                       "week-clustered): one interim look after Week 11, final after Week 18. "
                       "The frozen pass bar's book criteria end unadjudicated.",
        "in_season_value": False,
        "note": "Protocol reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md; needs "
                "the operator's Wednesday SIS acquisition from Week 5 (W1-4 backfill at W5). "
                "A missing W-1 SIS week is an explicit, recorded no-run.",
    },
    # 2026-10-05 (O-3, Amendment 1): the paired BOOKS under the adopted money-path generation
    # (single-seed books on the five registered seed pairs; the arms differ ONLY in the SIS
    # TabPFN cache). require_env == sis_pass_tail_portfolio.paired_job_environment(companion),
    # every value derived from ClassicProductionPolicy.engine_environment() (test-pinned).
    # Its weeks are never pooled with any August-generation book.
    "sis-pass-tail-2026-companion-v1": {
        "doc": "reports/2026-09-22-sis-pass-tail-2026-pass-bar.md",
        "amendment_doc": "reports/2026-10-05-sis-pass-tail-2026-amendment-1.md",
        "policy_doc": "reports/2026-09-19-in-season-adoption-track.md",
        "first_week": 5,
        "last_week": 18,
        "floor_weeks": 10,
        "schedulers": ["s-shadow-sis-pass-tail-paired"],
        "input_schedulers": ["s-tabpfn-sis-pass-tail-control",
                             "s-tabpfn-sis-pass-tail-treatment"],
        "require_env": {
            "SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1-companion",
            "GEN_TOTAL_BUDGET": "172",
            "N_LEV": "40",
            "N_CE": "0",
            "N_EPISTEMIC": "12",
            "N_BOOM": "160",
            "N_GUMBEL": "0",
            "REPLACEMENT_SLOTS": "12",
            "BOOM_UNIQUE_FILL": "0",
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": "target_share_last,carry_share_last,snap_share_last,"
                                    "target_share_jump,carry_share_jump,snap_share_jump",
            "CE_SEED": "1701",
            "BLEND_MODEL_WEIGHT": "0.45",
            "LIVE_SIMS": "30000",
            "GAME_SIM_MODE": "possession",
            "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
            "MODEL_ENSEMBLE": "1",
            "MIN_LINEUP_SALARY": "49000",
        },
        "same_env_across_jobs": ["CODE_SHA"],
        # The paired job and the two cache jobs it reads must be ONE build.
        "same_env_include_inputs": True,
        "require_code_ancestors": {**POOL_FIX_193E1B44, **SIS_ASOE_TEAM_WINDOW_72261A27},
        "adjudicates": "weekly in-season decision record (adoption track v2) with the book rule "
                       "of Amendment 1: one interim look after Week 11, final after Week 18.",
        "in_season_value": True,
        "note": "Companion of the SIS pass-tail pair on the current money path; reads the "
                "distribution caches of sis-pass-tail-2026.",
    },
}

# Schedulers deliberately dormant.  A reason is mandatory: this is the list that has to
# stay honest, because anything parked here stops being audited as a live gate.
DORMANT = {
    "s-shadow-k1-early": "K1 single-shadow superseded by the paired roleunion gate.",
    "s-shadow-k1-late": "K1 single-shadow superseded by the paired roleunion gate.",
    "s-shadow-k1-nofloor-early": "No-floor variant; no frozen prospective gate depends on it.",
    "s-shadow-k1-nofloor-late": "No-floor variant; no frozen prospective gate depends on it.",
    "s-shadow-k3-early": "K3 shadow; no frozen prospective gate grading 2026 weeks.",
    "s-shadow-k3-late": "K3 shadow; no frozen prospective gate grading 2026 weeks.",
    "s-shadow-archetype-paired-early": "Archetype pair; no frozen 2026 prospective gate.",
    "s-shadow-archetype-paired-late": "Archetype pair; no frozen 2026 prospective gate.",
    "s-freeze-tail-early": "Tail-freeze capture; superseded by the live enter-bundle path.",
    "s-freeze-tail-late": "Tail-freeze capture; superseded by the live enter-bundle path.",
    "s-shadow-cbwu-volume": "Route-tail union volume probe; research intake, not a graded gate.",
    # 2026-10-05 (O-27): s-shadow-cbwu-oi-paired-early/-late LEFT this list. Their reason
    # read "ENABLED and running; ownership-inclusive paired shadow" -- every run since 09-13
    # had failed, and OI is "order-invariant". They are GATES["cbwu-oi-2026"].
    # 2026-09-22: the SIS pass-tail pair was ruled dormant earlier today and re-opened the same
    # day with a pass bar frozen before it ever ran (GATES["sis-pass-tail-2026"]).
}


def sh(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout.strip()


def schedulers() -> dict[str, dict]:
    out = sh(["gcloud", "scheduler", "jobs", "list", "--project", PROJECT,
              "--location", LOCATION, "--format", "value(name,state,schedule)"])
    found = {}
    for line in filter(None, out.splitlines()):
        parts = line.split("\t")
        name = parts[0].split("/")[-1]
        found[name] = {"state": parts[1] if len(parts) > 1 else "?",
                       "schedule": parts[2] if len(parts) > 2 else "?"}
    return found


def job_env(job: str) -> dict[str, str]:
    out = sh(["gcloud", "run", "jobs", "describe", job, "--project", PROJECT,
              "--region", LOCATION, "--format", "json"])
    if not out:
        return {}
    try:
        c = json.loads(out)["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
    except Exception:
        return {}
    return {e["name"]: e.get("value", "") for e in c.get("env", [])}


def code_contains(code_sha: str, commit: str) -> bool | None:
    """Does the image commit CODE_SHA contain `commit`? None = cannot tell locally."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", commit, code_sha],
        capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def code_problems(job: str, env: dict[str, str], required: dict[str, str]) -> list[str]:
    code_sha = (env.get("CODE_SHA") or "").strip()
    if not code_sha:
        return [f"job {job} declares no CODE_SHA, so its image cannot be checked for "
                f"required fixes {sorted(c[:8] for c in required)}"]
    problems = []
    for commit, why in required.items():
        contained = code_contains(code_sha, commit)
        if contained is False:
            problems.append(f"job {job} runs CODE_SHA {code_sha[:12]}, which predates required "
                            f"fix {commit[:8]} ({why}). Rebuild the image and update the job.")
        elif contained is None:
            problems.append(f"job {job}: cannot tell whether CODE_SHA {code_sha[:12]} contains "
                            f"fix {commit[:8]} (git fetch, then re-run)")
    return problems


def job_executions(job: str) -> list[dict] | None:
    """Newest executions of one Cloud Run job (read-only). None = could not read."""
    proc = subprocess.run(
        ["gcloud", "run", "jobs", "executions", "list", "--job", job, "--project", PROJECT,
         "--region", LOCATION, "--limit", str(EXECUTION_LIMIT), "--format", "json"],
        capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout or "[]")
    except ValueError:
        return None
    return rows if isinstance(rows, list) else None


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def execution_outcome(row: dict) -> tuple[str, str, datetime | None]:
    """-> (name, SUCCEEDED|FAILED|RUNNING, finished-or-created time)."""
    meta = row.get("metadata") or {}
    status = row.get("status") or {}
    name = str(meta.get("name", "?"))
    completed = next((c for c in status.get("conditions") or []
                      if c.get("type") == "Completed"), None)
    when = _parse_time(status.get("completionTime")) or _parse_time(
        meta.get("creationTimestamp"))
    if completed and completed.get("status") == "True":
        return name, "SUCCEEDED", when
    if completed and completed.get("status") == "False":
        return name, "FAILED", when
    if status.get("completionTime"):
        failed = int(status.get("failedCount") or 0) or int(status.get("cancelledCount") or 0)
        return name, ("FAILED" if failed else "SUCCEEDED"), when
    return name, "RUNNING", when


def execution_problems(job: str, *, cadence_days: int, expect_recent: bool,
                       now: datetime) -> tuple[list[str], list[str]]:
    """(problems, notes) for one job's recent runs. A problem is a failed newest finished
    execution, an unreadable history, or -- when the gate graded last week -- no finished
    execution within the cadence. Earlier failures inside the cadence that a later success
    superseded are notes: that freeze was still lost, and the operator should see it."""
    rows = job_executions(job)
    if rows is None:
        return [f"job {job}: could not read its executions"], []
    outcomes = sorted((execution_outcome(r) for r in rows),
                      key=lambda o: o[2] or datetime.min.replace(tzinfo=timezone.utc),
                      reverse=True)
    finished = [o for o in outcomes if o[1] != "RUNNING"]
    window = now - timedelta(days=cadence_days + 1)
    recent = [o for o in finished if o[2] is not None and o[2] >= window]
    problems: list[str] = []
    notes: list[str] = []
    if finished and finished[0][1] == "FAILED":
        failed = [o[0] for o in recent if o[1] == "FAILED"] or [finished[0][0]]
        problems.append(f"job {job}: its newest finished execution FAILED ({finished[0][0]}); "
                        f"failed within {cadence_days + 1} days: {', '.join(failed)}")
    elif expect_recent and not recent:
        problems.append(f"job {job}: no finished execution within {cadence_days + 1} days, "
                        f"but the gate graded last week")
    else:
        lost = [o[0] for o in recent[1:] if o[1] == "FAILED"]
        if lost:
            notes.append(f"job {job}: newest run succeeded, but these runs within "
                         f"{cadence_days + 1} days FAILED: {', '.join(lost)}")
    return problems, notes


def scheduler_target(name: str) -> str:
    uri = sh(["gcloud", "scheduler", "jobs", "describe", name, "--project", PROJECT,
              "--location", LOCATION, "--format", "value(httpTarget.uri)"])
    return uri.split("/jobs/")[-1].replace(":run", "") if "/jobs/" in uri else ""


def audit(week: int, now: datetime | None = None) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    live = schedulers()
    now = now or datetime.now(timezone.utc)

    for gate, spec in GATES.items():
        first, last = spec["first_week"], spec["last_week"]
        superseded = spec.get("superseded_from_week")
        if superseded is not None and week >= superseded:
            notes.append(f"{gate}: SUPERSEDED from week {superseded} -- "
                         f"{spec['superseded_reason']}")
            continue
        active = first <= week <= last
        upcoming = first - LOOKAHEAD_WEEKS <= week < first
        if not (active or upcoming):
            notes.append(f"{gate}: dormant this week (grades weeks {first}-{last}).")
            continue
        when = "GRADED THIS WEEK" if active else f"first graded week is {first}"
        if spec.get("insufficient_rule"):
            notes.append(f"{gate}: may lose at most {spec['max_missed_weeks']} paired weeks -- "
                         f"{spec['insufficient_rule']}")
        if spec.get("in_season_value") is False:
            notes.append(f"{gate}: NOT a current-season lever -- {spec.get('adjudicates', '')} "
                         f"A lost week here costs the multi-season instrument, not this season.")
        paused = [s for s in spec["schedulers"] + spec.get("input_schedulers", [])
                  if live.get(s, {}).get("state", "MISSING") != "ENABLED"]
        if paused:
            msg = (f"{gate}: {when}, but these are not ENABLED: "
                   + ", ".join(f"{s}({live.get(s, {}).get('state', 'MISSING')})" for s in paused)
                   + f"  [gate: {spec['doc']}]")
            (errors if active else warnings).append(msg)
        by_scheduler = spec.get("require_env_by_scheduler") or {}
        wants: dict[str, dict | None] = {}
        for s in spec["schedulers"]:
            job = scheduler_target(s)
            if job:
                wants[job] = by_scheduler.get(s, spec["require_env"])
        targets = set(wants)
        envs: dict[str, dict[str, str]] = {}
        for job in sorted(targets):
            want = wants[job]
            env = envs[job] = job_env(job)
            if want is None:
                warnings.append(f"{gate}: job {job} has NO declared policy contract in this "
                                f"registry; rule on it before week {first}. Current env of "
                                f"interest: { {k: v for k, v in env.items() if k in ('N_BOOM', 'N_LEV')} }")
                continue
            bad = {k: env.get(k, "<unset>") for k, v in want.items() if env.get(k) != v}
            if bad:
                diff = {k: f"found {bad[k]!r}, want {want[k]!r}" for k in bad}
                errors.append(f"{gate}: job {job} contradicts the declared policy "
                              f"({len(bad)} of {len(want)} keys) -- {diff}. Resuming it would "
                              f"burn a graded week on a policy we do not run.")
        if spec.get("same_env_include_inputs"):
            for s in spec.get("input_schedulers", []):
                job = scheduler_target(s)
                if job and job not in envs:
                    envs[job] = job_env(job)
        for key in spec.get("same_env_across_jobs") or ():
            seen = {job: envs[job].get(key, "<unset>") for job in sorted(envs)}
            if len(set(seen.values())) > 1 or "<unset>" in seen.values():
                errors.append(f"{gate}: its jobs must carry ONE {key}, found {seen}. A pair "
                              f"built from two images is not one identity.")
        required_code = spec.get("require_code_ancestors") or {}
        if required_code:
            for job in sorted(targets):
                (errors if active else warnings).extend(
                    f"{gate}: {p}" for p in code_problems(job, envs[job], required_code))
        for lost, why in sorted((spec.get("lost_weeks") or {}).items()):
            notes.append(f"{gate}: week {lost} has no frozen panel -- {why}")
        graded_last_week = first <= week - 1 <= last
        for job in sorted(t for t in targets if t):
            problems, seen = execution_problems(
                job, cadence_days=int(spec.get("cadence_days", CADENCE_DAYS)),
                expect_recent=graded_last_week, now=now)
            (errors if active else warnings).extend(
                f"{gate}: {p}  [an armed job that fails every run freezes nothing]"
                for p in problems)
            notes.extend(f"{gate}: {n}" for n in seen)

    # A DORMANT scheduler is exempt from the window checks, not from running honestly: if it
    # is ENABLED its job runs every week, and a job that fails every run (O-27) is either to
    # be fixed or paused -- never left firing under a reason that says "running".
    #
    # 2026-10-05 (O-9/O-27): and an ENABLED scheduler may not be DORMANT at all, failing or
    # not -- "dormant" exempts it from every gate check while it fires every week.
    for name in sorted(DORMANT):
        if live.get(name, {}).get("state") != "ENABLED":
            continue
        errors.append(f"DORMANT-but-ENABLED {name}: a dormant scheduler is exempt from every "
                      f"gate check, so it may not fire. Classify it in GATES with its "
                      f"contract, or pause it.")
        job = scheduler_target(name)
        if not job:
            continue
        problems, _ = execution_problems(job, cadence_days=CADENCE_DAYS,
                                         expect_recent=False, now=now)
        errors.extend(f"DORMANT-but-ENABLED {name}: {p}. Pause it or fix it; a dormant "
                      f"entry may not hide a failing job." for p in problems)

    classified = set(DORMANT) | {s for g in GATES.values() for s in g["schedulers"]}
    for name, info in sorted(live.items()):
        if any(p in name for p in SHADOW_PATTERN) and name not in classified:
            errors.append(f"UNCLASSIFIED shadow scheduler {name} ({info['state']}). Add it to "
                          f"GATES or DORMANT in this script, with a reason. Silence is the bug "
                          f"this check exists to prevent.")
    return errors, warnings, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="NFL week to audit (default: ask week_env)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    week = a.week
    if week is None:
        try:
            from nfl_dfs import config  # noqa: PLC0415
            week = int(config.current_week())  # type: ignore[attr-defined]
        except Exception:
            print("could not determine the week; pass --week", file=sys.stderr)
            return 2
    errors, warnings, notes = audit(week)
    if a.json:
        print(json.dumps({"week": week, "errors": errors,
                          "warnings": warnings, "notes": notes}, indent=1))
        return 1 if errors else 0
    print(f"prospective-gate audit for week {week}")
    for n in notes:
        print(f"  ok    {n}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  FAIL  {e}")
    if errors:
        print(f"\n{len(errors)} gate problem(s). A graded week is at risk RIGHT NOW.")
        return 1
    print("\nevery gate that must be armed this week is armed and policy-consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
