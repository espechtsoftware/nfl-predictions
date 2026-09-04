"""Fail-closed adapter for the lab Week-1 D800/D400 live-run artifacts.

The lab generator emits local Parquet/CSV/JSON files.  The production adopted-
pair contract accepts canonical lineup and candidate identities.  This module
bridges those shapes without publishing anything: it verifies the exact live
recipe, active-roster eligibility, paired input/frame identity, full candidate
membership, D400-within-D800 containment, and exact selected CSV order before
building the two canonical book payloads.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import pandas as pd

from . import week1_adopted_pair as adopted_pair
from . import week1_adopted_pair_operator as pair_operator
from .generation_exposure import canonical_sha256

SCHEMA_VERSION: Final = "week1-live-pair-adapter/v1"
ACTIVE_POLICY: Final = "target-week-active-skill-allowlist-v1"
BOOK_HEADER: Final = tuple(pair_operator.DK_SLOT_ORDER)
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_FLEX: Final = frozenset({"RB", "WR", "TE"})
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class Week1LivePairAdapterError(ValueError):
    """The local live-run pair cannot become the Week-1 authority."""


def _fail(message: str) -> None:
    raise Week1LivePairAdapterError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be a mapping")
    return dict(value)


def _file_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _canonical_roster(raw: object, *, label: str) -> list[str]:
    if type(raw) is not str:
        _fail(f"{label} roster must be a comma-delimited string")
    roster = raw.split(",")
    if len(roster) != 9 or len(set(roster)) != 9 or roster != sorted(roster):
        _fail(f"{label} roster must contain nine unique sorted player IDs")
    if any(not player_id or player_id.strip() != player_id for player_id in roster):
        _fail(f"{label} roster contains a noncanonical player ID")
    return roster


def _lineup_id(roster: Sequence[str]) -> str:
    return f"lineup-v1-{canonical_sha256(list(roster))}"


def _validate_receipt(
    value: object, *, arm_id: str, lev: int, boom: int, candidates: int
) -> dict[str, object]:
    receipt = _mapping(value, label=f"{arm_id} receipt")
    identity = _mapping(receipt.get("identity"), label=f"{arm_id} code identity")
    source_sha = identity.get("sha")
    if (
        type(source_sha) is not str
        or _SHA40.fullmatch(source_sha) is None
        or identity.get("dirty") is not False
        or identity.get("diff_sha256") is not None
    ):
        _fail(f"{arm_id} was not produced from one clean Git commit")
    if (
        receipt.get("season") != 2026
        or receipt.get("week") != 1
        or receipt.get("draft_group") != 151307
        or str(receipt.get("lock_utc")) != "2026-09-13 17:00:00+00:00"
        or receipt.get("candidates") != candidates
        or receipt.get("written") != 80
        or receipt.get("book_k80_is_nested_prefix") is not True
    ):
        _fail(f"{arm_id} slate, census, or exact-K boundary differs")
    config = _mapping(receipt.get("config"), label=f"{arm_id} config")
    expected_config = {
        "lev": lev,
        "boom": boom,
        "k": 1,
        "operational_k": 80,
        "sims": 10_000,
        "seed": 2026,
        "selector": "dual_emax",
        "hsim_seed": 2326,
        "hsim_worlds": 10_000,
    }
    if any(config.get(key) != expected for key, expected in expected_config.items()):
        _fail(f"{arm_id} does not implement the frozen dual-EMAX recipe")
    banks = _mapping(receipt.get("banks"), label=f"{arm_id} banks")
    if banks != {
        "generation_seed": 2026,
        "selection_seed": 2076,
        "audit_seed": 2126,
        "independent_event_randomness": True,
        "shifted_to_identical_means": True,
    }:
        _fail(f"{arm_id} bank contract differs")
    inputs = _mapping(receipt.get("inputs"), label=f"{arm_id} inputs")
    status = _mapping(
        inputs.get("roster_status_invariant"),
        label=f"{arm_id} roster eligibility receipt",
    )
    if (
        status.get("eligibility_policy") != ACTIVE_POLICY
        or status.get("required_skill_status") != "ACT"
        or status.get("kept_nonact_skill_statuses") != {}
    ):
        _fail(f"{arm_id} did not use the active-skill allowlist")
    if not isinstance(inputs.get("content_hashes"), Mapping):
        _fail(f"{arm_id} input content hashes are absent")
    return receipt


def _player_bridge(
    frame: pd.DataFrame,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    required = {"id", "dk_player_id", "pos", "team", "salary", "roster_status"}
    if required - set(frame.columns) or frame.empty:
        _fail("live frame is empty or lacks player-authority fields")
    rows: list[dict[str, object]] = []
    dk_to_player: dict[str, str] = {}
    seen: set[str] = set()
    for ordinal, row in enumerate(frame.itertuples(index=False)):
        player_id = str(row.id)
        position = str(row.pos)
        team = str(row.team)
        salary_raw = row.salary
        roster_status = row.roster_status
        dk_raw = row.dk_player_id
        if (
            not player_id
            or player_id in seen
            or position not in _POSITIONS
            or not team
            or pd.isna(salary_raw)
            or int(salary_raw) < 1
            or pd.isna(dk_raw)
        ):
            _fail(f"live frame row {ordinal} has invalid player facts")
        if position != "DST" and (
            pd.isna(roster_status) or str(roster_status) != "ACT"
        ):
            _fail(f"live frame retains non-ACT skill player {player_id}")
        dk_player_id = str(int(dk_raw))
        if dk_player_id in dk_to_player:
            _fail("live frame repeats a DraftKings player ID")
        seen.add(player_id)
        dk_to_player[dk_player_id] = player_id
        rows.append(
            {
                "player_id": player_id,
                "position": position,
                "team": team,
                "salary": int(salary_raw),
            }
        )
    rows.sort(key=lambda row: str(row["player_id"]))
    return rows, dk_to_player


def _validate_candidate_pool(
    candidates: pd.DataFrame,
    *,
    expected_count: int,
    bridge: Mapping[str, Mapping[str, object]],
    arm_id: str,
) -> tuple[list[str], list[list[str]], dict[int, int]]:
    required = {"players", "book_rank"}
    if required - set(candidates.columns) or len(candidates) != expected_count:
        _fail(f"{arm_id} candidate schema or census differs")
    candidate_ids: list[str] = []
    rosters: list[list[str]] = []
    selected: dict[int, int] = {}
    for ordinal, row in enumerate(candidates.itertuples(index=False)):
        roster = _canonical_roster(row.players, label=f"{arm_id} candidate {ordinal}")
        if any(player_id not in bridge for player_id in roster):
            _fail(f"{arm_id} candidate {ordinal} leaves the active player bridge")
        positions = Counter(str(bridge[player_id]["position"]) for player_id in roster)
        salary = sum(int(bridge[player_id]["salary"]) for player_id in roster)
        teams = Counter(str(bridge[player_id]["team"]) for player_id in roster)
        if (
            positions["QB"] != 1
            or positions["RB"] < 2
            or positions["WR"] < 3
            or positions["TE"] < 1
            or positions["DST"] != 1
            or salary > 50_000
            or len(teams) < 2
            or max(teams.values()) > 8
        ):
            _fail(f"{arm_id} candidate {ordinal} is not DK Classic legal")
        lineup_id = _lineup_id(roster)
        if lineup_id in candidate_ids:
            _fail(f"{arm_id} candidate pool repeats a roster")
        candidate_ids.append(lineup_id)
        rosters.append(roster)
        rank_raw = row.book_rank
        if not pd.isna(rank_raw):
            rank = int(rank_raw)
            if float(rank_raw) != rank or rank in selected:
                _fail(f"{arm_id} selected rank is noncanonical or repeated")
            selected[rank] = ordinal
    if set(selected) != set(range(1, 81)):
        _fail(f"{arm_id} does not contain exact selected ranks 1..80")
    return candidate_ids, rosters, selected


def _build_book(
    *,
    arm_id: str,
    bridge_rows: list[dict[str, object]],
    dk_to_player: Mapping[str, str],
    rosters: Sequence[Sequence[str]],
    selected: Mapping[int, int],
    csv_rows: Sequence[Sequence[str]],
) -> dict[str, object]:
    if len(csv_rows) != 80 or any(len(row) != 9 for row in csv_rows):
        _fail(f"{arm_id} upload CSV is not exact K80 x nine slots")
    bridge = {str(row["player_id"]): row for row in bridge_rows}
    lineups: list[dict[str, object]] = []
    for rank, raw_slots in enumerate(csv_rows, start=1):
        try:
            slot_players = [dk_to_player[str(value)] for value in raw_slots]
        except KeyError as exc:
            raise Week1LivePairAdapterError(
                f"{arm_id} CSV references a player outside the bridge"
            ) from exc
        roster = list(rosters[selected[rank]])
        if set(slot_players) != set(roster) or len(set(slot_players)) != 9:
            _fail(f"{arm_id} CSV row {rank} differs from selected candidate rank")
        for slot, player_id in zip(BOOK_HEADER, slot_players, strict=True):
            position = str(bridge[player_id]["position"])
            if (slot == "FLEX" and position not in _FLEX) or (
                slot != "FLEX" and position != slot
            ):
                _fail(f"{arm_id} CSV row {rank} has an ineligible {slot}")
        lineups.append(
            {
                "lineup_id": _lineup_id(roster),
                "player_ids": roster,
                "slots": [
                    {"slot": slot, "player_id": player_id}
                    for slot, player_id in zip(BOOK_HEADER, slot_players, strict=True)
                ],
                "salary": sum(int(bridge[player_id]["salary"]) for player_id in roster),
            }
        )
    bridge_identity = {
        "id": "player-bridge/v1",
        "sha256": canonical_sha256(bridge_rows),
    }
    return pair_operator.build_week1_adopted_book_v1(
        arm_id=arm_id,
        player_bridge_identity=bridge_identity,
        player_bridge=bridge_rows,
        lineups=lineups,
    )


def adapt_week1_live_pair_v1(
    *,
    paid_receipt: object,
    shadow_receipt: object,
    paid_frame: pd.DataFrame,
    shadow_frame: pd.DataFrame,
    paid_candidates: pd.DataFrame,
    shadow_candidates: pd.DataFrame,
    paid_csv_rows: Sequence[Sequence[str]],
    shadow_csv_rows: Sequence[Sequence[str]],
    paid_frame_sha256: str,
    shadow_frame_sha256: str,
) -> dict[str, object]:
    """Validate and adapt one exact local D800/D400 run pair."""

    paid = _validate_receipt(
        paid_receipt,
        arm_id=adopted_pair.PAID_ARM_ID,
        lev=160,
        boom=640,
        candidates=800,
    )
    shadow = _validate_receipt(
        shadow_receipt,
        arm_id=adopted_pair.SHADOW_ARM_ID,
        lev=80,
        boom=320,
        candidates=400,
    )
    paid_inputs = _mapping(paid["inputs"], label="D800 inputs")
    shadow_inputs = _mapping(shadow["inputs"], label="D400 inputs")
    if (
        paid["identity"] != shadow["identity"]
        or paid["banks"] != shadow["banks"]
        or paid.get("salary_pull") != shadow.get("salary_pull")
        or paid_inputs.get("content_hashes") != shadow_inputs.get("content_hashes")
        or paid_inputs.get("proj_tourney") != shadow_inputs.get("proj_tourney")
        or paid_frame_sha256 != shadow_frame_sha256
    ):
        _fail("D800/D400 shared source, input, bank, or frame identity differs")
    paid_bridge, paid_dk = _player_bridge(paid_frame)
    shadow_bridge, shadow_dk = _player_bridge(shadow_frame)
    if paid_bridge != shadow_bridge or paid_dk != shadow_dk:
        _fail("D800/D400 active player bridges differ")
    bridge_by_id = {str(row["player_id"]): row for row in paid_bridge}
    paid_ids, paid_rosters, paid_selected = _validate_candidate_pool(
        paid_candidates,
        expected_count=800,
        bridge=bridge_by_id,
        arm_id=adopted_pair.PAID_ARM_ID,
    )
    shadow_ids, shadow_rosters, shadow_selected = _validate_candidate_pool(
        shadow_candidates,
        expected_count=400,
        bridge=bridge_by_id,
        arm_id=adopted_pair.SHADOW_ARM_ID,
    )
    if not set(shadow_ids) <= set(paid_ids):
        _fail("D400 candidate population is not contained in D800")
    paid_book = _build_book(
        arm_id=adopted_pair.PAID_ARM_ID,
        bridge_rows=paid_bridge,
        dk_to_player=paid_dk,
        rosters=paid_rosters,
        selected=paid_selected,
        csv_rows=paid_csv_rows,
    )
    shadow_book = _build_book(
        arm_id=adopted_pair.SHADOW_ARM_ID,
        bridge_rows=paid_bridge,
        dk_to_player=paid_dk,
        rosters=shadow_rosters,
        selected=shadow_selected,
        csv_rows=shadow_csv_rows,
    )
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "source_commit": paid["identity"]["sha"],
        "frame_sha256": paid_frame_sha256,
        "input_identity_sha256": canonical_sha256(
            {
                "salary_pull": paid.get("salary_pull"),
                "content_hashes": paid_inputs["content_hashes"],
                "proj_tourney": paid_inputs["proj_tourney"],
                "frame_sha256": paid_frame_sha256,
            }
        ),
        "player_bridge_identity": paid_book["player_bridge_identity"],
        "paid_candidate_ids": paid_ids,
        "shadow_candidate_ids": shadow_ids,
        "paid_book": paid_book,
        "shadow_book": shadow_book,
        "roster_overlap_count": len(
            set(paid_book["roster_ids"]) & set(shadow_book["roster_ids"])
        ),
        "outcome_fields_read": [],
    }
    body["adapter_sha256"] = canonical_sha256(body)
    return body


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or tuple(rows[0]) != BOOK_HEADER:
        _fail(f"{path} does not use the exact DK slot header")
    return rows[1:]


def adapt_week1_live_pair_directories_v1(
    *, paid_run_dir: Path, shadow_run_dir: Path
) -> dict[str, object]:
    """Load two local run directories and return the canonical adapter body."""

    paid_dir = paid_run_dir.resolve(strict=True)
    shadow_dir = shadow_run_dir.resolve(strict=True)
    if paid_dir == shadow_dir:
        _fail("D800 and D400 run directories alias")
    required = (
        "receipt.json",
        "frame.parquet",
        "candidates.parquet",
        "book.csv",
    )
    for directory, label in ((paid_dir, "D800"), (shadow_dir, "D400")):
        if any(not (directory / name).is_file() for name in required):
            _fail(f"{label} run directory is incomplete")
    return adapt_week1_live_pair_v1(
        paid_receipt=json.loads((paid_dir / "receipt.json").read_text()),
        shadow_receipt=json.loads((shadow_dir / "receipt.json").read_text()),
        paid_frame=pd.read_parquet(paid_dir / "frame.parquet"),
        shadow_frame=pd.read_parquet(shadow_dir / "frame.parquet"),
        paid_candidates=pd.read_parquet(paid_dir / "candidates.parquet"),
        shadow_candidates=pd.read_parquet(shadow_dir / "candidates.parquet"),
        paid_csv_rows=_read_csv(paid_dir / "book.csv"),
        shadow_csv_rows=_read_csv(shadow_dir / "book.csv"),
        paid_frame_sha256=str(_file_identity(paid_dir / "frame.parquet")["sha256"]),
        shadow_frame_sha256=str(_file_identity(shadow_dir / "frame.parquet")["sha256"]),
    )


__all__ = [
    "ACTIVE_POLICY",
    "SCHEMA_VERSION",
    "Week1LivePairAdapterError",
    "adapt_week1_live_pair_directories_v1",
    "adapt_week1_live_pair_v1",
]
