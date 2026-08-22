"""Annotate one slate's player catalog with receiver-matchup context.

Reads the generation-pinned player catalog (directly, or via the accepted
gt200 analysis artifact which embeds `player_catalog_identity`), fetches
the built PIT layers for the slate week from BigQuery, computes the
frozen-law annotation rows, and writes the create-once annotation object
plus a smoke receipt locally. Outcome-blind: no realized target-week
outcome is read anywhere in the path.

Source identities for the six family roles are computed over the EXACT
row sets fetched for this slate (canonical-JSON hash of the consumed
extract, `bq://` URI with the table's last-modified generation) — the
"source as read" identity. The family remains PROVISIONAL; this smoke is
the task-0 half of the P3 freeze gate.

Default-off: requires --execute and RECEIVER_MATCHUP_ANNOTATIONS_ENABLED=1.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
from pathlib import Path
import sys

ENABLE_ENV = "RECEIVER_MATCHUP_ANNOTATIONS_ENABLED"


def _identity_args(parser: argparse.ArgumentParser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-uri", required=True)
    parser.add_argument(f"--{prefix}-generation", required=True)
    parser.add_argument(f"--{prefix}-sha256", required=True)
    parser.add_argument(f"--{prefix}-bytes", required=True, type=int)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--season", required=True, type=int)
    value.add_argument("--week", required=True, type=int)
    value.add_argument("--task-id", required=True)
    value.add_argument("--slate-id", required=True)
    value.add_argument("--lock-time-utc", required=True)
    value.add_argument("--maximum-source-time-utc", required=True)
    value.add_argument("--created-at-utc", required=True)
    _identity_args(value, "analysis")
    value.add_argument("--project", default="nfl-predictions-503414")
    value.add_argument("--output-dir", required=True, type=Path)
    value.add_argument("--execute", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    output_dir: Path = args.output_dir
    annotation_path = output_dir / "annotation.json"
    receipt_path = output_dir / "smoke-receipt.json"
    for path in (annotation_path, receipt_path):
        if path.exists() or path.is_symlink():
            print(f"refused: output exists: {path}", file=sys.stderr)
            return 2

    from google.cloud import bigquery, storage

    from nfl_dfs import bq
    from nfl_dfs.research.corpus_parametric_snapshot import (
        normalize_object_identity,
    )
    from nfl_dfs.research.receiver_matchup_annotations import (
        SlateMatchupInputs,
        build_slate_annotation_object,
        fetch_slate_inputs,
    )
    from nfl_dfs.research.receiver_matchup_contract import (
        canonical_json_bytes,
        canonical_sha256,
        receiver_matchup_family_v1,
        validate_annotation_bytes,
    )
    from hashlib import sha256 as _sha256

    def read_pinned(identity: dict[str, object]) -> bytes:
        client = storage.Client(project=args.project)
        uri = str(identity["uri"])
        bucket_name, _, object_name = uri[5:].partition("/")
        blob = client.bucket(bucket_name).blob(
            object_name, generation=int(str(identity["generation"]))
        )
        # raw_download keeps the STORED bytes: objects published with
        # content_encoding gzip are otherwise transparently decompressed
        # and would fail their pinned byte/hash identity.
        raw = blob.download_as_bytes(raw_download=True)
        if (
            len(raw) != identity["bytes"]
            or _sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise SystemExit(f"pinned object identity differs: {uri}")
        return raw

    analysis_identity = normalize_object_identity({
        "uri": args.analysis_uri,
        "generation": args.analysis_generation,
        "sha256": args.analysis_sha256,
        "bytes": args.analysis_bytes,
    }, label="analysis artifact")
    analysis_raw = read_pinned(analysis_identity)
    if str(analysis_identity["uri"]).endswith(".gz"):
        analysis_raw = gzip.GzipFile(
            fileobj=io.BytesIO(analysis_raw)
        ).read()
    analysis = json.loads(analysis_raw.decode("utf-8"))
    evidence = analysis.get("evidence", analysis)
    catalog_identity = normalize_object_identity(
        evidence["player_catalog_identity"], label="player catalog identity"
    )
    catalog_raw = read_pinned(catalog_identity)
    catalog = json.loads(catalog_raw.decode("utf-8"))
    players = catalog["players"]

    inputs = fetch_slate_inputs(args.season, args.week)

    table_names = {
        "receiver-role-components":
            f"{bq.settings.features}.receiver_week_role_pit",
        "defense-role-concessions":
            f"{bq.settings.features}.defense_receiver_role_concession_pit",
        "sis-defender-alignment":
            f"{bq.settings.features}.defender_alignment_quality_week_pit",
        "fantasy-points-alignment":
            f"{bq.settings.raw}.fantasy_points_alignment_player_l4",
        "fantasy-points-shell-fit":
            f"{bq.settings.raw}.fantasy_points_receiver_coverage_prior",
        "pfr-secondary":
            f"{bq.settings.features}.defense_week_coverage",
    }
    extracts = {
        "receiver-role-components": inputs.role_rows,
        "defense-role-concessions": inputs.concession_rows,
        "sis-defender-alignment": inputs.defender_rows,
        "fantasy-points-alignment": inputs.alignment_rows,
        "fantasy-points-shell-fit": inputs.shell_receiver_rows,
        # The PFR secondary component enters at family-freeze; its as-read
        # extract for the smoke is the shell-defense rows consumed today.
        "pfr-secondary": inputs.shell_defense_rows,
    }
    bigquery_client = bigquery.Client(project=args.project)
    source_identities: dict[str, dict[str, object]] = {}
    for role, rows in extracts.items():
        raw_rows = canonical_json_bytes(list(rows))
        table = bigquery_client.get_table(table_names[role])
        generation = str(int(table.modified.timestamp() * 1000))
        source_identities[role] = {
            "uri": (
                f"bq://{table_names[role]}"
                f"?season={args.season}&week={args.week}"
            ),
            "generation": generation,
            "sha256": _sha256(raw_rows).hexdigest(),
            "bytes": len(raw_rows),
        }

    family = receiver_matchup_family_v1()
    body = build_slate_annotation_object(
        inputs=inputs,
        catalog_players=players,
        family=family,
        task_id=args.task_id,
        slate_id=args.slate_id,
        lock_time_utc=args.lock_time_utc,
        maximum_source_time_utc=args.maximum_source_time_utc,
        player_catalog_identity=catalog_identity,
        source_identities=source_identities,
        created_at_utc=args.created_at_utc,
    )
    raw = canonical_json_bytes(body)
    validate_annotation_bytes(
        raw, expected_family=family, require_analysis_grade=False
    )

    rows = body["rows"]
    supported_edges = [
        row["values"]["matchup_edge_score"]
        for row in rows
        if row["values"]["matchup_edge_score"] is not None
    ]
    easy = [
        row["player_id"] for row in rows
        if row["values"]["easy_coverage_v1"] is True
    ]
    receipt = {
        "schema_version": "receiver-matchup-annotation-smoke/v1",
        "slate_id": args.slate_id,
        "task_id": args.task_id,
        "annotation_object_sha256": body["annotation_object_sha256"],
        "annotation_bytes": len(raw),
        "player_catalog_identity": catalog_identity,
        "analysis_identity": analysis_identity,
        "source_identities": source_identities,
        "row_count": len(rows),
        "rows_with_edge": len(supported_edges),
        "easy_coverage_true_count": len(easy),
        "easy_coverage_players": sorted(easy),
        "analysis_grade": body["analysis_grade"],
        "family_provisional": family.provisional,
        "uses_realized_outcomes": False,
        "freeze_gate": (
            "task-0 half complete; governed winner-slate half and exact "
            "max-source timestamps remain before the family freezes"
        ),
    }
    receipt["smoke_receipt_sha256"] = canonical_sha256(receipt)
    output_dir.mkdir(parents=True, exist_ok=True)
    annotation_path.write_bytes(raw)
    receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")
    print(json.dumps({
        "row_count": len(rows),
        "rows_with_edge": len(supported_edges),
        "easy_coverage_true_count": len(easy),
        "annotation_object_sha256": body["annotation_object_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
