#!/usr/bin/env python3
"""Create a local Neo4j-ready phenotype projection from accepted sparse evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Mapping

from nfl_dfs.research import corpus_retrieval_engine as engine
from nfl_dfs.research.corpus_gt200_analysis import build_gt200_analysis


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-result-uri", required=True)
    parser.add_argument("--task-result-generation", required=True)
    parser.add_argument("--task-result-sha256", required=True)
    parser.add_argument("--task-result-bytes", required=True, type=int)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--context-annotations", type=Path)
    parser.add_argument(
        "--output", type=Path, required=True,
        help="new canonical JSON path; existing files are never overwritten",
    )
    return parser


def _split_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("object URI must start with gs://")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name:
        raise ValueError("object URI must include bucket and object name")
    return bucket, name


def main() -> int:
    args = _parser().parse_args()
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise SystemExit("google-cloud-storage is required (install project[gcp])") from exc

    client = storage.Client()

    def read_exact(identity: Mapping[str, object]) -> bytes:
        normalized = engine.normalize_object_identity(identity, label="GCS object identity")
        bucket_name, object_name = _split_gcs_uri(str(normalized["uri"]))
        generation = int(str(normalized["generation"]))
        blob = client.bucket(bucket_name).blob(object_name, generation=generation)
        return blob.download_as_bytes(if_generation_match=generation)

    task_identity = {
        "uri": args.task_result_uri,
        "generation": args.task_result_generation,
        "sha256": args.task_result_sha256,
        "bytes": args.task_result_bytes,
    }
    task_raw = read_exact(task_identity)
    annotations = None
    if args.context_annotations is not None:
        annotation_raw = args.context_annotations.read_bytes()
        if annotation_raw.endswith(b"\n"):
            annotation_raw = annotation_raw[:-1]
        annotations = engine.parse_canonical_json_bytes(
            annotation_raw, label="context annotations"
        )
    result = build_gt200_analysis(
        task_result_raw=task_raw,
        task_result_identity=task_identity,
        read_object=read_exact,
        analysis_id=args.analysis_id,
        created_at_utc=args.created_at_utc,
        context_annotations=annotations,
    )
    raw = engine.canonical_json_bytes(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(raw)
    summary = {
        "analysis_sha256": result["analysis_sha256"],
        "bytes": len(raw),
        "output": str(args.output.resolve()),
        "summary": result["summary"],
    }
    sys.stdout.buffer.write(engine.canonical_json_bytes(summary) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
