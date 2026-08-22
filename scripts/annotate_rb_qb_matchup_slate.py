"""Annotate one slate's RB and QB matchup context (families two/three).

Same mechanics as the receiver smoke: pinned catalog via the accepted
gt200 analysis artifact, as-read source identities (canonical-JSON hash
of each consumed extract), create-once local artifacts per family.
Outcome-blind; both families remain PROVISIONAL until their freeze
receipts exist. Default-off: --execute plus
RECEIVER_MATCHUP_ANNOTATIONS_ENABLED=1.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
from hashlib import sha256 as _sha256
from pathlib import Path
import sys

ENABLE_ENV = "RECEIVER_MATCHUP_ANNOTATIONS_ENABLED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--slate-id", required=True)
    parser.add_argument("--lock-time-utc", required=True)
    parser.add_argument("--maximum-source-time-utc", required=True)
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--analysis-uri", required=True)
    parser.add_argument("--analysis-generation", required=True)
    parser.add_argument("--analysis-sha256", required=True)
    parser.add_argument("--analysis-bytes", required=True, type=int)
    parser.add_argument("--project", default="nfl-predictions-503414")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    outputs = {
        "rb": args.output_dir / "rb-annotation.json",
        "qb": args.output_dir / "qb-annotation.json",
        "receipt": args.output_dir / "rb-qb-smoke-receipt.json",
    }
    for path in outputs.values():
        if path.exists() or path.is_symlink():
            print(f"refused: output exists: {path}", file=sys.stderr)
            return 2

    from google.cloud import bigquery, storage

    from nfl_dfs import bq
    from nfl_dfs.research.corpus_parametric_snapshot import (
        normalize_object_identity,
    )
    from nfl_dfs.research.rb_qb_matchup_annotations import (
        build_family_annotation_object,
        build_qb_matchup_rows,
        build_rb_matchup_rows,
        fetch_rb_qb_slate_inputs,
        qb_matchup_family_v1,
        rb_matchup_family_v1,
    )
    from nfl_dfs.research.receiver_matchup_contract import (
        canonical_json_bytes,
        canonical_sha256,
        validate_annotation_bytes,
    )

    def read_pinned(identity: dict[str, object]) -> bytes:
        client = storage.Client(project=args.project)
        uri = str(identity["uri"])
        bucket_name, _, object_name = uri[5:].partition("/")
        blob = client.bucket(bucket_name).blob(
            object_name, generation=int(str(identity["generation"]))
        )
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
    players = json.loads(
        read_pinned(catalog_identity).decode("utf-8")
    )["players"]

    inputs = fetch_rb_qb_slate_inputs(args.season, args.week)
    bigquery_client = bigquery.Client(project=args.project)

    def as_read_identity(table: str, rows: object) -> dict[str, object]:
        raw_rows = canonical_json_bytes(list(rows))
        handle = bigquery_client.get_table(table)
        return {
            "uri": f"bq://{table}?season={args.season}&week={args.week}",
            "generation": str(int(handle.modified.timestamp() * 1000)),
            "sha256": _sha256(raw_rows).hexdigest(),
            "bytes": len(raw_rows),
        }

    features = bq.settings.features
    rb_sources = {
        "rb-role-components": as_read_identity(
            f"{features}.rb_week_role_pit", inputs.rb_role_rows
        ),
        "defense-rb-role-concessions": as_read_identity(
            f"{features}.defense_rb_role_concession_pit",
            inputs.rb_concession_rows,
        ),
        "team-run-defense-context": as_read_identity(
            f"{features}.team_defense_context_pit",
            inputs.defense_context_rows,
        ),
    }
    qb_sources = {
        "qb-defense-concessions": as_read_identity(
            f"{features}.team_defense_context_pit",
            inputs.defense_context_rows,
        ),
        "pfr-pass-rush-context": as_read_identity(
            f"{features}.team_defense_context_pit",
            inputs.defense_context_rows,
        ),
        "secondary-coverage-quality": as_read_identity(
            f"{features}.defense_week_coverage", inputs.secondary_rows
        ),
    }

    summary: dict[str, object] = {}
    receipts: dict[str, object] = {}
    for name, family, build, sources, output in (
        ("rb", rb_matchup_family_v1(), build_rb_matchup_rows,
         rb_sources, outputs["rb"]),
        ("qb", qb_matchup_family_v1(), build_qb_matchup_rows,
         qb_sources, outputs["qb"]),
    ):
        rows = build(inputs, players)
        body = build_family_annotation_object(
            family=family,
            rows=rows,
            task_id=args.task_id,
            slate_id=args.slate_id,
            lock_time_utc=args.lock_time_utc,
            maximum_source_time_utc=args.maximum_source_time_utc,
            player_catalog_identity=catalog_identity,
            source_identities=sources,
            created_at_utc=args.created_at_utc,
        )
        raw = canonical_json_bytes(body)
        validate_annotation_bytes(
            raw, expected_family=family, require_analysis_grade=False
        )
        easy_field = (
            "easy_ground_matchup_v1" if name == "rb"
            else "easy_pass_matchup_v1"
        )
        with_edge = [
            row for row in body["rows"]
            if row["values"]["matchup_edge_score"] is not None
        ]
        easy = sorted(
            row["player_id"] for row in body["rows"]
            if row["values"][easy_field] is True
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
        summary[name] = {
            "row_count": len(body["rows"]),
            "rows_with_edge": len(with_edge),
            "easy_true_count": len(easy),
        }
        receipts[name] = {
            "annotation_object_sha256": body["annotation_object_sha256"],
            "annotation_bytes": len(raw),
            "source_identities": sources,
            "easy_players": easy,
            **summary[name],
        }
    receipt = {
        "schema_version": "rb-qb-matchup-annotation-smoke/v1",
        "slate_id": args.slate_id,
        "task_id": args.task_id,
        "player_catalog_identity": catalog_identity,
        "analysis_identity": analysis_identity,
        "families": receipts,
        "family_provisional": True,
        "uses_realized_outcomes": False,
        "freeze_gate": (
            "task-0 halves complete for rb/qb; winner-slate halves and "
            "family freeze receipts remain"
        ),
    }
    receipt["smoke_receipt_sha256"] = canonical_sha256(receipt)
    outputs["receipt"].write_bytes(canonical_json_bytes(receipt) + b"\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
