"""Compare two accepted corpus-parametric tasks on science content only.

Reads two generation-pinned carrier objects (producer worker completion or
closed task result), reopens each side's seven per-arm variant results,
projects the image-invariant science subset, and writes the machine-readable
equivalence receipt. On PASS (and only on PASS) it also writes the driver's
fan-out gate file. Exit codes: 0 equivalent, 3 not equivalent, 2 refused.

Read-only against GCS; no realized outcome is read; no cloud object is
written. The module's freeze gate applies: the first production use must be
an outcome-blind smoke against the real accepted v4 task-0 artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    GoogleCloudObjectStore,
    ObjectIdentity,
)
from nfl_dfs.research.corpus_parametric_snapshot import (
    CorpusParametricSnapshotError,
    canonical_json_bytes,
    compare_task_science,
    extract_task_science,
    normalize_object_identity,
    read_task_variant_results,
)


def _identity_arguments(
    parser: argparse.ArgumentParser, prefix: str
) -> None:
    parser.add_argument(f"--{prefix}-uri", required=True)
    parser.add_argument(f"--{prefix}-generation", required=True)
    parser.add_argument(f"--{prefix}-sha256", required=True)
    parser.add_argument(f"--{prefix}-bytes", required=True, type=int)


def _identity(namespace: argparse.Namespace, prefix: str) -> dict[str, object]:
    key = prefix.replace("-", "_")
    return normalize_object_identity({
        "uri": getattr(namespace, f"{key}_uri"),
        "generation": getattr(namespace, f"{key}_generation"),
        "sha256": getattr(namespace, f"{key}_sha256"),
        "bytes": getattr(namespace, f"{key}_bytes"),
    }, label=prefix)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    _identity_arguments(value, "baseline-carrier")
    _identity_arguments(value, "challenger-carrier")
    value.add_argument("--baseline-label", required=True)
    value.add_argument("--challenger-label", required=True)
    value.add_argument("--project", default="nfl-predictions-503414")
    value.add_argument(
        "--receipt-output", required=True, type=Path,
        help="create-once local path for the full equivalence receipt",
    )
    value.add_argument(
        "--pass-gate-output", required=True, type=Path,
        help=(
            "create-once local path written ONLY on PASS; this is the "
            "driver fan-out gate file (task0-equivalence-pass.json)"
        ),
    )
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    for path in (args.receipt_output, args.pass_gate_output):
        if path.exists() or path.is_symlink():
            print(f"refused: output already exists: {path}", file=sys.stderr)
            return 2
    try:
        store = GoogleCloudObjectStore(project=args.project)

        def read_exact(identity: dict[str, object]) -> bytes:
            return store.read_exact(ObjectIdentity(
                uri=str(identity["uri"]),
                generation=str(identity["generation"]),
                sha256=str(identity["sha256"]),
                bytes=int(identity["bytes"]),
            ))

        projections = {}
        for prefix, label in (
            ("baseline-carrier", args.baseline_label),
            ("challenger-carrier", args.challenger_label),
        ):
            identity = _identity(args, prefix)
            _, variants = read_task_variant_results(
                read_exact(identity),
                carrier_identity=identity,
                read_exact=read_exact,
            )
            projections[label] = extract_task_science(variants)
        receipt = compare_task_science(
            projections[args.baseline_label],
            projections[args.challenger_label],
            baseline_label=args.baseline_label,
            challenger_label=args.challenger_label,
        )
    except CorpusParametricSnapshotError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    raw = canonical_json_bytes(receipt) + b"\n"
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_bytes(raw)
    if receipt["equivalent"] is True:
        args.pass_gate_output.parent.mkdir(parents=True, exist_ok=True)
        args.pass_gate_output.write_bytes(raw)
        print("science-equivalence PASS")
        return 0
    print(
        "science-equivalence FAIL: "
        f"{len(receipt['differing_fields'])} differing fields",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
