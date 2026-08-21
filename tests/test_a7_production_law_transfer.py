from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from nfl_dfs.research import a7_production_law_transfer as science  # noqa: E402
import freeze_a7_production_law_transfer as freeze_builder  # noqa: E402
import run_a7_production_law_transfer as runner  # noqa: E402


def _licenses(*, shadow: bool = False) -> dict[str, bool]:
    values = {field: False for field in science.LICENSE_FIELDS}
    values["prospective_shadow_licensed"] = shadow
    return values


def _support(*, passed: bool = True) -> dict:
    cells = {
        "control": [20] * 5,
        "treatment": [20] * 5,
    }
    conditions = {
        "control_r3_events_at_least_100": True,
        "treatment_r3_events_at_least_100": True,
        "control_r3_supported_in_every_block": True,
        "treatment_r3_supported_in_every_block": True,
    }
    if not passed:
        cells["treatment"] = [0] * 5
        conditions["treatment_r3_events_at_least_100"] = False
        conditions["treatment_r3_supported_in_every_block"] = False
    return {
        "version": "a7-r3-support-census-v1",
        "uses_realized_outcomes": False,
        "slates": 54,
        "definition": (
            "positive-ladder-gain-events-with-at-least-3-strict-q99-"
            "exceedances"
        ),
        "minimum_aggregate_events_per_arm": science.a7.R3_SUPPORT_MIN_EVENTS,
        "r3_positive_gain_events_by_block": cells,
        "conditions": conditions,
        "passes": passed,
    }


def _inherited_gate(*, passed: bool) -> dict:
    conditions = {
        "treatment_nonvacuous": True,
        "aggregate_ladder_utility_strictly_improves": passed,
        "at_least_four_world_blocks_improve": True,
        "realism_r3_supported": True,
        "realism_r3_noninferior": True,
    }
    return {
        "protocol_id": science.a7.PROTOCOL_ID,
        "uses_realized_outcomes": False,
        "slates": 54,
        "changed_slates": 2,
        "ladder_utility": {"control": 10, "treatment": 11},
        "ladder_utility_by_block": {
            "control": [2] * 5, "treatment": [3] * 5,
        },
        "improved_world_blocks": 5,
        "realism": {},
        "support": {
            "uses_realized_outcomes": False,
            "passes": True,
        },
        "realism_r3_delta": 0.0,
        "realism_r3_exact_comparison": {
            "margin_numerator": 1,
            "margin_denominator": 100,
            "noninferior": True,
        },
        "conditions": conditions,
        "mechanics_passes": passed,
        "passes": passed,
    }


@pytest.mark.parametrize("passed", [False, True])
def test_transfer_wraps_the_unchanged_a7_gate(monkeypatch, passed: bool) -> None:
    inherited = _inherited_gate(passed=passed)
    calls = []
    monkeypatch.setattr(
        science.a7,
        "aggregate_scorefree",
        lambda rows: calls.append(rows) or deepcopy(inherited),
    )
    rows = [{"synthetic": True}] * 54
    result = science.aggregate_transfer(rows)
    assert calls == [rows]
    assert result["gate"] == inherited
    assert result["inherited_gate_unchanged"] is True
    assert result["uses_realized_outcomes"] is False
    assert result["actual_score_query_executed"] is False
    assert result["scorefree_transfer_passed"] is passed
    assert result["licenses"] == _licenses(shadow=passed)
    assert result["disposition"] == (
        science.PASS_DISPOSITION if passed else science.FAIL_DISPOSITION
    )


def test_inherited_gate_schema_and_pass_law_are_poison_closed(monkeypatch) -> None:
    value = _inherited_gate(passed=True)
    value["conditions"]["post_hoc_condition"] = True
    monkeypatch.setattr(science.a7, "aggregate_scorefree", lambda rows: value)
    with pytest.raises(ValueError, match="conditions differ"):
        science.aggregate_transfer([{}] * 54)

    value = _inherited_gate(passed=True)
    value["passes"] = False
    monkeypatch.setattr(science.a7, "aggregate_scorefree", lambda rows: value)
    with pytest.raises(ValueError, match="pass law differs"):
        science.aggregate_transfer([{}] * 54)


def _write_positive_a7(out: Path) -> tuple[dict, str]:
    report = {
        "version": "a7-select-ladder-phase-s-incumbent-v2",
        "run_id": runner.a7_transport.RUN_ID,
        "protocol_sha256": runner.A7_PROTOCOL_SHA256,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "production_law_scorefree_transfer_licensed": True,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
        "outcome": {
            "disposition": "historical-positive-phase-s",
            "production_law_scorefree_transfer_licensed": True,
            "prospective_shadow_licensed": False,
            "production_change_licensed": False,
        },
    }
    raw = runner._canonical_json(report)
    digest = sha256(raw).hexdigest()
    out.mkdir()
    (out / "report.json").write_bytes(raw)
    (out / "completion.txt").write_text(
        "\n".join((
            f"run_id={runner.a7_transport.RUN_ID}",
            "disposition=historical-positive-phase-s",
            "strict_science_replay=true",
            "uses_realized_outcomes=true",
            "actual_score_query_executed=true",
            "production_change_licensed=false",
            "prospective_shadow_licensed=false",
            "historical_outcome_lease_released=false",
            f"report_sha256={digest}",
        )) + "\n",
        encoding="utf-8",
    )
    (out / "lease-release.txt").write_text("closed\n", encoding="utf-8")
    (out / "finish.sha256").write_text("finished\n", encoding="utf-8")
    return report, digest


def _closed(digest: str) -> dict:
    return {
        "status": "already-closed",
        "run_id": runner.a7_transport.RUN_ID,
        "disposition": "historical-positive-phase-s",
        "report_sha256": digest,
        "lease_action": "released-after-realized-outcome",
        "lease_receipt_sha256": "a" * 64,
    }


def test_exact_final_a7_positive_receipt_is_required(tmp_path: Path) -> None:
    out = tmp_path / "a7"
    _, digest = _write_positive_a7(out)
    receipt = runner.validate_a7_positive_license(
        out, closed_validator=lambda path: _closed(digest),
    )
    assert receipt["disposition"] == "historical-positive-phase-s"
    assert receipt["production_law_scorefree_transfer_licensed"] is True
    assert receipt["prospective_shadow_licensed"] is False
    assert receipt["production_change_licensed"] is False
    assert receipt["report"] == {
        "name": "report.json", "sha256": digest,
        "bytes": len((out / "report.json").read_bytes()),
    }


@pytest.mark.parametrize(
    "poison",
    ("negative-closure", "shadow-license", "noncanonical-report"),
)
def test_a7_predecessor_poison_fails_closed(
    tmp_path: Path, poison: str,
) -> None:
    out = tmp_path / "a7"
    report, digest = _write_positive_a7(out)
    closed = _closed(digest)
    if poison == "negative-closure":
        closed["disposition"] = "historical-null-or-inconclusive-phase-s"
    elif poison == "shadow-license":
        report["prospective_shadow_licensed"] = True
        raw = runner._canonical_json(report)
        (out / "report.json").write_bytes(raw)
        digest = sha256(raw).hexdigest()
        closed["report_sha256"] = digest
        completion = (out / "completion.txt").read_text(encoding="utf-8")
        completion = re_sub_report_sha(completion, digest)
        (out / "completion.txt").write_text(completion, encoding="utf-8")
    else:
        raw = (out / "report.json").read_bytes()
        (out / "report.json").write_bytes(raw.rstrip() + b"   \n")
    with pytest.raises(RuntimeError, match="does not license|not canonical"):
        runner.validate_a7_positive_license(
            out, closed_validator=lambda path: closed,
        )


def re_sub_report_sha(text: str, digest: str) -> str:
    rows = []
    for line in text.splitlines():
        rows.append(
            f"report_sha256={digest}"
            if line.startswith("report_sha256=") else line
        )
    return "\n".join(rows) + "\n"


def test_predecessor_gate_runs_before_any_cloud_client(monkeypatch) -> None:
    calls: list[str] = []

    def reject(path):
        calls.append("predecessor")
        raise RuntimeError("not positive")

    monkeypatch.setattr(runner, "validate_a7_positive_license", reject)
    monkeypatch.setattr(
        runner.storage, "Client", lambda **kwargs: calls.append("storage"),
    )
    monkeypatch.setattr(
        runner.bigquery, "Client", lambda **kwargs: calls.append("bigquery"),
    )
    with pytest.raises(RuntimeError, match="not positive"):
        runner.run(
            mode="real-artifact-smoke",
            output_uri=runner.SMOKE_OUTPUT_URI,
        )
    assert calls == ["predecessor"]


def test_source_queries_are_scorefree_and_protocol_is_exact() -> None:
    runner.validate_scorefree_queries()
    combined = f"{runner.CANDIDATE_SQL}\n{runner.PLAYER_SQL}".lower()
    assert not any(token in combined for token in runner.FORBIDDEN_QUERY_TOKENS)
    assert "all_tags" in runner.CANDIDATE_SQL
    assert "@repair_panel" in runner.CANDIDATE_SQL
    protocol = ROOT / runner.PROTOCOL
    assert sha256(protocol.read_bytes()).hexdigest() == runner.PROTOCOL_SHA256
    assert runner.SOURCE_LOCK_SHA256 == (
        "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
    )


def _small_source(monkeypatch):
    panels = tuple(f"panel-{index}" for index in range(5))
    monkeypatch.setattr(runner, "SOURCE_PANELS", panels)
    monkeypatch.setattr(runner, "FULL_SLATES", ((2023, 1),))
    monkeypatch.setattr(runner, "ARTIFACT_COUNT", 5)
    monkeypatch.setattr(runner, "CATALOG_ROWS", 9)
    roster = [f"p{index}" for index in range(9)]
    artifacts = []
    rows = []
    for seed, panel in enumerate(panels):
        uri = f"gs://source/{panel}.npz"
        digest = sha256(uri.encode()).hexdigest()
        artifacts.append({
            "panel_run_id": panel,
            "season": 2023,
            "week": 1,
            "seed": seed,
            "candidate_rows": 1,
            "uri": uri,
            "sha256": digest,
        })
        rows.append({
            "panel_run_id": panel,
            "season": 2023,
            "week": 1,
            "cand_ix": 0,
            "tag": "boom",
            "all_tags": '["boom"]',
            "players": ",".join(roster),
            "score_artifact_uri": uri,
            "score_artifact_sha256": digest,
        })
    catalog = [{
        "season": 2023,
        "week": 1,
        "player_id": player_id,
        "position": "WR",
        "team": "AAA",
        "mean_projection": 10.0,
    } for player_id in roster]
    return panels, artifacts, catalog, pd.DataFrame(rows, columns=runner.CANDIDATE_COLUMNS)


def test_candidate_grid_binds_rosters_artifacts_and_locked_union(monkeypatch) -> None:
    panels, artifacts, catalog, frame = _small_source(monkeypatch)
    groups = runner._validate_candidate_source(frame, artifacts, catalog)
    assert set(groups) == {(panel, 2023, 1) for panel in panels}
    poisoned = frame.copy()
    poisoned.loc[0, "players"] = "p0,p1,p2,p3,p4,p5,p6,p7,poison"
    with pytest.raises(RuntimeError, match="candidate population differs"):
        runner._validate_candidate_source(poisoned, artifacts, catalog)


def test_player_grid_binds_full_legality_fields_to_locked_catalog(monkeypatch) -> None:
    monkeypatch.setattr(runner, "FULL_SLATES", ((2023, 1),))
    rows = [{
        "season": 2023,
        "week": 1,
        "player_id": f"p{index}",
        "player_name": f"Player {index}",
        "position": "WR",
        "team": "AAA",
        "opponent": "BBB",
        "game_id": "AAA-BBB",
        "salary": 5000,
        "mean_projection": 10.0,
    } for index in range(9)]
    frame = pd.DataFrame(rows, columns=runner.PLAYER_COLUMNS)
    locked = [{
        "season": row["season"], "week": row["week"],
        "player_id": row["player_id"], "position": row["position"],
        "team": row["team"], "mean_projection": row["mean_projection"],
    } for row in rows]
    assert len(runner._validate_player_source(frame, locked)) == 9
    poisoned = deepcopy(locked)
    poisoned[0]["team"] = "CCC"
    with pytest.raises(RuntimeError, match="locked catalog differs"):
        runner._validate_player_source(frame, poisoned)


def _preflight_report(
    *, mode: str, predecessor: dict, code_sha: str, image: str,
    candidate_sha: str, player_sha: str, prior: dict,
) -> dict:
    smoke = mode == "real-artifact-smoke"
    support = None if smoke else _support()
    return {
        "version": runner.VERSION,
        "run_id": runner.RUN_ID,
        "mode": mode,
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "code_sha": code_sha,
        "image": image,
        "predecessor_license": predecessor,
        "preflight_receipts": prior,
        "execution_freeze": None,
        "source_query_receipts": {
            "candidates": {"sha256": candidate_sha},
            "players": {"sha256": player_sha},
        },
        "scope": [[2023, 1]] if smoke else [
            [season, week] for season, week in runner.FULL_SLATES
        ],
        "source_artifacts": [{}] * (5 if smoke else runner.ARTIFACT_COUNT),
        "support": support,
        "transfer_gate": None,
        "decision": (
            science.smoke_disposition()
            if smoke else science.support_disposition(support)
        ),
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
    }


def _object(uri: str, marker: str) -> dict:
    return {
        "uri": uri,
        "generation": "123",
        "metageneration": "1",
        "sha256": marker * 64,
        "bytes": 100,
    }


def test_pinned_preflights_and_freeze_bind_same_image_support(
    monkeypatch,
) -> None:
    predecessor = {"positive": True}
    code_sha = "a" * 40
    image = "example@sha256:" + "b" * 64
    candidate_sha, player_sha = "c" * 64, "d" * 64
    smoke = _preflight_report(
        mode="real-artifact-smoke", predecessor=predecessor,
        code_sha=code_sha, image=image, candidate_sha=candidate_sha,
        player_sha=player_sha, prior={},
    )
    smoke_identity = _object(runner.SMOKE_OUTPUT_URI, "e")
    support_identity = _object(runner.SUPPORT_OUTPUT_URI, "f")
    support = _preflight_report(
        mode="support-census", predecessor=predecessor,
        code_sha=code_sha, image=image, candidate_sha=candidate_sha,
        player_sha=player_sha, prior={"smoke": smoke_identity},
    )
    objects = {
        runner.SMOKE_OUTPUT_URI: (smoke, smoke_identity),
        runner.SUPPORT_OUTPUT_URI: (support, support_identity),
    }
    monkeypatch.setattr(
        runner,
        "_a7_download_json_object_pinned",
        lambda client, identity: objects[identity["uri"]],
    )
    _, observed_smoke = runner._load_pinned_preflight(
        object(), smoke_identity, uri=runner.SMOKE_OUTPUT_URI,
        mode="real-artifact-smoke", predecessor=predecessor,
        code_sha=code_sha, image=image,
        expected_candidate_sha256=candidate_sha,
        expected_player_sha256=player_sha,
        expected_preflight_receipts={},
    )
    runner._load_pinned_preflight(
        object(), support_identity, uri=runner.SUPPORT_OUTPUT_URI,
        mode="support-census", predecessor=predecessor,
        code_sha=code_sha, image=image,
        expected_candidate_sha256=candidate_sha,
        expected_player_sha256=player_sha,
        expected_preflight_receipts={"smoke": observed_smoke},
    )
    manifest = freeze_builder.build_manifest(
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        candidate_query_sha256=candidate_sha,
        player_query_sha256=player_sha,
        smoke_object=smoke_identity,
        support_object=support_identity,
    )
    assert manifest["support_passed"] is True
    assert manifest["licenses"] == _licenses()
    assert manifest["shadow_deployment_licensed"] is False

    poisoned = deepcopy(manifest)
    poisoned["preflights"]["smoke"]["metageneration"] = "2"
    with pytest.raises(RuntimeError, match="preflight identity differs"):
        runner._validate_freeze_manifest(
            poisoned,
            predecessor=predecessor,
            code_sha=code_sha,
            image=image,
            candidate_query_sha256=candidate_sha,
            player_query_sha256=player_sha,
        )


def test_support_schema_poison_fails_before_freeze() -> None:
    support = _support()
    assert science.support_disposition(support)[
        "full_execution_freeze_licensed"
    ] is True
    support["conditions"]["control_r3_events_at_least_100"] = False
    with pytest.raises(ValueError, match="support census differs"):
        science.support_disposition(support)


def test_freeze_predecessor_gate_runs_before_storage_client(monkeypatch) -> None:
    calls: list[str] = []

    def reject(path):
        calls.append("predecessor")
        raise RuntimeError("not positive")

    monkeypatch.setattr(runner, "validate_a7_positive_license", reject)
    monkeypatch.setattr(
        freeze_builder.storage,
        "Client",
        lambda **kwargs: calls.append("storage"),
    )
    with pytest.raises(RuntimeError, match="not positive"):
        freeze_builder.freeze(
            output_uri=runner.FREEZE_MANIFEST_URI,
            code_sha="a" * 40,
            image="example@sha256:" + "b" * 64,
            candidate_query_sha256="c" * 64,
            player_query_sha256="d" * 64,
            smoke_generation="1",
            smoke_sha256="e" * 64,
            smoke_bytes=1,
            support_generation="2",
            support_sha256="f" * 64,
            support_bytes=1,
        )
    assert calls == ["predecessor"]


def test_container_and_cloudbuild_package_the_successor() -> None:
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "cloudbuild.yaml Dockerfile ./" in docker
    for name in (
        "run_a7_production_law_transfer.py",
        "freeze_a7_production_law_transfer.py",
    ):
        assert docker.count(name) == 2
        assert f"python scripts/{name} --help" in cloudbuild
