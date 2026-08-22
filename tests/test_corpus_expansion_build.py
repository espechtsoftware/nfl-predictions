from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shlex

import pytest
import yaml

from nfl_dfs.research import corpus_expansion_build as build


BUILD_ID = "11111111-2222-3333-4444-555555555555"
CODE_SHA = "a" * 40
IMAGE_REPOSITORY = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs"
)
IMAGE_TAG = f"{IMAGE_REPOSITORY}:corpus-expansion-fixture"
IMAGE = f"{IMAGE_REPOSITORY}@sha256:{'b' * 64}"
ROOT = Path(__file__).resolve().parents[1]


def _script(commands: tuple[tuple[str, ...], ...]) -> str:
    return "\n".join(shlex.join(command) for command in commands)


def _materialize(commands: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(IMAGE_TAG if token == "${_IMAGE}" else token for token in command)
        for command in commands
    )


def _metadata() -> dict[str, object]:
    source = {"revision": CODE_SHA, "url": build.EXPECTED_CODE_REPOSITORY}
    command_sets = (
        build.FOCUSED_TEST_COMMANDS,
        build.SOURCE_SMOKE_COMMANDS,
        build.PARAMETRIC_SMOKE_COMMANDS,
        build.NEO4J_SMOKE_COMMANDS,
    )
    shell_scripts = [_script(_materialize(commands)) for commands in command_sets]
    rows: list[dict[str, object]] = []
    shell_ordinal = 0
    for step_id, name, entrypoint in build.EXPECTED_STEP_SPECS:
        if step_id == "build-image":
            args = [
                "build", "-f", build.EXPANSION_DOCKERFILE,
                "-t", IMAGE_TAG, ".",
            ]
        else:
            args = ["-ceu", shell_scripts[shell_ordinal]]
            shell_ordinal += 1
        row: dict[str, object] = {
            "id": step_id,
            "name": name,
            "args": args,
            "status": "SUCCESS",
            "exitCode": 0,
        }
        if entrypoint:
            row["entrypoint"] = entrypoint
        rows.append(row)
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "substitutions": {"_IMAGE": IMAGE_TAG},
        "images": [IMAGE_TAG],
        "artifacts": {"images": [IMAGE_TAG]},
        "timeout": "10800s",
        "options": {
            "logging": "LEGACY",
            "machineType": "E2_HIGHCPU_8",
            "pool": {},
        },
        "results": {"images": [{
            "name": IMAGE_TAG,
            "digest": IMAGE.rsplit("@", 1)[1],
        }]},
        "steps": rows,
    }


def test_shared_focused_expansion_build_is_exact() -> None:
    retained = build.validate_build_metadata(
        _metadata(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )
    assert retained["build_contract"] == (
        "shared-focused-corpus-research-expansion/v1"
    )
    assert "PYTHONPATH=src pytest" not in _metadata()["steps"][0]["args"][1]
    assert tuple(build.FOCUSED_TEST_FILES) == tuple(dict.fromkeys(
        build.FOCUSED_TEST_FILES
    ))


def test_committed_cloud_build_matches_shared_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "cloudbuild.corpus-research-expansion.yaml").read_text()
    )
    metadata = _metadata()
    retained_steps = deepcopy(config["steps"])
    for row in retained_steps:
        row["args"] = [
            argument.replace("${_IMAGE}", IMAGE_TAG)
            for argument in row["args"]
        ]
        row["status"] = "SUCCESS"
        row["exitCode"] = 0
    metadata["steps"] = retained_steps
    build.validate_build_metadata(
        metadata, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )
    assert config["images"] == ["${_IMAGE}"]
    assert config["timeout"] == "10800s"


def test_expansion_image_retains_runtime_code_source_build_definitions() -> None:
    dockerfile = (
        ROOT / "Dockerfile.corpus-research-expansion"
    ).read_text(encoding="utf-8")
    assert (
        "COPY pyproject.toml README.md CLAUDE.md "
        "Dockerfile.corpus-research-expansion "
        "cloudbuild.corpus-research-expansion.yaml ./"
        in dockerfile
    )
    assert build.PARAMETRIC_SMOKE_COMMANDS[0] == (
        "docker", "run", "--rm", "${_IMAGE}", "python", "-c",
        "from pathlib import Path; from nfl_dfs.research import "
        "corpus_legal_feasibility as c; assert c._CODE_SOURCE_BUILD_PATHS "
        "== ('Dockerfile.corpus-research-expansion', "
        "'cloudbuild.corpus-research-expansion.yaml'); print({name: "
        "c._repository_source_sha256(Path('/app'), name) for name in "
        "c._CODE_SOURCE_BUILD_PATHS})",
    )


@pytest.mark.parametrize("mutation", [
    lambda value: value["steps"].pop(),
    lambda value: value["steps"].append(deepcopy(value["steps"][-1])),
    lambda value: value["steps"][0].update({"env": ["PYTEST_ADDOPTS=-k smoke"]}),
    lambda value: value["steps"][0]["args"].__setitem__(
        1, value["steps"][0]["args"][1] + " || true"
    ),
    lambda value: value["steps"][0]["args"].__setitem__(
        1, "PYTHONPATH=src pytest"
    ),
    lambda value: value["steps"][1]["args"].__setitem__(2, "Dockerfile"),
])
def test_shared_build_rejects_missing_extra_or_weakened_surface(mutation) -> None:
    metadata = _metadata()
    mutation(metadata)
    with pytest.raises(build.CorpusExpansionBuildError):
        build.validate_build_metadata(
            metadata, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
        )
