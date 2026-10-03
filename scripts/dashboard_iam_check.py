#!/usr/bin/env python3
"""Fail if a Cloud Run service is reachable without IAP (stdlib only).

    python3 scripts/dashboard_iam_check.py POLICY.json [SERVICE.json]

POLICY.json is `gcloud run services get-iam-policy SERVICE --format=json`;
SERVICE.json (optional) is `gcloud run services describe SERVICE --format=json`.
Exit 1, naming each problem, when the policy binds allUsers or
allAuthenticatedUsers, or the service has the invoker IAM check disabled.
The dashboard's deploy script runs this after every update and prints the
rollback command on failure.
"""
from __future__ import annotations

import json
import sys

PUBLIC_MEMBERS = ("allUsers", "allAuthenticatedUsers")


def public_bindings(policy: dict) -> list[str]:
    out = []
    for b in policy.get("bindings") or []:
        for m in b.get("members") or []:
            if m in PUBLIC_MEMBERS:
                out.append(f"{b.get('role', '?')} -> {m}")
    return out


def service_problems(service: dict) -> list[str]:
    ann = (service.get("metadata") or {}).get("annotations") or {}
    probs = []
    if str(ann.get("run.googleapis.com/invoker-iam-disabled", "")).lower() == "true":
        probs.append("invoker IAM check is disabled (run.googleapis.com/invoker-iam-disabled=true)")
    return probs


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    policy = json.loads(open(argv[0]).read() or "{}")
    problems = [f"public IAM binding: {p}" for p in public_bindings(policy)]
    if len(argv) > 1:
        problems += service_problems(json.loads(open(argv[1]).read() or "{}"))
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if not problems:
        print("ok: no public invoker binding; invoker IAM check enabled")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
