"""Build a live-matchup capture seal from independently validated schema-1 runs (the Week-1 seal, automated).

Before the schema-2 capture (2026-09-23 merge) a week's three live matchup reports were captured by schema-1 runs,
often across several runs (a report whose schedule gate failed in one run passed in a later one).  The staging
loader accepts such a week only through a seal naming one validated member per report
(``ingest.fantasy_points_matchups_weekly.validate_seal``).  This module assembles that seal mechanically:

* scans ``<output_root>/*__2026-live-matchups-v1__week-WW`` schema-1 run manifests for the target week;
* a report record is a candidate only if its schedule gate passed, it was archived (``archive_uri``), it was
  retrieved strictly before the run's first kickoff, the run's kickoff and expected pairs equal the warehouse
  schedule authority, and the file on disk still has the recorded hash and byte count;
* per report the LATEST such candidate before kickoff is chosen;
* each member's GCS archive is re-read: its bytes must hash to the member's sha256, and its generation is pinned.

  python -m nfl_dfs.ops.fantasy_points_matchup_seal --output-root fantasy-points/automated --week 2 --out <seal.json>

It then audits the seal with the staging loader (no write).  A week with no valid candidate for some report fails
closed and names the report; it never widens a gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .fantasy_points_matchups import CAPTURE_ID, MATCHUPS


SEAL_STATUS = "COMPLETE_FROM_INDEPENDENTLY_VALIDATED_REPORTS"
SEASON = 2026
REPORTS = tuple(definition.key for definition in MATCHUPS)
ArchiveLookup = Callable[[str], tuple[str, str]]          # uri -> (sha256 of the stored bytes, generation)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gcs_lookup(uri: str) -> tuple[str, str]:
    from google.cloud import storage

    bucket, _, name = uri.removeprefix("gs://").partition("/")
    blob = storage.Client().bucket(bucket).get_blob(name)
    if blob is None:
        raise FileNotFoundError(uri)
    return hashlib.sha256(blob.download_as_bytes()).hexdigest(), str(blob.generation)


def candidates(
    output_root: str | Path,
    *,
    week: int,
    kickoff: pd.Timestamp,
    expected: set[tuple[str, str]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Valid schema-1 report records per report key, plus the reasons other records were excluded."""
    root = Path(output_root)
    found: dict[str, list[dict[str, Any]]] = {key: [] for key in REPORTS}
    excluded: list[str] = []
    for manifest_path in sorted(root.glob(f"*__{CAPTURE_ID}__week-{int(week):02d}/manifest.json")):
        run_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            excluded.append(f"{run_dir.name}: schema {manifest.get('schema_version')} (use the run dir directly)")
            continue
        if (manifest.get("capture_id") != CAPTURE_ID or manifest.get("target_week") != int(week)
                or manifest.get("target_season") != SEASON):
            excluded.append(f"{run_dir.name}: identity differs")
            continue
        run_kickoff = pd.Timestamp(manifest.get("first_kickoff_utc"))
        run_pairs = {tuple(pair) for pair in manifest.get("expected_schedule_pairs") or []}
        if run_kickoff != kickoff or run_pairs != expected:
            excluded.append(f"{run_dir.name}: kickoff/pairs differ from the schedule authority")
            continue
        for record in manifest.get("reports", []):
            key = record.get("key")
            label = f"{run_dir.name}/{key}"
            if key not in found:
                excluded.append(f"{label}: unknown report")
                continue
            if not (record.get("schedule_gate") or {}).get("passes"):
                excluded.append(f"{label}: schedule gate failed")
                continue
            if not record.get("archive_uri"):
                excluded.append(f"{label}: not archived")
                continue
            retrieved = pd.Timestamp(record.get("retrieved_at_utc"))
            if retrieved.tzinfo is None or retrieved >= kickoff:
                excluded.append(f"{label}: retrieved at/after first kickoff or without a timezone")
                continue
            path = run_dir / Path(str(record.get("path", ""))).name
            if not path.is_file() or _sha256(path) != record.get("sha256") or path.stat().st_size != int(
                    record.get("bytes", -1)):
                excluded.append(f"{label}: file missing or changed on disk")
                continue
            found[key].append({**record, "source_run_id": run_dir.name, "retrieved": retrieved})
    return found, excluded


def build_seal(
    output_root: str | Path,
    *,
    week: int,
    kickoff: pd.Timestamp,
    expected: set[tuple[str, str]],
    archive_lookup: ArchiveLookup = gcs_lookup,
    now: datetime | None = None,
) -> dict[str, Any]:
    found, excluded = candidates(output_root, week=week, kickoff=kickoff, expected=expected)
    if missing := [key for key in REPORTS if not found[key]]:
        raise ValueError(f"week {week}: no valid pre-kickoff capture for {missing}; excluded: {excluded}")
    members = []
    for key in REPORTS:
        chosen = max(found[key], key=lambda record: record["retrieved"])
        stored_sha, generation = archive_lookup(chosen["archive_uri"])
        if stored_sha != chosen["sha256"]:
            raise ValueError(f"{key}: archive {chosen['archive_uri']} bytes differ from the captured file")
        gate = chosen.get("schedule_gate") or {}
        members.append({
            "report": key,
            "source_run_id": chosen["source_run_id"],
            "source_code_commit": chosen.get("source_code_commit"),
            "retrieved_at_utc": chosen["retrieved_at_utc"],
            "source_url": chosen.get("source_url"),
            "source_rows": chosen.get("source_rows"),
            "normalized_observed_pairs": gate.get("observed_pairs"),
            "schedule_gate_passes": True,
            "source_seasons": chosen.get("source_seasons"),
            "source_regime": chosen.get("source_regime"),
            "sha256": chosen["sha256"],
            "bytes": int(chosen["bytes"]),
            "archive_uri": chosen["archive_uri"],
            "archive_generation": generation,
        })
    regimes = {member["source_regime"] for member in members}
    seasons = sorted({season for member in members for season in (member["source_seasons"] or [])})
    return {
        "schema_version": 1,
        "capture_id": CAPTURE_ID,
        "status": SEAL_STATUS,
        "sealed_at_utc": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_season": SEASON,
        "target_week": int(week),
        "first_kickoff_utc": kickoff.isoformat(),
        "source_seasons": seasons,
        "source_regime": regimes.pop() if len(regimes) == 1 else sorted(regimes),
        "schedule_contract": {
            "expected_directional_pairs": len(expected),
            "required_unexpected_pairs": [],
            "required_missing_pairs": [],
            "schedule_source": "nfl_raw.schedules",
        },
        "members": members,
        "excluded_records": excluded,
        "integrity": {
            "all_members_retrieved_before_first_kickoff": True,
            "all_members_source_regime_identical": len({m["source_regime"] for m in members}) == 1,
            "all_members_schedule_gate_passes": True,
            "all_members_hash_addressed_and_generation_pinned": True,
            "vendor_rows_rewritten": False,
            "failed_or_mismatched_exports_admitted": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fp-matchup-seal", description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--skip-audit", action="store_true", help="do not audit the seal with the staging loader")
    a = parser.parse_args(argv)
    from ..ingest import fantasy_points_matchups_weekly as loader
    from .fantasy_points_matchups import _schedule, expected_schedule_pairs, first_kickoff_utc

    schedule = _schedule(SEASON, a.week)
    seal = build_seal(a.output_root, week=a.week, kickoff=first_kickoff_utc(schedule),
                      expected=expected_schedule_pairs(schedule))
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; a seal is written once")
    a.out.write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: " + ", ".join(f"{m['report']}<-{m['source_run_id']}" for m in seal["members"]))
    if not a.skip_audit:
        loader.run(a.out, target_week=a.week, output_root=a.output_root, write=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
