"""Frozen helpers for the historical realistic-recourse sizing run.

This module keeps proposal construction outcome blind.  It reconstructs the
fixed-budget CBWU book from immutable score worlds, derives game status at the
registered 3:55 PM Eastern decision, and creates deterministic receipts.  The
runner is responsible for persisting every proposal checksum before it opens
the separately queried realized-outcome phase.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
import hashlib
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .multiseed_candidate_world import reconstruct_fixed_budget_book


PROTOCOL_ID = "20260815-historical-realistic-recourse-sizing-v1"
SCOPE = "phase-s-cbwu-54"
DECISION_ZONE = "America/New_York"
DECISION_HOUR = 15
DECISION_MINUTE = 55
ENTRY_COUNT = 80
TAILS = (240.0, 230.0, 220.0, 210.0, 200.0, 194.0, 187.0)
FORBIDDEN_PROPOSAL_COLUMNS = frozenset({
    "actual", "actual_score", "actual_ownership", "contest_rank", "payout",
    "roi", "final_score", "authoritative_actual",
})


def _aware(value, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp


def canonical_roster(value: str | Sequence[object]) -> tuple[str, ...]:
    values = (
        [item for item in str(value).split(",") if item]
        if isinstance(value, str)
        else [str(item) for item in value]
    )
    if len(values) != 9 or len(set(values)) != 9:
        raise ValueError("classic roster must contain nine unique players")
    return tuple(sorted(values))


def decision_instant(game_date: str | date | pd.Timestamp) -> pd.Timestamp:
    """Return the single registered decision instant for a slate date."""
    day = pd.Timestamp(game_date)
    if day.tzinfo is not None:
        day = day.tz_convert(DECISION_ZONE).tz_localize(None)
    day = day.normalize()
    return pd.Timestamp(
        year=day.year,
        month=day.month,
        day=day.day,
        hour=DECISION_HOUR,
        minute=DECISION_MINUTE,
        tz=ZoneInfo(DECISION_ZONE),
    )


def _is_terminal(row: pd.Series) -> bool:
    description = str(row.get("desc", "")).strip().lower()
    if "end game" in description or "end of game" in description:
        return True
    qtr = pd.to_numeric(pd.Series([row.get("qtr")]), errors="coerce").iloc[0]
    remaining = pd.to_numeric(
        pd.Series([row.get("game_seconds_remaining")]), errors="coerce",
    ).iloc[0]
    home = pd.to_numeric(
        pd.Series([row.get("total_home_score")]), errors="coerce",
    ).iloc[0]
    away = pd.to_numeric(
        pd.Series([row.get("total_away_score")]), errors="coerce",
    ).iloc[0]
    if pd.isna(qtr) or pd.isna(remaining) or float(remaining) != 0:
        return False
    if float(qtr) == 4:
        return not pd.isna(home) and not pd.isna(away) and float(home) != float(away)
    return float(qtr) > 4


def derive_game_statuses(
    schedules: pd.DataFrame,
    pbp: pd.DataFrame,
    *,
    as_of,
) -> tuple[pd.DataFrame, dict]:
    """Derive not-started/in-progress/final from kickoff and visible PBP only."""
    current = _aware(as_of, "recourse status as-of").tz_convert("UTC")
    schedule_required = {"game_id", "kickoff_utc"}
    missing = schedule_required - set(schedules.columns)
    if missing:
        raise ValueError("recourse schedules missing " + ", ".join(sorted(missing)))
    games = schedules.copy()
    games["game_id"] = games.game_id.astype(str)
    games["kickoff_ts"] = pd.to_datetime(
        games.kickoff_utc, format="mixed", errors="coerce", utc=True,
    )
    if (
        games.game_id.eq("").any()
        or games.game_id.duplicated().any()
        or games.kickoff_ts.isna().any()
    ):
        raise ValueError("recourse schedule game identity/kickoff is invalid")

    pbp_required = {
        "game_id", "time_of_day", "play_id", "qtr",
        "game_seconds_remaining", "total_home_score", "total_away_score", "desc",
    }
    missing = pbp_required - set(pbp.columns)
    if missing:
        raise ValueError("recourse status PBP missing " + ", ".join(sorted(missing)))
    events = pbp.copy()
    events["game_id"] = events.game_id.astype(str)
    events["_event_time"] = pd.to_datetime(
        events.time_of_day, format="mixed", errors="coerce", utc=True,
    )
    target = events.game_id.isin(games.game_id)
    untimed = events.loc[target & events._event_time.isna()].copy()
    unknown = set(events.loc[target, "game_id"]) - set(games.game_id)
    if unknown:
        raise ValueError("recourse PBP contains an unmapped target game")
    visible = events.loc[target & events._event_time.le(current)].copy()
    visible = visible.sort_values(
        ["game_id", "_event_time", "play_id"], kind="mergesort",
    )

    rows: list[dict] = []
    for game in games.itertuples(index=False):
        if game.kickoff_ts > current:
            status = "not_started"
            last_time = None
            terminal_rule = None
        else:
            group = visible[visible.game_id.eq(game.game_id)]
            if group.empty:
                raise ValueError(f"started game lacks visible PBP: {game.game_id}")
            last = group.iloc[-1]
            status = "final" if _is_terminal(last) else "in_progress"
            last_time = pd.Timestamp(last._event_time).isoformat()
            terminal_rule = (
                "latest_visible_pbp_terminal" if status == "final" else None
            )
        rows.append({
            "game_id": game.game_id,
            "kickoff_utc": pd.Timestamp(game.kickoff_ts).isoformat(),
            "game_status": status,
            "last_visible_event_time": last_time,
            "terminal_rule": terminal_rule,
        })
    result = pd.DataFrame(rows).sort_values("game_id", kind="stable").reset_index(drop=True)
    counts = result.game_status.value_counts().to_dict()
    return result, {
        "as_of": current.isoformat(),
        "games": int(len(result)),
        "status_counts": {
            status: int(counts.get(status, 0))
            for status in ("not_started", "in_progress", "final")
        },
        "status_source": "kickoff_plus_latest_visible_timestamped_pbp",
        "untimed_rows_excluded": int(len(untimed)),
        "untimed_terminal_text_rows_excluded": int(
            untimed["desc"].astype("string").str.lower().str.contains(
                r"end(?: of)? game", regex=True, na=False,
            ).sum()
        ),
        "untimed_rows_never_used_as_terminal": True,
        "uses_schedule_final_score": False,
    }


def combine_seed_player_worlds(
    artifacts: Mapping[int, Mapping[str, np.ndarray]],
    source_receipts: Mapping[int, Mapping[str, object]],
    *,
    counterfactual_generated_at,
) -> tuple[dict, dict]:
    """Align and concatenate the five retained 10k player-world matrices."""
    seeds = sorted(artifacts)
    if seeds != list(range(5)) or set(seeds) != set(source_receipts):
        raise ValueError("recourse requires exact source seeds R0 through R4")
    common: tuple[str, ...] | None = None
    blocks: list[np.ndarray] = []
    sources: list[dict] = []
    hasher = hashlib.sha256()
    for seed in seeds:
        artifact = artifacts[seed]
        ids = np.asarray(artifact["player_ids"]).astype(str).tolist()
        draws = np.asarray(artifact["player_draws"], dtype=np.float32)
        if len(set(ids)) != len(ids) or draws.shape != (len(ids), 10_000):
            raise ValueError(f"R{seed} player-world shape/identity differs")
        universe = tuple(sorted(ids))
        if common is None:
            common = universe
        elif universe != common:
            raise ValueError("recourse player universes differ across seeds")
        lookup = {player_id: index for index, player_id in enumerate(ids)}
        aligned = draws[[lookup[player_id] for player_id in common]]
        blocks.append(aligned)
        receipt = source_receipts[seed]
        digest = str(receipt.get("sha256", ""))
        uri = str(receipt.get("uri", ""))
        generation = str(receipt.get("generation", ""))
        updated = str(receipt.get("updated", ""))
        panel_run_id = str(receipt.get("panel_run_id", ""))
        if (
            len(digest) != 64
            or not uri.startswith("gs://")
            or not generation.isdigit()
            or not updated
            or not panel_run_id
        ):
            raise ValueError(f"R{seed} source artifact receipt is invalid")
        sources.append({
            "seed": seed,
            "panel_run_id": panel_run_id,
            "uri": uri,
            "sha256": digest,
            "generation": generation,
            "updated": updated,
            "size": int(receipt.get("size", 0)),
        })
        hasher.update(seed.to_bytes(1, "big"))
        hasher.update(digest.encode("ascii"))
        hasher.update(aligned.tobytes(order="C"))
    assert common is not None
    combined = np.concatenate(blocks, axis=1)
    hasher.update("\n".join(common).encode("utf-8"))
    digest = hasher.hexdigest()
    generated = _aware(
        counterfactual_generated_at, "counterfactual world availability",
    )
    artifact = {
        "generated_at": generated,
        "player_ids": np.asarray(common),
        "player_draws": combined,
        "sha256": digest,
    }
    return artifact, {
        "combined_sha256": digest,
        "players": len(common),
        "worlds": int(combined.shape[1]),
        "sources": sources,
        "historical_counterfactual_availability": True,
        "counterfactual_generated_at": generated.isoformat(),
        "actual_artifact_creation_time_not_represented_as_decision_time": True,
    }


def reconstruct_outcome_blind_cbwu(
    seed_rows: Mapping[int, pd.DataFrame],
    seed_artifacts: Mapping[int, Mapping[str, np.ndarray]],
) -> pd.DataFrame:
    """Reconstruct CBWU while refusing realized outcome columns as inputs."""
    clean: dict[int, pd.DataFrame] = {}
    for seed, rows in seed_rows.items():
        forbidden = FORBIDDEN_PROPOSAL_COLUMNS & set(rows.columns)
        if forbidden:
            raise ValueError(
                "outcome-blind source rows contain forbidden columns: "
                + ", ".join(sorted(forbidden))
            )
        frame = rows.copy()
        # The legacy reconstruction validator needs an outcome placeholder only
        # to check duplicate-roster consistency. It never enters allocation or
        # selection, and it is removed from the returned proposal frame.
        frame["actual_score"] = 0.0
        clean[int(seed)] = frame
    result = reconstruct_fixed_budget_book(
        clean, seed_artifacts, world_union=True, entry_count=ENTRY_COUNT,
    )
    return result.drop(columns=["actual_score"])


def validate_forensic_parity(
    reconstructed: pd.DataFrame,
    forensic: pd.DataFrame,
) -> dict:
    """Require exact candidate and exact-80 selected identity parity."""
    required = {"roster_key", "selected", "selected_rank"}
    missing = required - set(forensic.columns)
    if missing:
        raise ValueError("forensic parity frame missing " + ", ".join(sorted(missing)))
    if FORBIDDEN_PROPOSAL_COLUMNS & set(forensic.columns):
        raise ValueError("forensic parity frame contains outcome columns")
    rec = reconstructed.copy()
    rec["roster_key"] = rec.players.map(lambda value: ",".join(canonical_roster(value)))
    ref = forensic.copy()
    ref["roster_key"] = ref.roster_key.map(
        lambda value: ",".join(canonical_roster(value))
    )
    if rec.roster_key.duplicated().any() or ref.roster_key.duplicated().any():
        raise ValueError("candidate parity population repeats a roster")
    if set(rec.roster_key) != set(ref.roster_key):
        raise ValueError("reconstructed candidate identities differ from forensic corpus")
    rec_sel = rec[rec.selected.astype(bool)].sort_values("selected_rank", kind="stable")
    ref_sel = ref[ref.selected.astype(bool)].sort_values("selected_rank", kind="stable")
    if len(rec_sel) != ENTRY_COUNT or len(ref_sel) != ENTRY_COUNT:
        raise ValueError("candidate parity does not contain exact-80 selections")
    if rec_sel.roster_key.tolist() != ref_sel.roster_key.tolist():
        raise ValueError("reconstructed selected order differs from forensic corpus")
    candidate_identities = sorted(rec.roster_key.astype(str).tolist())
    selected_order = rec_sel.roster_key.astype(str).tolist()
    return {
        "candidate_count": int(len(rec)),
        "selected_count": ENTRY_COUNT,
        "candidate_identity_sha256": canonical_json_sha256(candidate_identities),
        "selected_order_sha256": canonical_json_sha256(selected_order),
        "candidate_identity_parity": True,
        "selected_order_parity": True,
    }


def _canonical_json_bytes(value: object) -> bytes:
    def numpy_scalar(item: object) -> object:
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(
            f"Object of type {item.__class__.__name__} is not JSON serializable"
        )

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=numpy_scalar,
    ).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    payload = _canonical_json_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def freeze_proposals(proposals: Sequence[Mapping[str, object]]) -> dict:
    """Create the pre-outcome proposal-set receipt for all registered slates."""
    ordered = sorted(
        (dict(value) for value in proposals),
        key=lambda value: (int(value["season"]), int(value["week"])),
    )
    if len(ordered) != 54:
        raise ValueError("realistic recourse proposal set must contain 54 slates")
    keys = [(int(row["season"]), int(row["week"])) for row in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("realistic recourse proposal set repeats a slate")
    forbidden = FORBIDDEN_PROPOSAL_COLUMNS
    encoded = _canonical_json_bytes(ordered).decode("utf-8")
    # Freeze only standard JSON primitives so the later create-only upload
    # cannot fail after all 54 pre-outcome proposals have been constructed.
    ordered = json.loads(encoded)
    if any(f'"{column}"' in encoded for column in forbidden):
        raise ValueError("proposal set contains a forbidden outcome field")
    return {
        "protocol_id": PROTOCOL_ID,
        "scope": SCOPE,
        "slates": len(ordered),
        "proposal_set_sha256": canonical_json_sha256(ordered),
        "proposals": ordered,
        "outcomes_opened": False,
    }


def roster_swap_distance(left: Sequence[object], right: Sequence[object]) -> int:
    return 9 - len(set(map(str, left)) & set(map(str, right)))


__all__ = [
    "ENTRY_COUNT", "PROTOCOL_ID", "SCOPE", "TAILS",
    "canonical_json_sha256", "canonical_roster", "combine_seed_player_worlds",
    "decision_instant", "derive_game_statuses", "freeze_proposals",
    "reconstruct_outcome_blind_cbwu", "roster_swap_distance",
    "validate_forensic_parity",
]
