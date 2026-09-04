from __future__ import annotations

from itertools import islice, product

import pandas as pd
import pytest

from nfl_dfs.inference import week1_adopted_pair as adopted
from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference.week1_live_pair_adapter import (
    Week1LivePairAdapterError,
    adapt_week1_live_pair_v1,
)


def _live_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    list[list[str]],
]:
    groups = (
        ("q", "QB", "AAA"),
        ("a", "RB", "AAA"),
        ("b", "RB", "BBB"),
        ("c", "WR", "AAA"),
        ("d", "WR", "BBB"),
        ("e", "WR", "CCC"),
        ("f", "TE", "CCC"),
        ("g", "RB", "BBB"),
        ("h", "DST", "CCC"),
    )
    rows: list[dict[str, object]] = []
    choices: list[list[str]] = []
    for group_index, (prefix, position, team) in enumerate(groups):
        group_choices = []
        for choice in range(4):
            player_id = f"{prefix}{choice}"
            group_choices.append(player_id)
            rows.append(
                {
                    "id": player_id,
                    "dk_player_id": 1_000 + group_index * 10 + choice,
                    "pos": position,
                    "team": team,
                    "salary": 5_000,
                    "roster_status": pd.NA if position == "DST" else "ACT",
                }
            )
        choices.append(group_choices)
    slot_rosters = [list(roster) for roster in islice(product(*choices), 800)]
    frame = pd.DataFrame(rows)
    candidates = pd.DataFrame(
        {
            "players": [",".join(sorted(roster)) for roster in slot_rosters],
            "book_rank": [rank if rank <= 80 else pd.NA for rank in range(1, 801)],
        }
    )
    csv_rows = [
        [str(frame.set_index("id").loc[player_id, "dk_player_id"]) for player_id in roster]
        for roster in slot_rosters[:80]
    ]
    return frame, candidates, csv_rows


def _receipt(*, lev: int, boom: int, candidates: int) -> dict[str, object]:
    return {
        "season": 2026,
        "week": 1,
        "draft_group": 151307,
        "lock_utc": "2026-09-13 17:00:00+00:00",
        "salary_pull": "2026-09-04 09:03:18.206098+00:00",
        "identity": {"sha": "a" * 40, "dirty": False, "diff_sha256": None},
        "inputs": {
            "roster_status_invariant": {
                "eligibility_policy": "target-week-active-skill-allowlist-v1",
                "required_skill_status": "ACT",
                "kept_nonact_skill_statuses": {},
            },
            "content_hashes": {"salaries": "one", "rosters": "two"},
            "proj_tourney": {"formula_id": "fixture"},
        },
        "banks": {
            "generation_seed": 2026,
            "selection_seed": 2076,
            "audit_seed": 2126,
            "independent_event_randomness": True,
            "shifted_to_identical_means": True,
        },
        "config": {
            "lev": lev,
            "boom": boom,
            "k": 1,
            "operational_k": 80,
            "sims": 10_000,
            "seed": 2026,
            "selector": "dual_emax",
            "hsim_seed": 2326,
            "hsim_worlds": 10_000,
        },
        "candidates": candidates,
        "written": 80,
        "book_k80_is_nested_prefix": True,
    }


def _adapt(*, frame: pd.DataFrame | None = None) -> dict[str, object]:
    fixture_frame, paid_candidates, paid_csv = _live_inputs()
    if frame is not None:
        fixture_frame = frame
    shadow_candidates = paid_candidates.iloc[:400].copy()
    return adapt_week1_live_pair_v1(
        paid_receipt=_receipt(lev=160, boom=640, candidates=800),
        shadow_receipt=_receipt(lev=80, boom=320, candidates=400),
        paid_frame=fixture_frame,
        shadow_frame=fixture_frame.copy(),
        paid_candidates=paid_candidates,
        shadow_candidates=shadow_candidates,
        paid_csv_rows=paid_csv,
        shadow_csv_rows=paid_csv,
        paid_frame_sha256="b" * 64,
        shadow_frame_sha256="b" * 64,
    )


def test_adapts_exact_active_d800_d400_pair() -> None:
    adapted = _adapt()

    assert adapted["complete"] is True
    assert len(adapted["paid_candidate_ids"]) == 800
    assert len(adapted["shadow_candidate_ids"]) == 400
    assert set(adapted["shadow_candidate_ids"]) <= set(
        adapted["paid_candidate_ids"]
    )
    assert adapted["paid_book"]["arm_id"] == adopted.PAID_ARM_ID
    assert adapted["shadow_book"]["arm_id"] == adopted.SHADOW_ARM_ID
    assert adapted["roster_overlap_count"] == 80
    retained_hash = adapted.pop("adapter_sha256")
    assert retained_hash == canonical_sha256(adapted)


def test_rejects_non_active_skill_player_in_frozen_frame() -> None:
    frame, _candidates, _csv_rows = _live_inputs()
    frame.loc[frame.id == "q0", "roster_status"] = "DEV"

    with pytest.raises(Week1LivePairAdapterError, match="non-ACT skill"):
        _adapt(frame=frame)
