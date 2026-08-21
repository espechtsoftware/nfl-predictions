from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_full_source_shards as transport  # noqa: E402
import finish_lr8_full_source_shards as finisher  # noqa: E402
from nfl_dfs.research import lr8_full_source_shards as shards  # noqa: E402
from nfl_dfs.research import lr8_historical_arm as lr8  # noqa: E402
from nfl_dfs.research import lr8_training_source as training  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402


CODE_SHA = "a" * 40
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)
PREP_PROVENANCE = transport.build_execution_provenance(
    mode="prepare",
    code_sha=CODE_SHA,
    build_id=BUILD_ID,
    image=IMAGE,
    job_generation="2",
    job_spec_sha256="c" * 64,
)


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _receipt(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://lr8-transport-fixture/{label}",
        "generation": "1",
        "sha256": _digest(label),
        "bytes": len(label) + 1,
    }


class MemoryPublisher:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def __call__(self, uri: str, raw: bytes) -> transport.PublishedObject:
        created = uri not in self.objects
        if not created and self.objects[uri] != raw:
            raise AssertionError("fixture create-once collision")
        self.objects.setdefault(uri, raw)
        reopened = self.objects[uri]
        return transport.PublishedObject(
            receipt={
                "uri": uri,
                "generation": "1",
                "sha256": sha256(reopened).hexdigest(),
                "bytes": len(reopened),
            },
            reopened_raw=reopened,
            created=created,
        )

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        return [{
            "uri": uri,
            "generation": "1",
            "bytes": len(raw),
        } for uri, raw in sorted(self.objects.items()) if uri.startswith(prefix)]

    def load(self, row: dict[str, object]):
        raw = self.objects[str(row["uri"])]
        return ({
            "uri": row["uri"],
            "generation": row["generation"],
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, raw)

    def load_receipt(self, value: object):
        receipt = transport._receipt(value, label="fixture receipt")  # noqa: SLF001
        raw = self.objects[receipt.uri]
        return ({
            "uri": receipt.uri,
            "generation": receipt.generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, raw)


def _players() -> tuple[rw.PlayerSpec, ...]:
    values = []
    teams = ("A", "B", "C", "D")
    opponents = {"A": "B", "B": "A", "C": "D", "D": "C"}
    games = {"A": "G1", "B": "G1", "C": "G2", "D": "G2"}
    serial = 0
    for position, count in {"QB": 1, "RB": 4, "WR": 4, "TE": 2, "DST": 1}.items():
        for offset in range(count):
            team = teams[(serial + offset) % 4]
            values.append(rw.PlayerSpec(
                player_id=f"{position}{offset}",
                position=position,
                team=team,
                opponent=opponents[team],
                game_id=games[team],
                salary=4_000,
            ))
        serial += count
    return tuple(sorted(values, key=lambda row: row.player_id))


def _rosters(players: tuple[rw.PlayerSpec, ...], count: int = 41):
    by_position = {
        position: tuple(
            row.player_id for row in players if row.position == position
        )
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result = []
    for rb_count, wr_count, te_count in ((2, 3, 2), (2, 4, 1), (3, 3, 1)):
        for rbs in combinations(by_position["RB"], rb_count):
            for wrs in combinations(by_position["WR"], wr_count):
                for tes in combinations(by_position["TE"], te_count):
                    roster = rw.canonical_identity((
                        *by_position["QB"], *rbs, *wrs, *tes,
                        *by_position["DST"],
                    ))
                    try:
                        lr8.audit_dk_classic_identity(players, roster)
                    except lr8.LR8Error:
                        continue
                    result.append(roster)
                    if len(result) == count:
                        return tuple(result)
    raise AssertionError("not enough fixture rosters")


@dataclass(frozen=True)
class Fixture:
    publication: transport.PreparedPublication
    publisher: MemoryPublisher
    rosters: tuple[tuple[str, ...], ...]
    replay_calls: tuple[int, ...]


@pytest.fixture(scope="module")
def prepared_grid() -> Fixture:
    players = _players()
    rosters = _rosters(players)
    incumbent = (rosters[-1],)
    ids = tuple(row.player_id for row in players)
    draws = np.zeros(
        (len(players), training.WORLDS_PER_BLOCK),
        dtype=np.float32,
        order="C",
    )
    draws.flags.writeable = False
    canonical = tuple(training.CanonicalSlateSource(
        season=season,
        week=week,
        panel_id=training.CANONICAL_PANEL_ID,
        players=players,
        incumbent_candidates=incumbent,
        catalog_sha256=training.catalog_sha256(players),
        incumbent_candidates_sha256=training.identities_sha256(incumbent),
        catalog_source_receipts=(_receipt("catalog.json"),),
        incumbent_source_receipts=(_receipt("incumbents.json"),),
    ) for season, week in training.EXPECTED_SLATE_KEYS)
    calls = []

    def replay_factory(season: int):
        calls.append(season)
        return tuple(training.PITReplayBlock(
            target_season=season,
            block=block,
            projection_seed=training.BLOCK_SEED_PAIRS[block][0],
            source_environment_role_seed_nonoperative=(
                training.BLOCK_SEED_PAIRS[block][1]
            ),
            replay_path_id=training.PIT_REPLAY_PATH_ID,
            model_training_seasons=training.MODEL_TRAINING_SEASONS[season],
            model_fit_input_sha256=_digest(f"fit-input-{season}"),
            model_fit_sha256=_digest(f"fit-model-{season}"),
            fit_source_receipts=(_receipt(f"pit-{season}.json"),),
            slates=tuple(training.ReplaySlateWorlds(
                season=season,
                week=week,
                player_ids=ids,
                player_draws=draws,
                player_ids_sha256=training.player_ids_sha256(ids),
                player_draws_sha256=training.array_sha256(draws),
                source_receipts=(
                    _receipt(f"draw-source-{season}-{block}.json"),
                ),
            ) for week in training.EXPECTED_WEEKS[season]),
        ) for block in training.BLOCK_ORDER)

    publisher = MemoryPublisher()
    publication = transport.prepare_and_publish_cells(
        canonical,
        season_replay_factory=replay_factory,
        publish=publisher,
        execution_provenance=PREP_PROVENANCE,
    )
    return Fixture(publication, publisher, rosters, tuple(calls))


def _smoke_completion() -> dict[str, object]:
    return {
        "disposition": transport.SMOKE_COMPLETION_DISPOSITION,
        "execution": {
            "state": "True",
            "counters": {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            },
        },
        "uses_realized_target_or_candidate_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }


def _smoke_freeze(prepared: shards.PreparedCell) -> dict[str, object]:
    return {
        "season": 2019,
        "week": 1,
        "block": "R0",
        "projection_seed": prepared.projection_seed,
        "source_environment_role_seed_nonoperative": (
            prepared.source_environment_role_seed_nonoperative
        ),
        "player_ids_sha256": prepared.player_ids_sha256,
        "player_draws": {"sha256": prepared.player_draws_sha256},
        "catalog_sha256": prepared.catalog_sha256,
        "incumbent_candidates_sha256": prepared.incumbent_candidates_sha256,
    }


def _terminal(
    execution: str,
    *,
    provenance: dict[str, object],
    command: list[str],
    args: list[str],
) -> dict[str, object]:
    return {
        "metadata": {
            "name": execution,
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": transport.JOB_UID,
                "run.googleapis.com/jobGeneration": provenance["job_generation"],
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": provenance["image"],
                    "command": command,
                    "args": args,
                    "env": [
                        {"name": key, "value": value}
                        for key, value in provenance["env"].items()
                    ],
                    "resources": {"limits": provenance["resources"]},
                }],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
        },
    }


def _parity_receipt() -> shards.ObjectReceipt:
    return transport._receipt({  # noqa: SLF001
        "uri": transport.SMOKE_PARITY_URI,
        "generation": "1",
        "sha256": "d" * 64,
        "bytes": 101,
    }, label="fixture parity")


def _cell_provenance(
    publication: transport.PreparedPublication,
) -> dict[str, object]:
    return transport.build_execution_provenance(
        mode="cell",
        code_sha=CODE_SHA,
        build_id=BUILD_ID,
        image=IMAGE,
        job_generation="3",
        job_spec_sha256="e" * 64,
        preparation_receipt=publication.manifest_receipt,
        parity_receipt=_parity_receipt(),
    )


def test_preparation_is_exact_70_and_replays_once_per_season(prepared_grid: Fixture):
    publication = prepared_grid.publication
    assert prepared_grid.replay_calls == (2019, 2021)
    assert len(publication.prepared_cells) == 70
    assert len(publication.cell_manifest_receipts) == 70
    assert len(publication.draw_receipts) == 70
    assert len(prepared_grid.publisher.objects) == 141
    validated = transport.validate_preparation_manifest(publication.manifest)
    assert validated["season_replay_invocations"] == [2019, 2021]
    assert validated["fit_count"] == 2
    assert validated["actual_score_queried"] is False

    first = publication.prepared_cells[0]
    cell_raw = prepared_grid.publisher.objects[
        transport.prepared_manifest_uri(0)
    ]
    draw_raw = prepared_grid.publisher.objects[transport.prepared_draw_uri(0)]
    reopened = transport._prepared_from_object(  # noqa: SLF001
        cell_raw,
        draw_metadata=publication.draw_receipts[0].as_dict(),
        draw_raw=draw_raw,
    )
    assert reopened.prepared_cell_sha256 == first.prepared_cell_sha256
    assert reopened.player_draws_bytes == first.player_draws_bytes


def test_smoke_gate_requires_exact_prepared_cell_parity(prepared_grid: Fixture):
    prepared = prepared_grid.publication.prepared_cells[0]
    parity = transport.validate_smoke_parity(
        smoke_completion=_smoke_completion(),
        smoke_solve_freeze=_smoke_freeze(prepared),
        prepared_cell=prepared,
    )
    assert parity["parity_exact"] is True
    assert parity["cell_execution_licensed"] is True
    assert parity["historical_scoring_licensed"] is False

    poison = _smoke_freeze(prepared)
    poison["player_draws"]["sha256"] = "0" * 64
    with pytest.raises(
        transport.LR8FullSourceTransportError, match="does not exactly match",
    ):
        transport.validate_smoke_parity(
            smoke_completion=_smoke_completion(),
            smoke_solve_freeze=poison,
            prepared_cell=prepared,
        )


def test_one_cell_attempt_is_create_once_and_harvest_is_terminal_first(
    prepared_grid: Fixture,
):
    prepared = prepared_grid.publication.prepared_cells[0]
    publisher = prepared_grid.publisher
    execution = transport.JOB + "-abcde"
    cell_provenance = _cell_provenance(prepared_grid.publication)
    expected_script = transport.cell_job_script(
        cell_index=0,
        preparation_receipt=prepared_grid.publication.manifest_receipt,
        parity_receipt=_parity_receipt(),
        provenance_args=transport._provenance_cli_args(  # noqa: SLF001
            cell_provenance
        ),
    )

    def solver(request: training.WorldSolveRequest):
        base = (
            transport.cell_result_prefix(0)
            + f"/solver-evidence/{request.request_sha256}"
        )
        model_raw = b"model"
        domain_raw = b'{"domain":"fixture"}\n'
        cbc = {
            "pulp_status": 1,
            "pulp_solution_status": 1,
            "threads": 1,
            "warm_start": False,
            "mip_start_sha256": None,
            "model_sha256": sha256(model_raw).hexdigest(),
            "variable_domain_manifest_sha256": sha256(domain_raw).hexdigest(),
        }
        roster = prepared_grid.rosters[
            request.world_index % training.UNIQUE_OPTIMA_PER_BLOCK
        ]
        proof_raw = transport._canonical_json({  # noqa: SLF001
            "schema": transport.exact_solvers.PROOF_SCHEMA,
            "solve_kind": transport.exact_solvers.TRAINING_SOLVE_KIND,
            "request_sha256": request.request_sha256,
            "result": {
                "roster": list(roster),
                "objective_micro": 0,
                "dk_classic_only": True,
                "incumbent_no_goods_enforced": True,
                "house_rules_applied": [],
            },
            "cbc_solve_evidence": [cbc],
        })
        receipts = (
            publisher(base + "/proof.json", proof_raw).receipt,
            publisher(base + "/00-cbc.log", b"log").receipt,
            publisher(base + "/00-model.sol", b"solution").receipt,
            publisher(base + "/00-model.mps", model_raw).receipt,
            publisher(
                base + "/00-variable-domain-manifest.json", domain_raw,
            ).receipt,
        )
        return training.ExactWorldOptimum(
            roster=roster,
            request_sha256=request.request_sha256,
            objective_micro=0,
            evidence_receipts=receipts,
            exact_optimal=True,
            canonical_roster_tiebreak=True,
            dk_classic_only=True,
            incumbent_no_goods_enforced=True,
        )

    solved = transport.solve_and_publish_cell(
        prepared,
        preparation_receipt=prepared_grid.publication.cell_manifest_receipts[0],
        prepared_execution_provenance=PREP_PROVENANCE,
        cell_execution_provenance=cell_provenance,
        execution=execution,
        job=transport.JOB,
        task_index=0,
        task_attempt=0,
        solve_world=solver,
        publish=publisher,
    )
    assert len(solved.shard.frozen_block.candidates) == 40
    assert solved.attempt_receipt.uri == transport.cell_attempt_uri(0)
    with pytest.raises(
        transport.LR8FullSourceTransportError, match="attempt already exists",
    ):
        transport.solve_and_publish_cell(
            prepared,
            preparation_receipt=prepared_grid.publication.cell_manifest_receipts[0],
            prepared_execution_provenance=PREP_PROVENANCE,
            cell_execution_provenance=cell_provenance,
            execution=execution,
            job=transport.JOB,
            task_index=0,
            task_attempt=0,
            solve_world=solver,
            publish=publisher,
        )

    events = []

    def terminal_loader(_execution: str):
        events.append("terminal")
        return _terminal(
            execution,
            provenance=cell_provenance,
            command=["bash"],
            args=["-ceu", expected_script],
        )

    def inventory_loader(prefix: str):
        events.append("inventory")
        return publisher.inventory(prefix)

    def object_loader(row: dict[str, object]):
        events.append("body")
        return publisher.load(row)

    harvested = transport.harvest_cell_after_terminal(
        cell_index=0,
        execution=execution,
        job="atlas-md-prefix-r4-smoke",
        prepared=prepared,
        source_manifest_receipt=prepared_grid.publication.manifest_receipt,
        cell_preparation_receipt=(
            prepared_grid.publication.cell_manifest_receipts[0]
        ),
        parity_receipt=_parity_receipt(),
        prepared_execution_provenance=PREP_PROVENANCE,
        cell_execution_provenance=cell_provenance,
        terminal_loader=terminal_loader,
        inventory_loader=inventory_loader,
        object_loader=object_loader,
    )
    assert events[:2] == ["terminal", "inventory"]
    assert all(value == "body" for value in events[2:])
    assert harvested.shard.shard_sha256 == solved.shard.shard_sha256

    attempt = transport._strict_json(  # noqa: SLF001
        publisher.objects[transport.cell_attempt_uri(0)], label="fixture attempt",
    )
    for poison in (
        {**attempt, "extra": True},
        {**attempt, "create_once_asserted": False},
        {**attempt, "create_once_asserted": 1},
        {**attempt, "automatic_retry_licensed": True},
        {**attempt, "task_index": False},
    ):
        with pytest.raises(
            transport.LR8FullSourceTransportError,
            match="schema or execution binding",
        ):
            transport.validate_attempt_payload(
                poison,
                prepared=prepared,
                preparation_receipt=(
                    prepared_grid.publication.cell_manifest_receipts[0]
                ),
                execution=execution,
                job=transport.JOB,
                prepared_execution_provenance=PREP_PROVENANCE,
                cell_execution_provenance=cell_provenance,
            )

    permuted_execution = transport.JOB + "-fghij"
    with pytest.raises(
        transport.LR8FullSourceTransportError,
        match="schema or execution binding",
    ):
        transport.harvest_cell_after_terminal(
            cell_index=0,
            execution=permuted_execution,
            job=transport.JOB,
            prepared=prepared,
            source_manifest_receipt=prepared_grid.publication.manifest_receipt,
            cell_preparation_receipt=(
                prepared_grid.publication.cell_manifest_receipts[0]
            ),
            parity_receipt=_parity_receipt(),
            prepared_execution_provenance=PREP_PROVENANCE,
            cell_execution_provenance=cell_provenance,
            terminal_loader=lambda _name: _terminal(
                permuted_execution,
                provenance=cell_provenance,
                command=["bash"],
                args=["-ceu", expected_script],
            ),
            inventory_loader=publisher.inventory,
            object_loader=publisher.load,
        )


def test_terminal_contract_rejects_retry_or_failure():
    execution = transport.JOB + "-abcde"
    command = ["python"]
    args = [
        *transport.preparation_job_args(),
        *transport._provenance_cli_args(PREP_PROVENANCE),  # noqa: SLF001
    ]
    value = _terminal(
        execution, provenance=PREP_PROVENANCE, command=command, args=args,
    )
    value["spec"]["template"]["spec"]["maxRetries"] = 1
    with pytest.raises(transport.LR8FullSourceTransportError, match="retry"):
        transport.strict_terminal(
            value,
            execution=execution,
            job=transport.JOB,
            execution_provenance=PREP_PROVENANCE,
            expected_command=command,
            expected_args=args,
        )
    value = _terminal(
        execution, provenance=PREP_PROVENANCE, command=command, args=args,
    )
    value["status"]["conditions"][0]["status"] = "False"
    with pytest.raises(transport.LR8FullSourceTransportError, match="terminal"):
        transport.strict_terminal(
            value,
            execution=execution,
            job=transport.JOB,
            execution_provenance=PREP_PROVENANCE,
            expected_command=command,
            expected_args=args,
        )


def test_provenance_and_terminal_bind_all_execution_fields():
    for key, poison in (
        ("code_sha", "f" * 40),
        ("build_id", "different-build-1234"),
        ("image", IMAGE[:-1] + "0"),
        ("job_uid", "different-job-uid"),
        ("job_generation", "9"),
        ("job_spec_sha256", "9" * 64),
        ("command", ["bash"]),
        ("args", ["different"]),
        ("env", {}),
        ("service_account", "different@example.invalid"),
        ("resources", {"cpu": "1", "memory": "1Gi"}),
        ("task_count", True),
        ("parallelism", 2),
        ("max_retries", 1),
    ):
        value = deepcopy(PREP_PROVENANCE)
        value[key] = poison
        with pytest.raises(transport.LR8FullSourceTransportError):
            transport.validate_execution_provenance(value)

    execution = transport.JOB + "-abcde"
    command = ["python"]
    args = [
        *transport.preparation_job_args(),
        *transport._provenance_cli_args(PREP_PROVENANCE),  # noqa: SLF001
    ]
    valid = _terminal(
        execution, provenance=PREP_PROVENANCE, command=command, args=args,
    )
    poisons = []
    for mutate in (
        lambda row: row["metadata"]["labels"].__setitem__(
            "run.googleapis.com/jobUid", "different"
        ),
        lambda row: row["metadata"]["labels"].__setitem__(
            "run.googleapis.com/jobGeneration", "9"
        ),
        lambda row: row["spec"].__setitem__("taskCount", True),
        lambda row: row["spec"].__setitem__("parallelism", 2),
        lambda row: row["spec"]["template"]["spec"].__setitem__(
            "maxRetries", 1
        ),
        lambda row: row["spec"]["template"]["spec"]["containers"][0].__setitem__(
            "image", IMAGE[:-1] + "0"
        ),
        lambda row: row["spec"]["template"]["spec"]["containers"][0].__setitem__(
            "command", ["bash"]
        ),
        lambda row: row["spec"]["template"]["spec"]["containers"][0].__setitem__(
            "args", ["different"]
        ),
        lambda row: row["spec"]["template"]["spec"]["containers"][0]["env"][0].__setitem__(
            "value", "different"
        ),
        lambda row: row["spec"]["template"]["spec"].__setitem__(
            "serviceAccountName", "different@example.invalid"
        ),
        lambda row: row["spec"]["template"]["spec"]["containers"][0][
            "resources"
        ].__setitem__("limits", {"cpu": "1", "memory": "1Gi"}),
    ):
        value = deepcopy(valid)
        mutate(value)
        poisons.append(value)
    for value in poisons:
        with pytest.raises(transport.LR8FullSourceTransportError):
            transport.strict_terminal(
                value,
                execution=execution,
                job=transport.JOB,
                execution_provenance=PREP_PROVENANCE,
                expected_command=command,
                expected_args=args,
            )


def _configured_job() -> dict[str, object]:
    return {
        "metadata": {
            "name": transport.JOB,
            "uid": transport.JOB_UID,
            "generation": 2,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": ["python"],
                    "args": list(transport.preparation_job_args()),
                    "env": [
                        {"name": key, "value": value}
                        for key, value in PREP_PROVENANCE["env"].items()
                    ],
                    "workingDir": "",
                    "volumeMounts": [],
                    "resources": {"limits": PREP_PROVENANCE["resources"]},
                }],
                "volumes": [],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        }}},
    }


def test_launch_contract_binds_generation_and_full_job_spec(tmp_path: Path):
    job = _configured_job()
    contract = finisher.create_launch_contract(
        mode="prepare",
        job_metadata=job,
        code_sha=CODE_SHA,
        build_id=BUILD_ID,
        image=IMAGE,
        output=tmp_path / "preparation-launch-contract.json",
    )
    assert contract["job_generation"] == "2"
    assert contract["job_spec_sha256"] == finisher._job_spec_sha256(job)
    for poison in (
        {**deepcopy(job), "metadata": {**job["metadata"], "generation": 3}},
        deepcopy(job),
    ):
        if poison["metadata"]["generation"] == 2:
            poison["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0]["args"] = ["different"]
        with pytest.raises(finisher.LR8FullSourceFinishError):
            finisher._validate_configured_contract(poison, provenance=contract)


def test_preparation_ledger_is_exact_three_fields_and_canonical(tmp_path: Path):
    execution = transport.JOB + "-abcde"
    path = tmp_path / "preparation-execution.txt"
    path.write_text(transport.ledger_line(
        transport.JOB, execution, transport.PREPARATION_URI,
    ))
    assert finisher.parse_preparation_ledger(path) == (
        transport.JOB, execution, transport.PREPARATION_URI,
    )
    for text in (
        f"{transport.JOB} {execution} {transport.PREPARATION_URI} extra\n",
        f"{transport.JOB} {execution} gs://wrong/object\n",
        f"{transport.JOB}  {execution} {transport.PREPARATION_URI}\n",
        transport.ledger_line(
            transport.JOB, execution, transport.PREPARATION_URI,
        ) + "extra\n",
    ):
        path.write_text(text)
        with pytest.raises(finisher.LR8FullSourceFinishError):
            finisher.parse_preparation_ledger(path)


def test_preparation_manifest_hash_must_match_reopened_cell(prepared_grid: Fixture):
    poison = deepcopy(prepared_grid.publication.manifest)
    poison["prepared_cells"][0]["prepared_cell_sha256"] = "0" * 64
    with pytest.raises(finisher.LR8FullSourceFinishError, match="prepared cell"):
        finisher._load_prepared_cells(
            prepared_grid.publisher,
            poison,
        )


def test_build_gate_requires_the_future_shared_integration_smokes():
    build_id = "12345678-abcd-abcd-abcd-123456789abc"
    code_sha = "a" * 40
    digest = "sha256:" + "b" * 64
    image = (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/"
        f"nfl-dfs/nfl-dfs@{digest}"
    )
    build = {
        "id": build_id,
        "status": "SUCCESS",
        "source": {"gitSource": {"revision": code_sha}},
        "sourceProvenance": {"resolvedGitSource": {"revision": code_sha}},
        "results": {"images": [{"digest": digest}]},
        "steps": [{
            "status": "SUCCESS",
            "exitCode": 0,
            "args": ["\n".join(finisher.REQUIRED_BUILD_SMOKES)],
        }],
    }
    finisher.validate_build_metadata(
        build, build_id=build_id, code_sha=code_sha, image=image,
    )
    build["steps"][0]["args"] = [finisher.REQUIRED_BUILD_SMOKES[0]]
    with pytest.raises(
        finisher.LR8FullSourceFinishError, match="integration smokes",
    ):
        finisher.validate_build_metadata(
            build, build_id=build_id, code_sha=code_sha, image=image,
        )


def test_shell_scaffold_reuses_one_job_and_emits_three_field_ledgers():
    launcher = (ROOT / "scripts/cloud_lr8_full_source_shards.sh").read_text()
    watcher = (
        ROOT / "scripts/watch_lr8_full_source_shards_queue.sh"
    ).read_text()
    assert "gcloud run jobs update" in launcher
    assert "gcloud run jobs execute" in launcher
    assert "gcloud run jobs create" not in launcher
    assert "gcloud run jobs delete" not in launcher
    assert "--tasks 1 --parallelism 1" in launcher
    assert "--max-retries 0" in launcher
    assert "for CELL_INDEX in $(seq 0 69)" in launcher
    assert "printf '%s %s %s\\n'" in launcher
    assert "prepared-identity" in launcher
    assert "configured-image" not in launcher
    assert "LR8_BUILD_ID=$BUILD_ID" in launcher
    assert "CELL_PROVENANCE_STRING" in launcher
    assert "historical_outcome_lease" not in launcher + watcher
    assert "preparation-ledger-arguments" in watcher
    assert "validate-cell-ledger" in watcher
    assert "finish-preparation" in watcher
    assert "finish-cells" in watcher
    assert transport.ledger_line(
        "atlas-md-prefix-r4-smoke",
        "atlas-md-prefix-r4-smoke-abcde",
        transport.cell_shard_uri(0),
    ).split() == [
        "atlas-md-prefix-r4-smoke",
        "atlas-md-prefix-r4-smoke-abcde",
        transport.cell_shard_uri(0),
    ]
