#!/usr/bin/env python3
"""Build or verify the unadjudicated winner-registry-v2 artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from nfl_dfs.research.winner_registry_v2 import (
    adjudication_receipt_template,
    build_candidate_ledger,
    canonical_json_bytes,
    target_contest_policy_template,
    validate_candidate_ledger,
    validate_target_contest_policy,
    verify_source_files,
)


DEFAULT_LEDGER = Path(
    "reports/winner-registry/winner-registry-v2-candidate-ledger.json"
)
DEFAULT_POLICY_TEMPLATE = Path(
    "reports/winner-registry/"
    "winner-registry-v2-target-contest-policy.template.json"
)
DEFAULT_RECEIPT_TEMPLATE = Path(
    "reports/winner-registry/"
    "winner-registry-v2-adjudication-receipt.template.json"
)


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _write_create_or_exact(path: Path, value: Any) -> str:
    payload = _pretty_json_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise SystemExit(
                f"refusing to overwrite a different registry-v2 artifact: {path}"
            )
        return "verified-existing"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return "created"


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise SystemExit(f"expected one JSON object: {path}")
    return value


def _resolve(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def _check_exact(path: Path, expected: Any) -> None:
    actual = _load_json(path)
    if canonical_json_bytes(actual) != canonical_json_bytes(expected):
        raise SystemExit(f"registry-v2 artifact differs from source rebuild: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument(
        "--policy-template", type=Path, default=DEFAULT_POLICY_TEMPLATE
    )
    parser.add_argument(
        "--receipt-template", type=Path, default=DEFAULT_RECEIPT_TEMPLATE
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and require all committed artifacts to match",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    ledger_path = _resolve(root, args.ledger)
    policy_path = _resolve(root, args.policy_template)
    receipt_path = _resolve(root, args.receipt_template)

    ledger = build_candidate_ledger(root)
    policy = target_contest_policy_template()
    receipt = adjudication_receipt_template()
    validate_candidate_ledger(ledger)
    verify_source_files(ledger, root)
    validate_target_contest_policy(policy, require_frozen=False)

    if args.check:
        for path, expected in (
            (ledger_path, ledger),
            (policy_path, policy),
            (receipt_path, receipt),
        ):
            _check_exact(path, expected)
        result = "verified"
    else:
        states = [
            _write_create_or_exact(path, value)
            for path, value in (
                (ledger_path, ledger),
                (policy_path, policy),
                (receipt_path, receipt),
            )
        ]
        result = ",".join(states)

    print(
        json.dumps(
            {
                "result": result,
                "ledger": str(ledger_path),
                "ledger_sha256": ledger["ledger_sha256"],
                "source_artifact_count": ledger["source_artifact_count"],
                "observation_count": ledger["observation_count"],
                "official_target_score_count": ledger[
                    "official_target_score_count"
                ],
                "registry_status": ledger["registry_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
