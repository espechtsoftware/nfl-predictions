#!/usr/bin/env python3
"""Read-only bounded report for one exact R6 realized-grade completion."""

from __future__ import annotations

import argparse
import os
from typing import Mapping, Sequence

from nfl_dfs.research import corpus_r6_full_union_score_report_v1 as report
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release
from nfl_dfs.research import corpus_parametric_batch as batch


PROJECT = "nfl-predictions-503414"
ENABLED_ENV = "R6_FULL_UNION_SCORE_REPORT_ENABLED"


class ScoreReportCliV1Error(ValueError):
    pass


class GenerationPinnedGCSV1:
    def __init__(self, client: object) -> None:
        self.client = client

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = batch.normalize_object_identity(identity, label="report object")
        uri = str(retained["uri"])
        if not uri.startswith("gs://"):
            raise ScoreReportCliV1Error("report object URI differs")
        bucket_name, object_name = uri[5:].split("/", 1)
        blob = self.client.bucket(bucket_name).blob(
            object_name, generation=int(str(retained["generation"]))
        )
        return bytes(blob.download_as_bytes(if_generation_match=int(
            str(retained["generation"])
        )))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--grade-completion-uri", required=True)
    parser.add_argument("--grade-completion-generation", required=True)
    parser.add_argument("--grade-completion-sha256", required=True)
    parser.add_argument("--grade-completion-bytes", type=int, required=True)
    parser.add_argument("--expected-grade-run-id", required=True)
    parser.add_argument("--expected-grade-job", required=True)
    parser.add_argument("--expected-grade-execution", required=True)
    parser.add_argument("--expected-grade-code-sha", required=True)
    parser.add_argument("--expected-grade-image", required=True)
    parser.add_argument("--expected-supply-run-id", required=True)
    parser.add_argument("--expected-supply-job", required=True)
    parser.add_argument("--expected-supply-code-sha", required=True)
    parser.add_argument("--expected-supply-image", required=True)
    parser.add_argument("--snapshot-module-sha256", required=True)
    parser.add_argument("--snapshot-cli-sha256", required=True)
    parser.add_argument("--snapshot-test-sha256", required=True)
    parser.add_argument("--snapshot-cli-test-sha256", required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *, environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    env = os.environ if environ is None else environ
    if not args.execute or env.get(ENABLED_ENV) != "1":
        raise ScoreReportCliV1Error(f"--execute and {ENABLED_ENV}=1 are required")
    if args.project != PROJECT:
        raise ScoreReportCliV1Error("score-report project differs")
    try:
        identity = batch.normalize_object_identity({
            "uri": args.grade_completion_uri,
            "generation": args.grade_completion_generation,
            "sha256": args.grade_completion_sha256,
            "bytes": args.grade_completion_bytes,
        }, label="grade completion identity")
        config = release.FullUnionGradeReleaseConfigV1(
            run_id=args.expected_grade_run_id,
            job=args.expected_grade_job,
            execution=args.expected_grade_execution,
            code_sha=args.expected_grade_code_sha,
            image=args.expected_grade_image,
            expected_supply_run_id=args.expected_supply_run_id,
            expected_supply_job=args.expected_supply_job,
            expected_supply_code_sha=args.expected_supply_code_sha,
            expected_supply_image=args.expected_supply_image,
            snapshot_module_sha256=args.snapshot_module_sha256,
            snapshot_cli_sha256=args.snapshot_cli_sha256,
            snapshot_test_sha256=args.snapshot_test_sha256,
            snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
            enabled=True,
        )
        release.validate_grade_release_config_v1(config)
        if identity["uri"] != config.completion_uri:
            raise ScoreReportCliV1Error(
                "grade completion URI/runtime coordinate differs"
            )
    except (
        ScoreReportCliV1Error,
        batch.CorpusParametricBatchError,
        release.CorpusR6FullUnionGradeReleaseV1Error,
    ) as exc:
        raise ScoreReportCliV1Error(str(exc)) from exc
    if storage_client is None:
        from google.cloud import storage
        storage_client = storage.Client(project=PROJECT)
    result = report.build_persisted_score_report_v1(
        grade_completion_identity=identity,
        grade_release_config=config,
        read_exact=GenerationPinnedGCSV1(storage_client).read_exact,
    )
    print(grading.canonical_json_bytes(result).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ScoreReportCliV1Error,
        report.CorpusR6FullUnionScoreReportV1Error,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
