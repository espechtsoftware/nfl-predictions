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

PROJECT = "nfl-predictions-503414"
LOCATION = "us-central1"
LOOKAHEAD_WEEKS = 2  # warn this far before a gate's first graded week

# Every scheduler whose name matches this is either a classified gate below or an error.
SHADOW_PATTERN = ("shadow", "freeze", "tail")

# --- The registry.  One entry per frozen prospective gate. ------------------------
# first_week/last_week are the Sunday-main weeks the gate GRADES (inclusive).
# floor_weeks is the minimum complete paired weeks the gate needs, if it states one.
# require_env asserts what the target Cloud Run job must declare for the comparison to
# be the current policy.  None means "not yet ruled on" and is reported, never assumed.
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
        "require_env": {"N_BOOM": "160", "N_LEV": "40"},
        "note": "Control shadow-k1-roleunion vs treatment shadow-k1-route-roleunion; the "
                "treatment must differ ONLY by the four Fantasy Points route features.",
    },
    "sis-pass-tail-2026": {
        # NOTE (2026-09-18): no frozen prospective-gate DOCUMENT governs this pair.  The
        # Week-5 start is implementation-derived: the shadow builds a last-four-weeks
        # context, so week 5 is the earliest target with four completed weeks.  That is a
        # finding, not a registry convenience -- a paired job with a scheduler but no
        # written gate cannot be graded.  Write the gate, or move it to DORMANT.
        "doc": "src/nfl_dfs/inference/sis_pass_tail_shadow.py",
        "first_week": 5,
        "last_week": 18,
        "floor_weeks": None,
        "schedulers": [
            "s-shadow-sis-pass-tail-paired",
            "s-tabpfn-sis-pass-tail-control", "s-tabpfn-sis-pass-tail-treatment",
        ],
        "require_env": None,
        "note": "NO FROZEN GATE DOCUMENT FOUND. Week 5 comes from the last-four-weeks "
                "context in the module. Before week 5: either write the gate and declare "
                "its policy contract, or move these schedulers to DORMANT with a reason.",
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
    "s-shadow-cbwu-oi-paired-early": "ENABLED and running; ownership-inclusive paired shadow.",
    "s-shadow-cbwu-oi-paired-late": "ENABLED and running; ownership-inclusive paired shadow.",
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


def scheduler_target(name: str) -> str:
    uri = sh(["gcloud", "scheduler", "jobs", "describe", name, "--project", PROJECT,
              "--location", LOCATION, "--format", "value(httpTarget.uri)"])
    return uri.split("/jobs/")[-1].replace(":run", "") if "/jobs/" in uri else ""


def audit(week: int) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    live = schedulers()

    for gate, spec in GATES.items():
        first, last = spec["first_week"], spec["last_week"]
        active = first <= week <= last
        upcoming = first - LOOKAHEAD_WEEKS <= week < first
        if not (active or upcoming):
            notes.append(f"{gate}: dormant this week (grades weeks {first}-{last}).")
            continue
        when = "GRADED THIS WEEK" if active else f"first graded week is {first}"
        paused = [s for s in spec["schedulers"]
                  if live.get(s, {}).get("state", "MISSING") != "ENABLED"]
        if paused:
            msg = (f"{gate}: {when}, but these are not ENABLED: "
                   + ", ".join(f"{s}({live.get(s, {}).get('state', 'MISSING')})" for s in paused)
                   + f"  [gate: {spec['doc']}]")
            (errors if active else warnings).append(msg)
        want = spec["require_env"]
        targets = {scheduler_target(s) for s in spec["schedulers"]}
        for job in sorted(t for t in targets if t):
            env = job_env(job)
            if want is None:
                warnings.append(f"{gate}: job {job} has NO declared policy contract in this "
                                f"registry; rule on it before week {first}. Current env of "
                                f"interest: { {k: v for k, v in env.items() if k in ('N_BOOM', 'N_LEV')} }")
                continue
            bad = {k: env.get(k, "<unset>") for k, v in want.items() if env.get(k) != v}
            if bad:
                errors.append(f"{gate}: job {job} contradicts the declared policy "
                              f"{want} -- found {bad}. Resuming it would burn a graded week "
                              f"on a policy we do not run.")

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
