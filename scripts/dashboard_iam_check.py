#!/usr/bin/env python3
"""Fail unless a Cloud Run service is IAP-only and serving its latest
revision (stdlib only, so it runs without the project venv).

    python3 scripts/dashboard_iam_check.py --service SERVICE.json [--policy POLICY.json] [--traffic]

SERVICE.json is `gcloud run services describe SERVICE --format=json`;
POLICY.json is `gcloud run services get-iam-policy SERVICE --format=json`.
Problems (each printed, exit 1):
  * the service annotation run.googleapis.com/iap-enabled is not "true";
  * the invoker IAM check is disabled (run.googleapis.com/invoker-iam-disabled);
  * the policy binds allUsers or allAuthenticatedUsers;
  * with --traffic: status.traffic does not send 100% to
    status.latestReadyRevisionName (a rollback pins traffic to a revision,
    and a later update would then not be served).
It always prints what it found. scripts/deploy_dashboard.sh runs it before
the update (service only) and after (all three), printing the rollback on
failure.
"""
from __future__ import annotations

import argparse
import json
import sys

PUBLIC_MEMBERS = ("allUsers", "allAuthenticatedUsers")
IAP_ANNOTATION = "run.googleapis.com/iap-enabled"
INVOKER_DISABLED = "run.googleapis.com/invoker-iam-disabled"


def public_bindings(policy: dict) -> list[str]:
    out = []
    for b in policy.get("bindings") or []:
        for m in b.get("members") or []:
            if m in PUBLIC_MEMBERS:
                out.append(f"{b.get('role', '?')} -> {m}")
    return out


def _annotations(service: dict) -> dict:
    return (service.get("metadata") or {}).get("annotations") or {}


def service_problems(service: dict) -> list[str]:
    ann = _annotations(service)
    probs = []
    if str(ann.get(IAP_ANNOTATION, "")).lower() != "true":
        probs.append(f"IAP is not enabled ({IAP_ANNOTATION}={ann.get(IAP_ANNOTATION)!r}, expected 'true')")
    if str(ann.get(INVOKER_DISABLED, "")).lower() == "true":
        probs.append(f"invoker IAM check is disabled ({INVOKER_DISABLED}=true)")
    return probs


def traffic_summary(service: dict) -> tuple[str | None, list[tuple[str, int, bool]]]:
    status = service.get("status") or {}
    latest = status.get("latestReadyRevisionName")
    rows = [(t.get("revisionName") or ("<latest>" if t.get("latestRevision") else "?"),
             int(t.get("percent") or 0), bool(t.get("latestRevision")))
            for t in status.get("traffic") or []]
    return latest, rows


def traffic_problems(service: dict) -> list[str]:
    latest, rows = traffic_summary(service)
    if not latest:
        return ["status.latestReadyRevisionName is missing"]
    on_latest = sum(p for name, p, is_latest in rows if is_latest or name == latest)
    if on_latest != 100:
        return [f"traffic is not 100% on the latest ready revision {latest}: {rows}"]
    return []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--service", required=True)
    ap.add_argument("--policy")
    ap.add_argument("--traffic", action="store_true")
    a = ap.parse_args(argv)
    service = json.loads(open(a.service).read() or "{}")
    problems = service_problems(service)
    ann = _annotations(service)
    print(f"found: {IAP_ANNOTATION}={ann.get(IAP_ANNOTATION)!r} "
          f"{INVOKER_DISABLED}={ann.get(INVOKER_DISABLED)!r}")
    if a.policy:
        policy = json.loads(open(a.policy).read() or "{}")
        pub = public_bindings(policy)
        print(f"found: {len(policy.get('bindings') or [])} IAM binding(s), public: {pub or 'none'}")
        problems += [f"public IAM binding: {p}" for p in pub]
    if a.traffic:
        latest, rows = traffic_summary(service)
        print(f"found: latest ready revision {latest}; traffic {rows}")
        problems += traffic_problems(service)
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if not problems:
        print("ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
