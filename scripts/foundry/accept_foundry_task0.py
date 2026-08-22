"""Independent task-0 acceptance gate for the Foundry v6 fan-out.

The v5 design gated tasks 1..53 on science equivalence against the accepted
v4 task-0 artifact. The v4 producer failed terminally on 2026-08-22 (CBC
integer-infeasibility solution headers were classified ERROR), its launch
authority is consumed, and no v4 artifact exists — that baseline is
permanently dead. This gate replaces it with independent evidence that does
not require any prior run:

  1. Exact-identity reopen of the accepted task-0 carrier and all seven
     per-arm variant results (every structural law in
     corpus_parametric_snapshot applies, fail-closed).
  2. Full-matrix solver census: every arm must record scheduled=attempted=
     optimal=1000 visits with 1000 recorded rosters — the exact invariant
     the v4 failure violated (6,363 ERROR cells).
  3. The driver's verifier-accepted receipt must record accepted=true and
     partial_result=false (the independent verifier replays MPS semantics
     and proofs from the published evidence).
  4. Cross-arm slate/schedule/source identity (enforced by the reader) and
     per-arm selected_entries consistency.

On PASS (and only on PASS) writes the driver fan-out gate file
task0-acceptance-pass.json (create-once). Read-only against GCS; no
realized outcome is read; no cloud object is written.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    GoogleCloudObjectStore,
    ObjectIdentity,
)
from nfl_dfs.research.corpus_parametric_snapshot import (
    CorpusParametricSnapshotError,
    canonical_json_bytes,
    extract_task_science,
    normalize_object_identity,
    read_task_variant_results,
)

EXPECTED_VISITS = 1000
EXPECTED_ARMS = 7
GATE_NAME = "task0-independent-acceptance"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    for suffix in ("uri", "generation", "sha256", "bytes"):
        value.add_argument(
            f"--carrier-{suffix}", required=True,
            **({"type": int} if suffix == "bytes" else {}),
        )
    value.add_argument(
        "--verifier-accepted-receipt", required=True, type=Path,
        help="driver receipt tasks/000-verifier-accepted.json",
    )
    value.add_argument("--project", default="nfl-predictions-503414")
    value.add_argument(
        "--receipt-output", required=True, type=Path,
        help="create-once local path for the full acceptance receipt",
    )
    value.add_argument(
        "--pass-gate-output", required=True, type=Path,
        help=(
            "create-once local path written ONLY on PASS; this is the "
            "driver fan-out gate file (task0-acceptance-pass.json)"
        ),
    )
    return value


def _census(arms: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    defects: list[str] = []
    for ordinal, arm in enumerate(arms):
        coverage = arm["coverage"]
        row = {
            "ordinal": ordinal,
            "parameter_set_id": arm["profile"]["parameter_set_id"],
            "scheduled_visits": coverage["scheduled_visits"],
            "attempted_visits": coverage["attempted_visits"],
            "optimal_visits": coverage["optimal_visits"],
            "unique_candidates": coverage["unique_candidates"],
            "selected_entries": coverage["selected_entries"],
            "visit_roster_rows": len(arm["visit_rosters"]),
        }
        rows.append(row)
        for field in ("scheduled_visits", "attempted_visits", "optimal_visits"):
            if row[field] != EXPECTED_VISITS:
                defects.append(f"arm {ordinal} {field}={row[field]}")
        if row["visit_roster_rows"] != EXPECTED_VISITS:
            defects.append(
                f"arm {ordinal} visit_roster_rows={row['visit_roster_rows']}"
            )
        if any(not roster for roster in arm["visit_rosters"]):
            defects.append(f"arm {ordinal} has an empty visit roster")
        if row["selected_entries"] != len(arm["selected_rosters"]):
            defects.append(f"arm {ordinal} selected_entries differ from rosters")
        if row["selected_entries"] <= 0:
            defects.append(f"arm {ordinal} selected no entries")
        if row["unique_candidates"] != len(arm["unique_rosters"]):
            defects.append(f"arm {ordinal} unique_candidates differ from rosters")
    return rows, defects


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    for path in (args.receipt_output, args.pass_gate_output):
        if path.exists() or path.is_symlink():
            print(f"refused: output already exists: {path}", file=sys.stderr)
            return 2
    try:
        accepted = json.loads(args.verifier_accepted_receipt.read_bytes())
    except (OSError, ValueError) as exc:
        print(f"refused: verifier receipt unreadable: {exc}", file=sys.stderr)
        return 2
    verifier_ok = (
        accepted.get("accepted") is True
        and accepted.get("partial_result") is False
    )
    try:
        identity = normalize_object_identity({
            "uri": args.carrier_uri,
            "generation": args.carrier_generation,
            "sha256": args.carrier_sha256,
            "bytes": args.carrier_bytes,
        }, label="carrier")
        store = GoogleCloudObjectStore(project=args.project)

        def read_exact(pinned: dict[str, object]) -> bytes:
            return store.read_exact(ObjectIdentity(
                uri=str(pinned["uri"]),
                generation=str(pinned["generation"]),
                sha256=str(pinned["sha256"]),
                bytes=int(pinned["bytes"]),
            ))

        _, variants = read_task_variant_results(
            read_exact(identity),
            carrier_identity=identity,
            read_exact=read_exact,
        )
        science = extract_task_science(variants)
    except CorpusParametricSnapshotError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    arms = science["arms"]
    census, defects = _census(arms)
    if len(arms) != EXPECTED_ARMS:
        defects.append(f"arm count {len(arms)} != {EXPECTED_ARMS}")
    if not verifier_ok:
        defects.append("verifier receipt does not record full acceptance")
    passed = not defects
    receipt = {
        "gate": GATE_NAME,
        "passed": passed,
        "solver_all_optimal": all(
            row["optimal_visits"] == EXPECTED_VISITS for row in census
        ) and len(census) == EXPECTED_ARMS,
        "verifier_accepted": verifier_ok,
        "carrier_identity": identity,
        "science_projection_sha256": science["science_projection_sha256"],
        "arm_census": census,
        "defects": defects,
        "uses_realized_outcomes": False,
    }
    raw = canonical_json_bytes(receipt) + b"\n"
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_bytes(raw)
    if passed:
        args.pass_gate_output.parent.mkdir(parents=True, exist_ok=True)
        args.pass_gate_output.write_bytes(raw)
        print("task-0 independent acceptance PASS")
        return 0
    print(
        "task-0 independent acceptance FAILED: " + "; ".join(defects),
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
