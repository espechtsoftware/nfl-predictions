"""Exact shared image-build contract for the corpus research expansion.

The source publisher, 54x7 parametric batch, realized-outcome grader, graph
loader, and dashboard use one immutable image.  This module prevents those
transports from accepting subtly different builds and deliberately binds a
focused corpus test surface instead of rerunning the repository-wide suite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
import shlex
from typing import Final


EXPECTED_CODE_REPOSITORY: Final = (
    "https://github.com/espechtsoftware/nfl-predictions.git"
)
EXPANSION_DOCKERFILE: Final = "Dockerfile.corpus-research-expansion"

FOCUSED_TEST_FILES: Final = (
    "tests/test_corpus_retrieval_engine.py",
    "tests/test_corpus_retrieval_transport.py",
    "tests/test_corpus_artifact_source_authority.py",
    "tests/test_prepare_corpus_artifact_source_authority.py",
    "tests/test_corpus_artifact_source_transport.py",
    "tests/test_corpus_parametric_batch.py",
    "tests/test_corpus_batch_evidence_contract.py",
    "tests/test_corpus_legal_feasibility.py",
    "tests/test_corpus_legal_feasibility_verifier.py",
    "tests/test_prepare_corpus_parametric_batch_v1.py",
    "tests/test_corpus_parametric_transport.py",
    "tests/test_corpus_realized_grading.py",
    "tests/test_corpus_realized_outcome_transport.py",
    "tests/test_corpus_realized_cloud_transport.py",
    "tests/test_corpus_retrieval_neo4j.py",
    "tests/test_corpus_neo4j_transport.py",
    "tests/test_corpus_strategy_registry.py",
    "tests/test_corpus_strategy_registry_release.py",
    "tests/test_corpus_research_ui.py",
    "tests/test_corpus_research_ui_bridge.py",
    "tests/test_corpus_expansion_build.py",
)

FOCUSED_TEST_COMMANDS: Final = (
    ("apt-get", "update"),
    (
        "apt-get", "install", "-y", "--no-install-recommends", "git",
        "jq", "libgomp1",
    ),
    ("pip", "install", "--no-cache-dir", ".[gcp,app,graph,dev]"),
    (
        "PYTHONPATH=src", "python", "-m", "pytest", "-q",
        *FOCUSED_TEST_FILES,
    ),
)

SOURCE_SMOKE_COMMANDS: Final = (
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_artifact_source_authority.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_artifact_source_authority.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_artifact_source_authority.py", "cloud-worker",
        "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_artifact_source_transport.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_artifact_source_transport.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "bash", "-n",
        "scripts/cloud_corpus_artifact_source_v1_reuse.sh",
    ),
)

PARAMETRIC_SMOKE_COMMANDS: Final = (
    (
        "docker", "run", "--rm", "${_IMAGE}", "python", "-c",
        "from pathlib import Path; from nfl_dfs.research import "
        "corpus_legal_feasibility as c; assert c._CODE_SOURCE_BUILD_PATHS "
        "== ('Dockerfile.corpus-research-expansion', "
        "'cloudbuild.corpus-research-expansion.yaml'); print({name: "
        "c._repository_source_sha256(Path('/app'), name) for name in "
        "c._CODE_SOURCE_BUILD_PATHS})",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_parametric_transport.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_parametric_transport.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_parametric_batch_v1.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_parametric_batch_v1.py", "solver-probe",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "bash", "-n",
        "scripts/cloud_corpus_parametric_v1_reuse.sh",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_realized_outcomes.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_realized_cloud_transport.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_realized_cloud_transport.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "bash", "-n",
        "scripts/cloud_corpus_realized_v1_reuse.sh",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python", "-c",
        "import nfl_dfs.research.corpus_legal_feasibility; "
        "import nfl_dfs.research.corpus_legal_feasibility_verifier; "
        "import nfl_dfs.research.corpus_realized_grading; "
        "import nfl_dfs.research.corpus_realized_outcome_transport; "
        "import nfl_dfs.research.corpus_realized_cloud_transport",
    ),
)

NEO4J_SMOKE_COMMANDS: Final = (
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_neo4j_load_manifest.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_neo4j_transport.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/run_corpus_neo4j_transport.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "bash", "-n",
        "scripts/cloud_corpus_neo4j_v1_reuse.sh",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_strategy_registry_release.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/prepare_corpus_strategy_registry_release.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/materialize_corpus_research_ui_projection.py", "--help",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python",
        "scripts/materialize_corpus_research_ui_projection.py", "parked",
    ),
    (
        "docker", "run", "--rm", "${_IMAGE}", "python", "-c",
        "import neo4j; import nfl_dfs.research.corpus_neo4j_transport; "
        "import nfl_dfs.research.corpus_strategy_registry; "
        "import nfl_dfs.research.corpus_strategy_registry_release; "
        "import nfl_dfs.research.corpus_research_ui_bridge; "
        "import nfl_dfs.app.corpus_research",
    ),
)

EXPECTED_STEP_SPECS: Final = (
    ("focused-corpus-research-tests", "python:3.11-slim", "bash"),
    ("build-image", "gcr.io/cloud-builders/docker", ""),
    ("smoke-corpus-artifact-source", "gcr.io/cloud-builders/docker", "bash"),
    (
        "smoke-corpus-parametric-expansion",
        "gcr.io/cloud-builders/docker",
        "bash",
    ),
    ("smoke-corpus-neo4j-transport", "gcr.io/cloud-builders/docker", "bash"),
)

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_BUILD = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_ALLOWED_STEP_KEYS: Final = frozenset({
    "args", "entrypoint", "exitCode", "id", "name", "pullTiming",
    "status", "timing",
})


class CorpusExpansionBuildError(RuntimeError):
    """The shared expansion image does not match its exact build law."""


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusExpansionBuildError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise CorpusExpansionBuildError(f"{label} must be an array")
    return value


def _shell_commands(value: object, *, label: str) -> tuple[tuple[str, ...], ...]:
    row = _mapping(value, label=label)
    args = _sequence(row.get("args"), label=f"{label}.args")
    if len(args) != 2 or args[0] != "-ceu" or type(args[1]) is not str:
        raise CorpusExpansionBuildError(f"{label} shell argv differs")
    lexer = shlex.shlex(
        args[1].replace("\\\n", " ").replace("\n", ";"),
        posix=True,
        punctuation_chars=";&|()",
    )
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise CorpusExpansionBuildError(f"{label} shell syntax differs") from exc
    commands: list[tuple[str, ...]] = []
    current: list[str] = []
    for token in tokens:
        if token and set(token) <= set(";&|()"):
            if token != ";":
                raise CorpusExpansionBuildError(
                    f"{label} may not mask or branch failures"
                )
            if current:
                commands.append(tuple(current))
                current = []
        else:
            current.append(token)
    if current:
        commands.append(tuple(current))
    return tuple(commands)


def _materialize(
    commands: Sequence[Sequence[str]], *, image_tag: str,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(image_tag if token == "${_IMAGE}" else token for token in command)
        for command in commands
    )


def validate_build_metadata(
    value: object, *, build_id: str, code_sha: str, image: str,
) -> dict[str, str]:
    """Validate one successful exact-source shared expansion build."""
    item = _mapping(value, label="build metadata")
    if (
        _BUILD.fullmatch(build_id) is None
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(image) is None
        or item.get("id") != build_id
        or item.get("status") != "SUCCESS"
    ):
        raise CorpusExpansionBuildError("immutable build identity differs")
    source = _mapping(item.get("source"), label="build source")
    provenance = _mapping(
        item.get("sourceProvenance"), label="build source provenance"
    )
    requested = _mapping(source.get("gitSource"), label="requested Git source")
    resolved = _mapping(
        provenance.get("resolvedGitSource"), label="resolved Git source"
    )
    expected_source = {
        "revision": code_sha,
        "url": EXPECTED_CODE_REPOSITORY,
    }
    if (
        set(source) != {"gitSource"}
        or set(provenance) != {"resolvedGitSource"}
        or dict(requested) != expected_source
        or dict(resolved) != expected_source
    ):
        raise CorpusExpansionBuildError("build source commit differs")

    substitutions = _mapping(
        item.get("substitutions"), label="build substitutions"
    )
    image_tag = substitutions.get("_IMAGE")
    digest = image.rsplit("@", 1)[1]
    if (
        set(substitutions) != {"_IMAGE"}
        or type(image_tag) is not str
        or image_tag.rsplit(":", 1)[0] != image.rsplit("@", 1)[0]
        or item.get("images") != [image_tag]
        or item.get("artifacts") != {"images": [image_tag]}
        or item.get("timeout") != "10800s"
        or item.get("options")
        != {"logging": "LEGACY", "machineType": "E2_HIGHCPU_8", "pool": {}}
    ):
        raise CorpusExpansionBuildError("build image/config binding differs")
    results = _mapping(item.get("results"), label="build results")
    result_images = _sequence(
        results.get("images"), label="build result images"
    )
    if len(result_images) != 1 or not isinstance(result_images[0], Mapping):
        raise CorpusExpansionBuildError("build result image census differs")
    if (
        result_images[0].get("name") != image_tag
        or result_images[0].get("digest") != digest
    ):
        raise CorpusExpansionBuildError("build image digest differs")

    steps = _sequence(item.get("steps"), label="build steps")
    if len(steps) != len(EXPECTED_STEP_SPECS):
        raise CorpusExpansionBuildError("build step census/order differs")
    retained: list[Mapping[str, object]] = []
    for ordinal, (raw, expected) in enumerate(zip(steps, EXPECTED_STEP_SPECS)):
        row = _mapping(raw, label=f"build step[{ordinal}]")
        if set(row) - _ALLOWED_STEP_KEYS:
            raise CorpusExpansionBuildError(
                f"build step[{ordinal}] retains unbound execution fields"
            )
        expected_id, expected_name, expected_entrypoint = expected
        if (
            row.get("id") != expected_id
            or row.get("name") != expected_name
            or str(row.get("entrypoint", "")) != expected_entrypoint
            or row.get("status") != "SUCCESS"
            or (
                row.get("exitCode") is not None
                and (type(row.get("exitCode")) is not int or row["exitCode"] != 0)
            )
        ):
            raise CorpusExpansionBuildError(
                f"build step[{ordinal}] identity/status differs"
            )
        retained.append(row)

    if list(_sequence(retained[1].get("args"), label="image build args")) != [
        "build", "-f", EXPANSION_DOCKERFILE, "-t", image_tag, ".",
    ]:
        raise CorpusExpansionBuildError("immutable image build argv differs")
    expected_commands = (
        FOCUSED_TEST_COMMANDS,
        SOURCE_SMOKE_COMMANDS,
        PARAMETRIC_SMOKE_COMMANDS,
        NEO4J_SMOKE_COMMANDS,
    )
    for step, commands, label in zip(
        (retained[0], retained[2], retained[3], retained[4]),
        expected_commands,
        ("focused tests", "source smoke", "parametric smoke", "Neo4j smoke"),
    ):
        actual = _shell_commands(step, label=label)
        expected = _materialize(commands, image_tag=image_tag)
        if actual != expected:
            raise CorpusExpansionBuildError(f"{label} commands are not exact")
    build_config = {
        "schema_version": "shared-focused-corpus-research-expansion/v1",
        "source_commit": code_sha,
        "steps": [{
            key: row[key]
            for key in ("name", "id", "entrypoint", "args")
            if key in row
        } for row in retained],
        "image_tag": image_tag,
        "image_digest": digest,
        "dockerfile": EXPANSION_DOCKERFILE,
    }
    build_config_sha256 = sha256(json.dumps(
        build_config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return {
        "build_id": build_id,
        "code_repository": EXPECTED_CODE_REPOSITORY,
        "code_sha": code_sha,
        "image": image,
        "image_tag": image_tag,
        "build_contract": "shared-focused-corpus-research-expansion/v1",
        "build_config_sha256": build_config_sha256,
    }


__all__ = [
    "CorpusExpansionBuildError",
    "EXPECTED_CODE_REPOSITORY",
    "EXPECTED_STEP_SPECS",
    "EXPANSION_DOCKERFILE",
    "FOCUSED_TEST_COMMANDS",
    "FOCUSED_TEST_FILES",
    "NEO4J_SMOKE_COMMANDS",
    "PARAMETRIC_SMOKE_COMMANDS",
    "SOURCE_SMOKE_COMMANDS",
    "validate_build_metadata",
]
