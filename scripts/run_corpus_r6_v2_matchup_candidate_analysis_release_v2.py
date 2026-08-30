#!/usr/bin/env python3
"""CLI for the candidate-rooted outcome-blind R6-v2 accepted release."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)
from nfl_dfs.research.corpus_neo4j_transport import (
    ExactObjectStore,
    GoogleCloudObjectStore,
)


COMMANDS: Final = ("prepare", "run-worker", "verify-worker", "finish")
CLOUD_RUN_TASK_INDEX: Final = "CLOUD_RUN_TASK_INDEX"
_COMMIT = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_ORDINAL = re.compile(r"(?:0|[1-9][0-9]*)")


class CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(RuntimeError):
    """The CLI cannot preserve an exact release boundary."""


def _fail(message: str) -> None:
    raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(message)


def _load_identity(
    path: Path, *, label: str, carrier_fields: Sequence[str] = (),
) -> dict[str, object]:
    if not path.is_absolute():
        _fail(f"{label} path must be absolute")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(
            f"cannot read {label} file"
        ) from exc
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or raw not in {canonical, canonical + b"\n"}:
        _fail(f"{label} must be canonical JSON with at most one newline")
    try:
        parsed = batch.parse_canonical_json_bytes(canonical, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(str(exc)) from exc
    if not isinstance(parsed, Mapping):
        _fail(f"{label} must be an object")
    candidate: object = parsed
    present = [field for field in carrier_fields if field in parsed]
    if len(present) > 1:
        _fail(f"{label} carries multiple candidate identity fields")
    if present:
        candidate = parsed[present[0]]
    try:
        return batch.normalize_object_identity(candidate, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(str(exc)) from exc


def _project(value: object) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not value
        or any(character.isspace() for character in value)
    ):
        _fail("project must be one nonempty whitespace-free identifier")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase full Git commit")
    return value


def _image(value: object, *, label: str) -> str:
    if type(value) is not str or _IMAGE.fullmatch(value) is None:
        _fail(f"{label} must be one immutable image digest")
    return value


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("gs://")
        or not value.endswith("/")
        or any(character.isspace() for character in value)
    ):
        _fail("output prefix must be one canonical trailing-slash GCS prefix")
    bucket_and_object = value[5:]
    bucket, separator, object_name = bucket_and_object.partition("/")
    if not bucket or not separator or not object_name or "//" in object_name:
        _fail("output prefix must name one non-root canonical GCS prefix")
    return value


def _repository_root(value: object) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        _fail("repository root must be absolute")
    try:
        root = value.resolve(strict=True)
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(
            "repository root does not exist"
        ) from exc
    if not root.is_dir():
        _fail("repository root must be an existing directory")
    return root


def _ordinal_text(value: object, *, label: str) -> int:
    if type(value) is not str or _ORDINAL.fullmatch(value) is None:
        _fail(f"{label} must be one canonical decimal integer in 0..53")
    ordinal = int(value)
    if ordinal >= release.AUTHORITATIVE_SLATE_COUNT:
        _fail(f"{label} must be one canonical decimal integer in 0..53")
    return ordinal


def _ordinal_argument(value: str) -> int:
    try:
        return _ordinal_text(value, label="source ordinal")
    except CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _source_ordinal(
    explicit: int | None, *, environment: Mapping[str, str],
) -> int:
    if explicit is not None and (
        type(explicit) is not int
        or not 0 <= explicit < release.AUTHORITATIVE_SLATE_COUNT
    ):
        _fail("explicit source ordinal must be one exact integer in 0..53")
    raw_task_index = environment.get(CLOUD_RUN_TASK_INDEX)
    if raw_task_index is None:
        if explicit is None:
            _fail(
                "worker/verifier requires --source-ordinal or "
                "CLOUD_RUN_TASK_INDEX"
            )
        return explicit
    task_index = _ordinal_text(
        raw_task_index, label=CLOUD_RUN_TASK_INDEX
    )
    if explicit is not None and explicit != task_index:
        _fail(
            "explicit source ordinal conflicts with CLOUD_RUN_TASK_INDEX"
        )
    return task_index


def _git_head(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(
            "measured Git HEAD failed"
        ) from exc


def _git_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "show", f"{commit}:{relative_path}"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(
            f"measured Git blob failed for {relative_path}"
        ) from exc
    return completed.stdout


def _git_status(repository_root: Path, relative_paths: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            [
                "git", "status", "--porcelain=v1", "--untracked-files=all",
                "--", *relative_paths,
            ],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2CLIError(
            "critical-path Git status measurement failed"
        ) from exc
    return completed.stdout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare, execute, independently verify, and finish the exact "
            "candidate-rooted outcome-blind R6-v2 release"
        )
    )
    parser.add_argument(
        "--project",
        help="optional GCP project used only to construct the exact GCS store",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--panel-index-identity", required=True, type=Path)
    prepare.add_argument(
        "--lane-terminal-identity", required=True, action="append", type=Path
    )
    prepare.add_argument(
        "--matchup-source-release-identity", required=True, type=Path
    )
    prepare.add_argument("--source-commit-sha", required=True)
    prepare.add_argument("--immutable-image", required=True)
    prepare.add_argument("--output-prefix", required=True)
    prepare.add_argument(
        "--execute",
        action="store_true",
        help="explicitly authorize this command's create-once cloud writes",
    )

    for name in ("run-worker", "verify-worker"):
        command = commands.add_parser(name)
        command.add_argument("--manifest-identity", required=True, type=Path)
        command.add_argument("--source-ordinal", type=_ordinal_argument)
        command.add_argument("--repository-root", required=True, type=Path)
        command.add_argument("--runtime-source-commit-sha", required=True)
        command.add_argument("--runtime-immutable-image", required=True)
        command.add_argument(
            "--execute",
            action="store_true",
            help="explicitly authorize this command's create-once cloud writes",
        )

    finish = commands.add_parser("finish")
    finish.add_argument("--manifest-identity", required=True, type=Path)
    finish.add_argument(
        "--execute",
        action="store_true",
        help="explicitly authorize this command's create-once cloud writes",
    )
    return parser


def _validated_request(
    argv: Sequence[str], *, environment: Mapping[str, str],
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    if args.execute is not True:
        _fail(f"{args.command} requires explicit --execute")
    project = _project(args.project)
    if args.command == "prepare":
        if len(args.lane_terminal_identity) != 2:
            _fail("prepare requires exactly two lane terminal identities")
        kwargs = {
            "panel_index_identity": _load_identity(
                args.panel_index_identity,
                label="panel index identity",
                carrier_fields=("panel_object_identity", "panel_index_identity"),
            ),
            "lane_terminal_identities": [
                _load_identity(
                    path,
                    label=f"lane terminal identity[{ordinal}]",
                    carrier_fields=("terminal_receipt_identity",),
                )
                for ordinal, path in enumerate(args.lane_terminal_identity)
            ],
            "matchup_source_release_identity": _load_identity(
                args.matchup_source_release_identity,
                label="candidate-rooted matchup release identity",
                carrier_fields=("release_identity",),
            ),
            "source_commit_sha": _commit(
                args.source_commit_sha, label="source commit"
            ),
            "immutable_image": _image(
                args.immutable_image, label="immutable image"
            ),
            "output_prefix": _output_prefix(args.output_prefix),
        }
        return {"command": args.command, "project": project, "kwargs": kwargs}
    if args.command in {"run-worker", "verify-worker"}:
        kwargs = {
            "manifest_identity": _load_identity(
                args.manifest_identity,
                label="analysis manifest identity",
                carrier_fields=("manifest_identity",),
            ),
            "source_ordinal": _source_ordinal(
                args.source_ordinal, environment=environment
            ),
            "repository_root": _repository_root(args.repository_root),
            "runtime_source_commit_sha": _commit(
                args.runtime_source_commit_sha, label="runtime source commit"
            ),
            "runtime_immutable_image": _image(
                args.runtime_immutable_image, label="runtime immutable image"
            ),
            "git_head": _git_head,
            "git_blob": _git_blob,
            "git_status": _git_status,
        }
        return {"command": args.command, "project": project, "kwargs": kwargs}
    if args.command == "finish":
        kwargs = {
            "manifest_identity": _load_identity(
                args.manifest_identity,
                label="analysis manifest identity",
                carrier_fields=("manifest_identity",),
            )
        }
        return {"command": args.command, "project": project, "kwargs": kwargs}
    _fail(f"unregistered command {args.command!r}")


def _execute_validated_request(
    request: Mapping[str, object], *, storage: ExactObjectStore,
) -> dict[str, object]:
    command = request.get("command")
    raw_kwargs = request.get("kwargs")
    if not isinstance(raw_kwargs, Mapping):
        _fail("validated request kwargs differ")
    kwargs = dict(raw_kwargs)
    if command == "prepare":
        return release.prepare_release_v2(storage=storage, **kwargs)
    if command == "run-worker":
        return release.run_worker_v2(storage=storage, **kwargs)
    if command == "verify-worker":
        return release.verify_worker_v2(storage=storage, **kwargs)
    if command == "finish":
        return release.finish_release_v2(storage=storage, **kwargs)
    _fail(f"unregistered validated command {command!r}")


def run(
    argv: Sequence[str], *, storage: ExactObjectStore,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    request = _validated_request(
        argv, environment=os.environ if environment is None else environment
    )
    return _execute_validated_request(request, storage=storage)


def main(argv: Sequence[str] | None = None) -> int:
    parsed = list(sys.argv[1:] if argv is None else argv)
    request = _validated_request(parsed, environment=os.environ)
    storage = GoogleCloudObjectStore(project=request["project"])
    result = _execute_validated_request(request, storage=storage)
    sys.stdout.buffer.write(batch.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
