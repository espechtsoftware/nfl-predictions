"""Verify the deployed Week 1 classic-policy contract.

The app receives its roster-changing environment as an immutable request-local
mapping from ``production_policy.py``. Cloud Run therefore must not inject a
second research policy. The projection and registry jobs have smaller exact
contracts, while the role-union shadow must expose the historical arm's full
configuration for prospective attribution.

Usage::

    python scripts/verify_deployment.py
    python scripts/verify_deployment.py --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

sys.path.insert(0, "src")
from nfl_dfs.inference.production_policy import (  # noqa: E402
    ADOPTED_CLASSIC_POLICY,
)
from nfl_dfs.inference.route_share_shadow import (  # noqa: E402
    ROUTE_FEATURES as ROUTE_FEATURE_NAMES,
)
from nfl_dfs.inference.prospective_shadow import (  # noqa: E402
    CBWU_OI_CONTRACT,
    CBWU_OI_CONTRACT_ENV,
)
from nfl_dfs.inference.tail_shadow import (  # noqa: E402
    ROUTE_SHARE_COMPANION_V1,
    route_share_job_environment,
)

REGION = "us-central1"
ROLE_FEATURES = ADOPTED_CLASSIC_POLICY.role_features
ROUTE_FEATURES = ",".join(ROUTE_FEATURE_NAMES)

# Values that may never be injected into the app service. The adopted mapping
# owns all of them per request, including the labeled CE-only fallback.
APP_FORBIDDEN = {
    "GEN_POOL_CAP", "GEN_POOL_CAP_MAP", "GEN_TOTAL_BUDGET",
    "N_CE", "N_EPISTEMIC", "N_BOOM", "N_GUMBEL", "N_LEV",
    "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
    "OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES",
    "REPLACEMENT_SLOTS", "SELECT_OBJ", "SELECT_LSE", "SELECT_LADDER",
}

TARGETS = (
    ("service", "nfl-dfs-app", {}),
    ("job", "project-slate", {
        "MODEL_ENSEMBLE": "1", "MODEL_REGISTRY_VARIANT": "tail_k1",
        "GAME_SIM_MODE": "possession", "BLEND_MODEL_WEIGHT": "0.45",
    }),
    ("job", "train-weekly-k1", {
        "MODEL_ENSEMBLE": "1", "MODEL_REGISTRY_VARIANT": "tail_k1",
    }),
    ("job", "train-weekly-k1-role", {
        "MODEL_ENSEMBLE": "1", "MODEL_REGISTRY_VARIANT": "tail_k1_role",
        "EXTRA_FEATURES": ROLE_FEATURES,
    }),
    ("job", "train-weekly-k1-route", {
        "MODEL_ENSEMBLE": "1", "MODEL_REGISTRY_VARIANT": "tail_k1_route",
        "EXTRA_FEATURES": ROUTE_FEATURES,
    }),
    ("job", "train-weekly-k1-route-role", {
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1_route_role",
        "EXTRA_FEATURES": f"{ROLE_FEATURES},{ROUTE_FEATURES}",
    }),
    # 2026-10-05 (O-25): the Route Share pair runs under ONE declared contract,
    # companion v1, derived from production_policy by tail_shadow. This list
    # used to pin the frozen August N_BOOM=28 set beside jobs carrying 160.
    ("job", "shadow-k1-roleunion", {
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        **route_share_job_environment(ROUTE_SHARE_COMPANION_V1),
    }),
    ("job", "shadow-k1-route-roleunion", {
        "MODEL_REGISTRY_VARIANT": "tail_k1_route",
        **route_share_job_environment(ROUTE_SHARE_COMPANION_V1),
    }),
    # 2026-10-05 (O-27): the CBWU-OI paired shadow builds its environment in
    # code (prospective_shadow.check_cbwu_oi_contract pins the frozen
    # settings); the job must only declare which contract it collects for.
    ("job", "shadow-cbwu-oi-paired", {
        CBWU_OI_CONTRACT_ENV: CBWU_OI_CONTRACT,
    }),
)


def _env_of(kind: str, name: str) -> dict[str, str] | None:
    if kind == "service":
        cmd = ["gcloud", "run", "services", "describe", name,
               "--region", REGION, "--format", "json"]
    else:
        cmd = ["gcloud", "run", "jobs", "describe", name,
               "--region", REGION, "--format", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:  # pragma: no cover - network path
        print(f"  {name}: describe failed ({exc})")
        return None
    if out.returncode != 0:
        print(f"  {name}: describe failed: {out.stderr.strip()[:160]}")
        return None
    try:
        document = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        print(f"  {name}: deployment env was not valid JSON")
        return None
    if kind == "service":
        rows = document["spec"]["template"]["spec"]["containers"][0].get(
            "env", [])
    else:
        rows = document["spec"]["template"]["spec"]["template"]["spec"][
            "containers"][0].get("env", [])
    return {
        str(row.get("name")): str(row.get("value", ""))
        for row in rows if row.get("name")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report: list[dict] = []
    failures: list[str] = []
    for kind, name, expected in TARGETS:
        env = _env_of(kind, name)
        if env is None:
            failures.append(f"{name}: could not read deployment spec")
            continue
        problems = [
            f"{key}={env.get(key)!r} (want {value!r})"
            for key, value in expected.items() if env.get(key) != value
        ]
        if kind == "service":
            injected = {key: env[key] for key in APP_FORBIDDEN if key in env}
            if injected:
                problems.append(f"app research overrides present: {injected}")
        row = {
            "target": name, "kind": kind, "matches_adopted": not problems,
            "expected": expected, "problems": problems,
        }
        report.append(row)
        if problems:
            failures.append(f"{name}: " + "; ".join(problems))

    payload = {
        "policy_id": ADOPTED_CLASSIC_POLICY.policy_id,
        "source_panel": ADOPTED_CLASSIC_POLICY.source_panel,
        "targets": report, "failures": failures,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Adopted policy: {payload['policy_id']}")
        for row in report:
            state = "OK" if row["matches_adopted"] else "DRIFT"
            print(f"  [{state:<5}] {row['target']}")
            for problem in row["problems"]:
                print(f"          {problem}")
    if failures:
        return 1
    print("Deployment contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
