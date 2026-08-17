"""Exact outcome-free generation schedule for the same-law capacity curve."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping, Sequence

from .same_law_capacity_curve import BOOK_ORDER, validate_seed_ledger


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SOURCE_CODE_SHA = "4d6f5cf"
SOURCE_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:757f0784937492c23917c245b082e052508fcac693840a1469e0020257fad6a4"
)
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
POSITION_SCALES = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
SEASONS = tuple(POSITION_SCALES)
NEW_BOOKS = BOOK_ORDER[5:]
COMMON_ENV = {
    "GCP_PROJECT": PROJECT,
    "GAME_SIM_MODE": "possession",
    "MODEL_ENSEMBLE": "1",
    "TABPFN_MARGINALS": "1",
    "TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v2",
    "EPISTEMIC_FAMILY": "role_draws",
    "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
    "REPLACEMENT_SLOTS": "12",
    "N_CE": "0",
    "N_EPISTEMIC": "12",
    "N_GUMBEL": "0",
    "N_BOOM": "40",
    "GAME_SIM_USAGE": "dirichlet",
    "DIRICHLET_K": "28.154043586960896",
    "SIS_ASOE_TARGET_ALLOCATION": "1",
    "SIS_ASOE_BETA": "0.07771181538347656",
    "CODE_SHA": SOURCE_CODE_SHA,
    "CAND_LOG_TABLE": f"{PROJECT}.nfl_predictions.replay_candidates_staging",
    "CAND_FEATURE_TABLE": f"{PROJECT}.nfl_predictions.slate_player_features",
    "CAND_ARTIFACT_BUCKET": f"{PROJECT}-raw",
    "CAND_ARTIFACT_PLAYER_WORLDS": "1",
}


@dataclass(frozen=True)
class GenerationCell:
    replicate: str
    season: int
    panel_run_id: str
    job: str
    lineups_table: str
    projection_seed: int
    role_seed: int
    image: str
    code_sha: str
    command: tuple[str, ...]
    args: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    cpu: int = 8
    memory: str = "32Gi"
    max_retries: int = 0
    timeout_seconds: int = 14_400

    def receipt(self) -> dict[str, Any]:
        value = asdict(self)
        value["command"] = list(self.command)
        value["args"] = list(self.args)
        value["environment"] = dict(self.environment)
        return value


def _replicate_index(replicate: str) -> int:
    if not re.fullmatch(r"R(?:[5-9]|[1-4][0-9])", replicate):
        raise ValueError("capacity generation replicate must be R5--R49")
    index = int(replicate[1:])
    if BOOK_ORDER[index] != replicate:
        raise ValueError("capacity generation replicate is noncanonical")
    return index


def panel_id(replicate: str) -> str:
    index = _replicate_index(replicate)
    return f"20260817-same-law-capacity-r{index:02d}-v1"


def job_name(replicate: str, season: int) -> str:
    index = _replicate_index(replicate)
    if season not in SEASONS:
        raise ValueError("capacity generation season differs")
    return f"capacity-r{index:02d}-{season}-v1"


def lineups_table(replicate: str, season: int) -> str:
    index = _replicate_index(replicate)
    if season not in SEASONS:
        raise ValueError("capacity generation season differs")
    return (
        f"{PROJECT}.nfl_features."
        f"replay_lineups_same_law_capacity_r{index:02d}_{season}_v1"
    )


def render_environment(
    *,
    replicate: str,
    season: int,
    projection_seed: int,
    role_seed: int,
) -> dict[str, str]:
    if season not in SEASONS:
        raise ValueError("capacity generation season differs")
    index = _replicate_index(replicate)
    if not (
        0 <= int(projection_seed) < 2**32 and 0 <= int(role_seed) < 2**32
    ):
        raise ValueError("capacity generation seed leaves uint32 range")
    env = dict(COMMON_ENV)
    env.update({
        "ROLE_BELIEF_SEED": str(int(role_seed)),
        "REPLAY_PROJECTION_SEED": str(int(projection_seed)),
        "SERVED_POSITION_SCALES": POSITION_SCALES[season],
        "PANEL_RUN_ID": f"20260817-same-law-capacity-r{index:02d}-v1",
        "REPLAY_LINEUPS_TABLE": lineups_table(replicate, season),
    })
    return env


def generation_schedule(seed_ledger: Any) -> list[GenerationCell]:
    """Return the exact canary-first 135-cell schedule from a valid ledger."""
    records = validate_seed_ledger(seed_ledger)
    by_replicate = {row["replicate"]: row for row in records}
    output: list[GenerationCell] = []
    for replicate in NEW_BOOKS:
        seeds = by_replicate[replicate]
        for season in SEASONS:
            environment = render_environment(
                replicate=replicate,
                season=season,
                projection_seed=seeds["projection_seed"],
                role_seed=seeds["role_seed"],
            )
            output.append(GenerationCell(
                replicate=replicate,
                season=season,
                panel_run_id=panel_id(replicate),
                job=job_name(replicate, season),
                lineups_table=lineups_table(replicate, season),
                projection_seed=int(seeds["projection_seed"]),
                role_seed=int(seeds["role_seed"]),
                image=SOURCE_IMAGE,
                code_sha=SOURCE_CODE_SHA,
                command=("nfl-dfs",),
                args=(
                    "replay", "--season", str(season), "--contest", "gpp",
                    "--entries", "80",
                ),
                environment=tuple(sorted(environment.items())),
            ))
    validate_generation_schedule(output)
    return output


def validate_generation_schedule(cells: Sequence[GenerationCell]) -> None:
    if len(cells) != 135:
        raise ValueError("capacity generation schedule must contain 135 cells")
    expected = [
        (replicate, season) for replicate in NEW_BOOKS for season in SEASONS
    ]
    observed = [(cell.replicate, cell.season) for cell in cells]
    if observed != expected or observed[0] != ("R5", 2023):
        raise ValueError("capacity generation schedule order/grid differs")
    if len({cell.job for cell in cells}) != 135 or \
            len({cell.lineups_table for cell in cells}) != 135:
        raise ValueError("capacity generation destinations repeat")
    if len({cell.panel_run_id for cell in cells}) != 45:
        raise ValueError("capacity generation panel population differs")
    for cell in cells:
        expected_env = render_environment(
            replicate=cell.replicate,
            season=cell.season,
            projection_seed=cell.projection_seed,
            role_seed=cell.role_seed,
        )
        if cell.image != SOURCE_IMAGE or cell.code_sha != SOURCE_CODE_SHA or \
                cell.command != ("nfl-dfs",) or cell.args != (
                    "replay", "--season", str(cell.season), "--contest", "gpp",
                    "--entries", "80",
                ) or dict(cell.environment) != expected_env or \
                cell.panel_run_id != panel_id(cell.replicate) or \
                cell.job != job_name(cell.replicate, cell.season) or \
                cell.lineups_table != lineups_table(cell.replicate, cell.season) or \
                (cell.cpu, cell.memory, cell.max_retries, cell.timeout_seconds) != (
                    8, "32Gi", 0, 14_400,
                ):
            raise ValueError("capacity generation cell contract differs")


def environment_delta(
    left: Mapping[str, str], right: Mapping[str, str],
) -> set[str]:
    """Return keys whose values differ, including one-sided keys."""
    return {
        key for key in set(left) | set(right) if left.get(key) != right.get(key)
    }


__all__ = [
    "COMMON_ENV",
    "GenerationCell",
    "NEW_BOOKS",
    "POSITION_SCALES",
    "PROJECT",
    "REGION",
    "SEASONS",
    "SOURCE_CODE_SHA",
    "SOURCE_IMAGE",
    "environment_delta",
    "generation_schedule",
    "job_name",
    "lineups_table",
    "panel_id",
    "render_environment",
    "validate_generation_schedule",
]
