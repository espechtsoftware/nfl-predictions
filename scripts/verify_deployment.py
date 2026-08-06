"""Deployment contract check: does the LIVE lineup-generation config
match the adopted default?

Why this exists: `check-freshness` resolves configuration inside its
OWN process, so if the app alone were deployed with N_CE=0 the
freshness job would still see code defaults (12/28) and pass. The
claimed "an accidental app override trips the alert" protection did
not exist. This reads the Cloud Run specs for the two live
lineup-generation paths and fails if either departs from 12/28.

  python scripts/verify_deployment.py            # check, exit 1 on drift
  python scripts/verify_deployment.py --json     # machine-readable

Run it as a deploy gate and/or a scheduled job; a non-zero exit trips
the existing failed-execution alert.
"""
import argparse
import json
import subprocess
import sys

sys.path.insert(0, "src")
from nfl_dfs.backtest.engine import (  # noqa: E402
    DEFAULT_N_BOOM, DEFAULT_N_CE, resolve_generation_budget)

REGION = "us-central1"
# the two paths that actually BUILD lineups
TARGETS = (("service", "nfl-dfs-app"), ("job", "project-slate"))


def _env_of(kind: str, name: str) -> dict[str, str] | None:
    if kind == "service":
        fmt = "value(spec.template.spec.containers[0].env)"
        cmd = ["gcloud", "run", "services", "describe", name,
               "--region", REGION, "--format", fmt]
    else:
        fmt = ("value(spec.template.spec.template.spec.containers[0].env)")
        cmd = ["gcloud", "run", "jobs", "describe", name,
               "--region", REGION, "--format", fmt]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=120)
    except Exception as exc:  # pragma: no cover - network path
        print(f"  {name}: describe failed ({exc})")
        return None
    if out.returncode != 0:
        print(f"  {name}: describe failed: {out.stderr.strip()[:160]}")
        return None
    env: dict[str, str] = {}
    for part in out.stdout.split(";"):
        part = part.strip()
        if "'name':" in part and "'value':" in part:
            try:
                k = part.split("'name':")[1].split("'")[1]
                v = part.split("'value':")[1].split("'")[1]
                env[k] = v
            except IndexError:
                continue
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    report, failures = [], []
    for kind, name in TARGETS:
        env = _env_of(kind, name)
        if env is None:
            failures.append(f"{name}: could not read deployment spec")
            continue
        ce, epi, boom = resolve_generation_budget(env=env)
        # FULL contract, not just (ce, boom): N_EPISTEMIC=1 alongside
        # 12/28 would otherwise pass while producing 41 slots. Research
        # knobs must never appear on a production deployment either.
        forbidden = {k: env[k] for k in ("GEN_POOL_CAP", "GEN_POOL_CAP_MAP",
                                         "GEN_TOTAL_BUDGET") if k in env}
        problems = []
        if ce != DEFAULT_N_CE:
            problems.append(f"N_CE={ce} (want {DEFAULT_N_CE})")
        if epi != 0:
            problems.append(f"N_EPISTEMIC={epi} (want 0)")
        if boom != DEFAULT_N_BOOM:
            problems.append(f"N_BOOM={boom} (want {DEFAULT_N_BOOM})")
        if ce + epi + boom != DEFAULT_N_CE + DEFAULT_N_BOOM:
            problems.append(f"total={ce + epi + boom} (want 40)")
        if forbidden:
            problems.append(f"research overrides present: {forbidden}")
        ok = not problems
        row = {"target": name, "kind": kind, "n_ce": ce,
               "n_epistemic": epi, "n_boom": boom, "total": ce + epi + boom,
               "ce_seed": int(env.get("CE_SEED", "1701") or 1701),
               "matches_adopted": ok,
               "overrides": {k: v for k, v in env.items()
                             if k in ("N_CE", "N_EPISTEMIC", "N_BOOM",
                                      "CE_SEED", "GEN_TOTAL_BUDGET",
                                      "GEN_POOL_CAP")}}
        report.append(row)
        row["problems"] = problems
        if not ok:
            failures.append(f"{name}: " + "; ".join(problems))

    if a.json:
        print(json.dumps({"targets": report, "failures": failures}, indent=2))
    else:
        for r in report:
            state = "OK " if r["matches_adopted"] else "DRIFT"
            print(f"  [{state}] {r['target']:<16} CE {r['n_ce']:>2} / "
                  f"boom {r['n_boom']:>2} / total {r['total']:>2}"
                  + (f"  overrides={r['overrides']}" if r["overrides"] else ""))
    if failures:
        print("\nDEPLOYMENT CONTRACT FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nDeployment contract OK — both lineup paths on the adopted "
          f"{DEFAULT_N_CE}/{DEFAULT_N_BOOM} budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
