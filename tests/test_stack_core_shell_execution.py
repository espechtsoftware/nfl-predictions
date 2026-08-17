from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_stack_core_shell_scorefree import _validate_fold  # noqa: E402
from nfl_dfs.analysis.constraint_lattice import REPORT_THRESHOLDS  # noqa: E402
from nfl_dfs.analysis.stack_core_shell import VERSION  # noqa: E402
from run_stack_core_shell_scorefree import (  # noqa: E402
    SUPPORT_RUN_ID,
    SUPPORT_URI,
    _download_support,
)
from stack_core_shell_sources import PROTOCOL_SHA256  # noqa: E402


class _Blob:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.size = len(raw)
        self.generation = "123"
        self.updated = datetime(2026, 8, 17, tzinfo=timezone.utc)

    def reload(self) -> None:
        return None

    def download_as_bytes(self) -> bytes:
        return self.raw


class _Bucket:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def blob(self, _name: str) -> _Blob:
        return _Blob(self.raw)


class _Client:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def bucket(self, _name: str) -> _Bucket:
        return _Bucket(self.raw)


def _support_report() -> dict:
    return {
        "version": "stack-core-shell-control-support-report-v1",
        "run_id": SUPPORT_RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "protocol_sha256": PROTOCOL_SHA256,
        "mechanical": {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "worlds_per_fold": 10_000,
            "source_artifacts": 270, "all_valid": True,
        },
        "selected_anchor": 230,
        "adequate_by_threshold": {"230": True, "220": True, "210": True},
        "disposition": "p230-supported-stack-core-shell-treatment-licensed",
    }


def test_support_download_requires_complete_positive_receipt() -> None:
    report = _support_report()
    raw = (json.dumps(report, sort_keys=True) + "\n").encode()
    digest = sha256(raw).hexdigest()
    loaded, receipt = _download_support(_Client(raw), SUPPORT_URI, digest)
    assert loaded == report
    assert receipt["sha256"] == digest
    assert receipt["selected_anchor"] == 230
    assert receipt["generation"] == "123"

    report["treatment_constructed"] = True
    bad = (json.dumps(report, sort_keys=True) + "\n").encode()
    try:
        _download_support(_Client(bad), SUPPORT_URI, sha256(bad).hexdigest())
    except RuntimeError as exc:
        assert "support disposition differs" in str(exc)
    else:
        raise AssertionError("treatment-bearing support report was accepted")


def _roster(prefix: str) -> list[str]:
    return sorted(f"{prefix}-{index}" for index in range(9))


def _rank() -> dict:
    value = {
        "participation_ratio": 10.0,
        "entropy_effective_rank": 9.0,
        "top_five_variance_share": 0.5,
    }
    return {"covariance": dict(value), "correlation": dict(value)}


def _fold() -> dict:
    control = [_roster(f"control-{index}") for index in range(80)]
    cores = [{
        "players": list(control[index][:4]),
        "rank": [1.0] * 7,
        "parent": list(control[index]),
        "qb": control[index][0],
        "game": f"game-{index // 8}",
    } for index in range(32)]
    shells = [{
        "players": list(
            control[index // 2][:5]
            if index % 2 == 0 else control[index // 2][4:]
        ),
        "rank": [1.0] * 7,
        "parent": list(control[index // 2]),
    } for index in range(128)]
    proposals = []
    used_rosters = set()
    used_pairs = set()
    control_rosters = {tuple(row) for row in control}
    for index in range(40):
        core = cores[index % len(cores)]["players"]
        shell = next(
            row["players"] for row in shells
            if not set(core) & set(row["players"])
            and tuple(sorted([*core, *row["players"]])) not in used_rosters
            and tuple(sorted([*core, *row["players"]])) not in control_rosters
            and ({
                tuple(sorted((left, right)))
                for left in core for right in row["players"]
            } - used_pairs or index == 0)
        )
        roster = sorted([*core, *shell])
        used_rosters.add(tuple(roster))
        used_pairs.update(
            tuple(sorted((left, right))) for left in core for right in shell
        )
        proposals.append({
            "roster": roster,
            "core": core,
            "shell": shell,
            "rank": [1.0] * 7,
        })
    treatment = [*control[:79], proposals[0]["roster"]]
    counts = {
        str(int(line)): 100 for line in REPORT_THRESHOLDS
    }
    structure = {
        "unique_players": 100,
        "unique_player_pairs": 1000,
        "unique_qb_stack_cores": 50,
        "unique_dominant_games": 20,
    }
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": 2023,
        "week": 1,
        "heldout_block": "R0",
        "worlds": 10_000,
        "candidate_budget": 80,
        "selected_entries": 80,
        "candidate_shared_rosters": 79,
        "candidate_new_rosters": 1,
        "selected_shared_rosters": 79,
        "selected_new_rosters": 1,
        "admitted_proposals": 1,
        "proposal_counts": {
            "legal_crosses": 300,
            "existing_control_crosses": 10,
            "duplicate_crosses": 20,
            "unique_recombinants": 256,
            "covered_core_shell_pairs": len(used_pairs),
        },
        "threshold_counts": {
            layer: {book: dict(counts) for book in ("control", "treatment")}
            for layer in ("candidate", "selected")
        },
        "structure": {
            layer: {book: dict(structure) for book in ("control", "treatment")}
            for layer in ("candidate", "selected")
        },
        "score_effective_rank": {
            layer: {book: _rank() for book in ("control", "treatment")}
            for layer in ("candidate", "selected")
        },
        "candidate_control_rosters": control,
        "candidate_treatment_rosters": treatment,
        "selected_control_rosters": control,
        "selected_treatment_rosters": treatment,
        "training_blocks": ["R1", "R2", "R3", "R4"],
        "training_union_candidates": 100,
        "component_library": {
            "source_lineups": 80,
            "decompositions": 128,
            "discovered_cores": 64,
            "discovered_shells": 128,
            "retained_cores": 32,
            "retained_shells": 128,
            "core_qb_counts": {
                control[index][0]: 1 for index in range(32)
            },
            "core_game_counts": {f"game-{index}": 8 for index in range(4)},
            "cores": cores,
            "shells": shells,
        },
        "beam_candidates": 256,
        "proposal_candidates": 40,
        "proposals": proposals,
        "elapsed_seconds": 1.0,
    }


def test_strict_fold_validator_binds_fixed_mechanics_and_rosters() -> None:
    row = _fold()
    _validate_fold(row, season=2023, week=1, block="R0")
    row["proposal_counts"]["covered_core_shell_pairs"] = 58
    try:
        _validate_fold(row, season=2023, week=1, block="R0")
    except ValueError as exc:
        assert "proposal counts differ" in str(exc)
    else:
        raise AssertionError("under-covered proposal set was accepted")


def test_strict_fold_validator_rejects_unbound_admitted_roster() -> None:
    row = _fold()
    row["candidate_treatment_rosters"][-1] = _roster("not-a-proposal")
    row["selected_treatment_rosters"][-1] = _roster("not-a-proposal")
    try:
        _validate_fold(row, season=2023, week=1, block="R0")
    except ValueError as exc:
        assert "admitted proposal binding differs" in str(exc)
    else:
        raise AssertionError("unbound treatment roster was accepted")


def test_strict_fold_validator_binds_library_counts_and_components() -> None:
    row = _fold()
    qb_counts = row["component_library"]["core_qb_counts"]
    value = qb_counts.pop(next(iter(qb_counts)))
    qb_counts["fictional-qb"] = value
    try:
        _validate_fold(row, season=2023, week=1, block="R0")
    except ValueError as exc:
        assert "component identity repeats" in str(exc)
    else:
        raise AssertionError("unbound core QB counts were accepted")

    row = _fold()
    row["proposals"][0]["core"] = sorted(["not", "a", "retained", "core"])
    try:
        _validate_fold(row, season=2023, week=1, block="R0")
    except ValueError as exc:
        assert "proposal receipt differs" in str(exc)
    else:
        raise AssertionError("unbound proposal component was accepted")


def test_strict_fold_validator_binds_reported_pair_coverage() -> None:
    row = _fold()
    row["proposal_counts"]["covered_core_shell_pairs"] += 1
    try:
        _validate_fold(row, season=2023, week=1, block="R0")
    except ValueError as exc:
        assert "proposal counts differ" in str(exc)
    else:
        raise AssertionError("incorrect proposal pair coverage was accepted")
