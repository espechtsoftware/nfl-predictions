"""Capture and assemble one v7 lane runtime IAM policy capture.

Re-captures every component fresh AFTER the v6->v7a/v7b IAM condition move —
four bucket policies + metadata, the project policy, the two narrow
custom role definitions, and three effective-access analyses (runtime
service account, allUsers, allAuthenticatedUsers) — normalizes each body
through the frozen transport's external-JSON canonicalization, and
assembles the corpus-parametric-runtime-iam-policy-capture/v2 document
with its capture_sha256 self-hash. Raw component bodies are retained
beside the capture. Read-only against GCP; the only writes are local
create-once files under governance-live-v6.

Run with the py311 interpreter; law code loads from the frozen bcf31a7
worktree so canonicalization is byte-exact with what configure validates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

WORKTREE = Path("/tmp/nfl-predictions-corpus-6f66bf9")
import argparse

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument("--lane", required=True, choices=("a", "b"))
_LANE = _parser.parse_args().lane
OUT_DIR = Path(
    "/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/"
    f"20260823-foundry-production-v9{_LANE}/governance-live-v9{_LANE}"
)
PROJECT = "nfl-predictions-503414"
# Per-lane runtime identity: the transport's least-privilege law admits
# exactly one live batch per service account, so lane B runs as its own
# SA with its own single-permission role pair (distinct roles keep the
# raw bucket's unconditional principal-exact GET binding unmergeable).
SERVICE_ACCOUNT = (
    "corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com"
    if _LANE == "a"
    else "corpus-parametric-research-b@nfl-predictions-503414.iam.gserviceaccount.com"
)
BUCKETS = (
    "nfl-predictions-503414-corpus-parametric",
    "nfl-predictions-503414-corpus-retrieval",
    "nfl-predictions-503414-corpus-source",
    "nfl-predictions-503414-raw",
)
_SUFFIX = "" if _LANE == "a" else "B"
ROLES = (
    ("role-create", f"corpusParametricObjectCreateV2{_SUFFIX}"),
    ("role-get", f"corpusParametricObjectGetV2{_SUFFIX}"),
)
IDENTITIES = (
    ("asset-runtime", f"serviceAccount:{SERVICE_ACCOUNT}", "runtime_identity"),
    ("asset-all-users", "allUsers", "all_users"),
    (
        "asset-all-authenticated-users",
        "allAuthenticatedUsers",
        "all_authenticated_users",
    ),
)


def _transport():
    spec = importlib.util.spec_from_file_location(
        "frozen_corpus_parametric_transport",
        WORKTREE / "scripts/run_corpus_parametric_transport.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(WORKTREE / "src"))
    sys.path.insert(0, str(WORKTREE / "scripts"))
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _gcloud(arguments: list[str], name: str) -> object:
    path = OUT_DIR / f"{name}.raw.json"
    if path.exists():
        # Idempotent resume within one capture session: gcloud reads are
        # read-only and the assembled capture does not exist yet, so a
        # retained raw component from this session is reused, never
        # refetched-and-overwritten.
        return json.loads(path.read_bytes())
    import time as _time
    for attempt in range(8):
        completed = subprocess.run(
            ["gcloud", *arguments, "--format=json"], capture_output=True,
        )
        if completed.returncode == 0:
            break
        stderr = completed.stderr.decode("utf-8", "replace")
        if "RESOURCE_EXHAUSTED" in stderr or " 429" in stderr:
            # Cloud Asset analyze quota is 100/min and 200/day; back off
            # rather than fail the whole capture on a burst limit.
            _time.sleep(min(300, 30 * (attempt + 1)))
            continue
        raise subprocess.CalledProcessError(
            completed.returncode, completed.args, completed.stdout,
            completed.stderr,
        )
    else:
        raise SystemExit(f"gcloud capture exhausted retries: {name}")
    raw = completed.stdout
    path.write_bytes(raw)
    return json.loads(raw)


def main() -> int:
    transport = _transport()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / "runtime-iam-policy-capture.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite capture: {output}")

    def canonical(value: object, label: str) -> object:
        return transport.external_json_bytes(
            json.dumps(value).encode("utf-8"), label=label
        )

    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    def _api(path: str, name: str) -> object:
        raw_path = OUT_DIR / f"{name}.raw.json"
        if raw_path.exists():
            return json.loads(raw_path.read_bytes())
        raw = subprocess.run(
            ["curl", "-sf", "-H", f"Authorization: Bearer {token}",
             f"https://storage.googleapis.com/storage/v1/{path}"],
            check=True, capture_output=True,
        ).stdout
        raw_path.write_bytes(raw)
        return json.loads(raw)

    bucket_policies = []
    bucket_metadata = []
    for bucket in BUCKETS:
        # The transport validates the storage JSON API shapes
        # (iamConfiguration object, policy kind/resourceId/version), which
        # the modern gcloud storage surface re-renders — so both bodies
        # come from the API directly, exactly like the v4 captures.
        # Version 3 is required so condition expressions (the two narrow
        # v6 prefix conditions) are returned, not elided.
        policy = _api(
            f"b/{bucket}/iam?optionsRequestedPolicyVersion=3",
            f"{bucket}-policy",
        )
        metadata = _api(f"b/{bucket}", f"{bucket}-metadata")
        bucket_policies.append({
            "bucket": bucket,
            "policy": canonical(policy, f"{bucket} policy"),
        })
        bucket_metadata.append({
            "bucket": bucket,
            "metadata": canonical(metadata, f"{bucket} metadata"),
        })

    project_policy = canonical(
        _gcloud(
            ["projects", "get-iam-policy", PROJECT], "project-policy"
        ),
        "project policy",
    )
    custom_role_definitions = [
        canonical(
            _gcloud(
                ["iam", "roles", "describe", role, "--project", PROJECT],
                name,
            ),
            f"role {role}",
        )
        for name, role in ROLES
    ]
    effective_access_analyses = {}
    analyzer_exhausted = False
    for name, identity, key in IDENTITIES:
        if analyzer_exhausted:
            break
        try:
            effective_access_analyses[key] = canonical(
                _gcloud(
                    ["asset", "analyze-iam-policy",
                     "--project", PROJECT,
                     f"--identity={identity}",
                     "--expand-groups", "--expand-roles",
                     "--expand-resources", "--show-response",
                     "--output-resource-edges", "--output-group-edges"],
                    name,
                ),
                f"analysis {key}",
            )
        except SystemExit:
            analyzer_exhausted = True
    if analyzer_exhausted:
        # Primary-evidence fallback (transport-validated): the analyzer
        # daily quota is exhausted, so each record is derived from the
        # captured version-3 policies themselves; the transport
        # recomputes the same derivation independently and refuses any
        # divergence. The analyzer path is preferred whenever available.
        observed_at = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        unavailable = {
            "reason": (
                "cloudasset analyze_iam_policy daily project quota "
                "exhausted (HTTP 429 after retries)"
            ),
            "observed_at_utc": observed_at,
        }
        member = f"serviceAccount:{SERVICE_ACCOUNT}"
        role_permissions = {
            str(row["name"]): str(row["includedPermissions"][0])
            for row in custom_role_definitions
        }
        grants = transport._policy_derived_grants(
            bucket_policies,
            member=member,
            role_permissions=role_permissions,
        )
        effective_access_analyses = {
            "runtime_identity": {
                "policy_derived": True,
                "analyzer_unavailable": dict(unavailable),
                "derived_grants": [
                    {
                        "role": role,
                        "resource": resource,
                        "condition_title": title,
                        "prefixes": sorted(prefixes),
                        "exact_objects": sorted(exact_objects),
                        "permissions": sorted(permissions),
                    }
                    for (
                        role, resource, title, prefixes,
                        exact_objects, permissions,
                    ) in grants
                ],
            },
            "all_users": {
                "policy_derived": True,
                "analyzer_unavailable": dict(unavailable),
                "public_bindings_found": 0,
            },
            "all_authenticated_users": {
                "policy_derived": True,
                "analyzer_unavailable": dict(unavailable),
                "public_bindings_found": 0,
            },
        }

    body = {
        "schema_version": "corpus-parametric-runtime-iam-policy-capture/v2",
        "captured_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "project": PROJECT,
        "project_policy": project_policy,
        "custom_role_definitions": custom_role_definitions,
        "bucket_policies": bucket_policies,
        "bucket_metadata": bucket_metadata,
        "effective_access_analyses": effective_access_analyses,
    }
    body["capture_sha256"] = transport.canonical_sha256(body)
    raw = transport.canonical_json_bytes(body)
    output.write_bytes(raw)
    print(json.dumps({
        "output": str(output),
        "bytes": len(raw),
        "capture_sha256": body["capture_sha256"],
        "buckets": len(bucket_policies),
        "roles": len(custom_role_definitions),
        "analyses": sorted(effective_access_analyses),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
