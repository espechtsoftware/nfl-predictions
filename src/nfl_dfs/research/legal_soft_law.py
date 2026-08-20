"""Pure accounting and ranking for the contingent legal-soft-law-v1 policy.

The module is deliberately incapable of touching an optimizer, warehouse,
object store, cloud resource, lease, or outcome source.  It accepts only a
mock-marked contract while the policy is ``READY-AWAITING-A2A-AND-B1``.  A
later, separately reviewed implementation may reuse these invariants after
both prerequisite experiments have passed and the real-artifact protocol has
been frozen.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import math
import re
from statistics import mean
from typing import Any


PROTOCOL_ID = "20260820-legal-soft-law-v1"
PROTOCOL_STATUS = "READY-AWAITING-A2A-AND-B1"
A2A_PASS_DISPOSITION = (
    "a2a-law-shape-passes-single-stack-protocol-licensed"
)
B1_REPORT_VERSION = "b1-corpus-tail-historical-evaluation-v1"
B1_MODEL_VERSION = "b1-corpus-tail-logit-v1"

WORLD_BLOCKS = 5
WORLDS_PER_BLOCK = 10_000
ENTRIES = 80
MIN_NATIVE_CANDIDATES = 241
INCUMBENT_SUPPORT = 80
EXACT_ONE_SUPPORT = 80
THRESHOLDS = (194, 200, 210)
SUPPORT_SLEEVES = ("incumbent", "exact_one", "legality_only")

# Every former house mandate is represented here.  The first nine values are
# reconstructed from the roster.  Ownership and duplication are point-in-time
# estimates supplied to the eventual model, not legality requirements.
SOFT_LAW_FEATURES = (
    "salary_total",
    "unused_salary",
    "qb_partner_count",
    "bring_back_count",
    "rb_vs_dst_count",
    "same_team_rb_pair_count",
    "games_represented",
    "teams_represented",
    "largest_game_block",
    "largest_team_block",
    "ownership_sum_est",
    "duplication_risk_est",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "DST"})
_FORBIDDEN_OUTCOME_KEYS = frozenset({
    "actual",
    "actual_score",
    "candidate_max",
    "contest_rank",
    "field_rank",
    "outcome",
    "payout",
    "settled_score",
    "weekly_max",
    "winner",
    "winner_score",
})


class LegalSoftLawError(ValueError):
    """A fail-closed legal-soft policy contract violation."""


def canonical_json(value: object) -> bytes:
    """Return the canonical bytes used by the local mocked scaffold."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def _require_keys(
    value: Mapping[str, object], expected: set[str], *, label: str,
) -> None:
    if set(value) != expected:
        raise LegalSoftLawError(
            f"{label} fields differ: expected {sorted(expected)}, "
            f"got {sorted(value)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LegalSoftLawError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def _finite(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LegalSoftLawError(f"{label} must be finite numeric")
    number = float(value)
    if not math.isfinite(number):
        raise LegalSoftLawError(f"{label} must be finite numeric")
    return number


def _literal_bool(value: object, *, label: str, expected: bool) -> None:
    if not isinstance(value, bool) or value is not expected:
        raise LegalSoftLawError(f"{label} must be literal {expected}")


def _mock_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} is not an identity")
    _require_keys(
        value, {"uri", "generation", "sha256", "bytes"}, label=label,
    )
    uri = value["uri"]
    generation = value["generation"]
    digest = value["sha256"]
    if not isinstance(uri, str) or not uri.startswith("mock://") or \
            not isinstance(generation, str) or not generation.isdigit() or \
            not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise LegalSoftLawError(f"{label} must be a mock content identity")
    _exact_int(value["bytes"], label=f"{label}.bytes", minimum=1)
    return dict(value)


def _bind_mock_body(
    body: object, identity: object, *, label: str,
) -> dict[str, object]:
    """Validate mock identity by body content, not caller representation."""
    validated = _mock_identity(identity, label=label)
    raw = canonical_json(body)
    if validated["sha256"] != sha256(raw).hexdigest() or \
            validated["bytes"] != len(raw):
        raise LegalSoftLawError(f"{label} does not match its canonical body")
    return validated


def _aware_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise LegalSoftLawError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LegalSoftLawError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LegalSoftLawError(f"{label} must be timezone-aware")
    return parsed


def _find_forbidden_key(value: object, path: str = "payload") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in _FORBIDDEN_OUTCOME_KEYS:
                return child
            found = _find_forbidden_key(item, child)
            if found is not None:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            found = _find_forbidden_key(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def validate_prerequisites(value: object) -> dict[str, object]:
    """Require literal, content-pinned A2a and B1 historical passes."""
    if not isinstance(value, Mapping):
        raise LegalSoftLawError("prerequisites are not an object")
    _require_keys(value, {"a2a", "b1"}, label="prerequisites")

    a2a = value["a2a"]
    if not isinstance(a2a, Mapping):
        raise LegalSoftLawError("A2a prerequisite is not an object")
    _require_keys(a2a, {"result", "result_identity"}, label="A2a prerequisite")
    result = a2a["result"]
    if not isinstance(result, Mapping):
        raise LegalSoftLawError("A2a result is not an object")
    a2a_identity = _bind_mock_body(
        result, a2a["result_identity"], label="A2a result identity",
    )
    if result.get("passes") is not True or \
            result.get("disposition") != A2A_PASS_DISPOSITION:
        raise LegalSoftLawError("A2a realized-law result did not pass")
    a2a_licenses = result.get("licenses")
    expected_a2a_licenses = {
        "uses_realized_outcomes": True,
        "actual_outcomes_queried": True,
        "candidate_or_lineup_scores_read": False,
        "single_stack_protocol_licensed": True,
        "single_stack_arm_licensed": False,
        "exact80_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if not isinstance(a2a_licenses, Mapping) or \
            dict(a2a_licenses) != expected_a2a_licenses:
        raise LegalSoftLawError("A2a licenses differ from the sole pass contract")

    b1 = value["b1"]
    if not isinstance(b1, Mapping):
        raise LegalSoftLawError("B1 prerequisite is not an object")
    _require_keys(
        b1,
        {"report", "report_identity", "model_artifact", "model_identity"},
        label="B1 prerequisite",
    )
    report = b1["report"]
    if not isinstance(report, Mapping):
        raise LegalSoftLawError("B1 report is not an object")
    report_identity = _bind_mock_body(
        report, b1["report_identity"], label="B1 report identity",
    )
    expected_b1_licenses = {
        "write_2026_shadow_artifact": True,
        "run_2026_shadow": True,
        "production": False,
        "historical_retune": False,
    }
    if report.get("version") != B1_REPORT_VERSION or \
            report.get("historical_pass") is not True or \
            report.get("uses_realized_outcomes") is not True or \
            report.get("uses_winner_target_or_feature") is not False or \
            report.get("licenses") != expected_b1_licenses:
        raise LegalSoftLawError("B1 corpus-tail historical result did not pass")
    model = report.get("model")
    if not isinstance(model, Mapping) or model.get("version") != B1_MODEL_VERSION:
        raise LegalSoftLawError("B1 report does not bind the frozen model")

    artifact = b1["model_artifact"]
    if not isinstance(artifact, Mapping):
        raise LegalSoftLawError("B1 portable model artifact is not an object")
    model_identity = _bind_mock_body(
        artifact, b1["model_identity"], label="B1 model identity",
    )
    artifact_without_hash = {
        key: item for key, item in artifact.items() if key != "artifact_sha256"
    }
    if artifact.get("historical_gate_passed") is not True or \
            artifact.get("production_licensed") is not False or \
            artifact.get("prospective_shadow_only") is not True or \
            artifact.get("artifact_sha256") != canonical_sha256(
                artifact_without_hash
            ):
        raise LegalSoftLawError("B1 portable model artifact is not licensed")

    return {
        "a2a_result_identity": a2a_identity,
        "b1_report_identity": report_identity,
        "b1_model_identity": model_identity,
    }


def _validate_snapshot(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError("snapshot is not an object")
    _require_keys(
        value,
        {
            "snapshot_id", "feature_snapshot_at", "contest_lock_at",
            "source_identities", "outcome_fields_read", "winner_fields_read",
        },
        label="snapshot",
    )
    if not isinstance(value["snapshot_id"], str) or not value["snapshot_id"]:
        raise LegalSoftLawError("snapshot_id must be nonempty")
    snapshot_at = _aware_datetime(
        value["feature_snapshot_at"], label="feature_snapshot_at",
    )
    lock_at = _aware_datetime(value["contest_lock_at"], label="contest_lock_at")
    if snapshot_at >= lock_at:
        raise LegalSoftLawError("feature snapshot must precede contest lock")
    identities = value["source_identities"]
    if not isinstance(identities, list) or not identities:
        raise LegalSoftLawError("source identities must be a nonempty list")
    validated = [
        _mock_identity(item, label=f"source identity {index}")
        for index, item in enumerate(identities)
    ]
    if value["outcome_fields_read"] != [] or value["winner_fields_read"] != []:
        raise LegalSoftLawError("snapshot crosses the outcome/winner firewall")
    return {
        "snapshot_id": value["snapshot_id"],
        "feature_snapshot_at": value["feature_snapshot_at"],
        "contest_lock_at": value["contest_lock_at"],
        "source_identities": validated,
    }


def _validate_budget(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} budget is not an object")
    _require_keys(
        value,
        {
            "candidate_budget_source", "control_candidate_budget",
            "treatment_candidate_budget", "control_solve_attempts",
            "treatment_solve_attempts", "world_blocks", "worlds_per_block",
            "seed_ids", "world_draw_sha256s", "solve_schedule_sha256",
            "entry_count",
        },
        label=f"{label} budget",
    )
    if value["candidate_budget_source"] != "incumbent-r0-native-count":
        raise LegalSoftLawError(f"{label} candidate budget source differs")
    control_candidates = _exact_int(
        value["control_candidate_budget"],
        label=f"{label} control candidate budget",
        minimum=MIN_NATIVE_CANDIDATES,
    )
    treatment_candidates = _exact_int(
        value["treatment_candidate_budget"],
        label=f"{label} treatment candidate budget",
        minimum=MIN_NATIVE_CANDIDATES,
    )
    if treatment_candidates != control_candidates:
        raise LegalSoftLawError(f"{label} candidate budgets differ")
    control_solves = _exact_int(
        value["control_solve_attempts"],
        label=f"{label} control solve attempts",
        minimum=control_candidates,
    )
    treatment_solves = _exact_int(
        value["treatment_solve_attempts"],
        label=f"{label} treatment solve attempts",
        minimum=treatment_candidates,
    )
    if treatment_solves != control_solves:
        raise LegalSoftLawError(f"{label} solve budgets differ")
    if _exact_int(value["world_blocks"], label=f"{label} world blocks") != \
            WORLD_BLOCKS or _exact_int(
                value["worlds_per_block"], label=f"{label} worlds per block",
            ) != WORLDS_PER_BLOCK:
        raise LegalSoftLawError(f"{label} world budget differs")
    if _exact_int(value["entry_count"], label=f"{label} entry count") != ENTRIES:
        raise LegalSoftLawError(f"{label} entry count is not exact 80")
    if value["seed_ids"] != list(range(WORLD_BLOCKS)):
        raise LegalSoftLawError(f"{label} seed schedule differs")
    draw_hashes = value["world_draw_sha256s"]
    if not isinstance(draw_hashes, list) or len(draw_hashes) != WORLD_BLOCKS or \
            len(set(draw_hashes)) != WORLD_BLOCKS or any(
                not isinstance(item, str) or _SHA256.fullmatch(item) is None
                for item in draw_hashes
            ):
        raise LegalSoftLawError(f"{label} world identities differ")
    schedule_hash = value["solve_schedule_sha256"]
    if not isinstance(schedule_hash, str) or \
            _SHA256.fullmatch(schedule_hash) is None:
        raise LegalSoftLawError(f"{label} solve schedule identity differs")
    return {
        "candidate_budget": control_candidates,
        "solve_attempts": control_solves,
        "world_blocks": WORLD_BLOCKS,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "entry_count": ENTRIES,
        "seed_ids": list(value["seed_ids"]),
        "world_draw_sha256s": list(draw_hashes),
        "solve_schedule_sha256": schedule_hash,
    }


def _validate_player(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} is not a player")
    _require_keys(
        value,
        {
            "id", "pos", "team", "opp", "game_id", "salary",
            "slate_eligible", "prelock_eligible",
        },
        label=label,
    )
    for key in ("id", "team", "opp", "game_id"):
        if not isinstance(value[key], str) or not value[key]:
            raise LegalSoftLawError(f"{label}.{key} must be nonempty")
    if value["pos"] not in _POSITIONS:
        raise LegalSoftLawError(f"{label}.pos is invalid")
    salary = _exact_int(value["salary"], label=f"{label}.salary", minimum=1)
    _literal_bool(
        value["slate_eligible"], label=f"{label}.slate_eligible", expected=True,
    )
    _literal_bool(
        value["prelock_eligible"], label=f"{label}.prelock_eligible", expected=True,
    )
    output = dict(value)
    output["salary"] = salary
    return output


def _roster_features(players: list[dict[str, object]], *, label: str) -> dict[str, int]:
    if len(players) != 9 or len({str(player["id"]) for player in players}) != 9:
        raise LegalSoftLawError(f"{label} must contain nine unique players")
    positions = Counter(str(player["pos"]) for player in players)
    if positions["QB"] != 1 or positions["DST"] != 1 or \
            not 2 <= positions["RB"] <= 3 or \
            not 3 <= positions["WR"] <= 4 or \
            not 1 <= positions["TE"] <= 2:
        raise LegalSoftLawError(f"{label} violates DK Classic position shape")
    salary = sum(int(player["salary"]) for player in players)
    if salary > 50_000:
        raise LegalSoftLawError(f"{label} exceeds the DK salary cap")
    teams = Counter(str(player["team"]) for player in players)
    games = Counter(str(player["game_id"]) for player in players)
    if len(games) < 2 or max(teams.values()) > 8:
        raise LegalSoftLawError(f"{label} violates DK game/team requirements")

    qb = next(player for player in players if player["pos"] == "QB")
    dst = next(player for player in players if player["pos"] == "DST")
    qb_team = str(qb["team"])
    qb_opp = str(qb["opp"])
    qb_partners = sum(
        player["pos"] in {"WR", "TE"} and player["team"] == qb_team
        for player in players
    )
    bring_backs = sum(
        player["pos"] in {"RB", "WR", "TE"} and player["team"] == qb_opp
        for player in players
    )
    rb_vs_dst = sum(
        player["pos"] == "RB" and player["opp"] == dst["team"]
        for player in players
    )
    rb_teams = Counter(
        str(player["team"]) for player in players if player["pos"] == "RB"
    )
    same_team_rb_pairs = sum(
        count * (count - 1) // 2 for count in rb_teams.values()
    )
    return {
        "salary_total": salary,
        "unused_salary": 50_000 - salary,
        "qb_partner_count": int(qb_partners),
        "bring_back_count": int(bring_backs),
        "rb_vs_dst_count": int(rb_vs_dst),
        "same_team_rb_pair_count": int(same_team_rb_pairs),
        "games_represented": len(games),
        "teams_represented": len(teams),
        "largest_game_block": max(games.values()),
        "largest_team_block": max(teams.values()),
    }


def _validate_candidate(
    value: object, *, label: str, arm: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} is not a candidate")
    _require_keys(
        value,
        {
            "roster_key", "players", "support_sleeve", "model_score",
            "tie_break_p_line", "tie_break_q99", "soft_features",
        },
        label=label,
    )
    players_raw = value["players"]
    if not isinstance(players_raw, list):
        raise LegalSoftLawError(f"{label}.players is not a list")
    players = [
        _validate_player(player, label=f"{label}.players[{index}]")
        for index, player in enumerate(players_raw)
    ]
    roster_key = ",".join(sorted(str(player["id"]) for player in players))
    if value["roster_key"] != roster_key:
        raise LegalSoftLawError(f"{label}.roster_key is not canonical")
    derived = _roster_features(players, label=label)

    features = value["soft_features"]
    if not isinstance(features, Mapping) or set(features) != set(SOFT_LAW_FEATURES):
        raise LegalSoftLawError(f"{label}.soft_features fields differ")
    for key, expected in derived.items():
        if features[key] != expected:
            raise LegalSoftLawError(f"{label}.soft_features.{key} differs")
    for key in ("ownership_sum_est", "duplication_risk_est"):
        if features[key] is not None:
            _finite(features[key], label=f"{label}.soft_features.{key}")

    sleeve = value["support_sleeve"]
    if arm == "control":
        if sleeve != "control":
            raise LegalSoftLawError(f"{label} has a non-control sleeve")
    elif sleeve not in SUPPORT_SLEEVES:
        raise LegalSoftLawError(f"{label} has an unknown treatment sleeve")
    elif sleeve == "incumbent":
        if derived["qb_partner_count"] < 2 or \
                derived["bring_back_count"] < 1 or \
                derived["salary_total"] < 49_000 or \
                derived["rb_vs_dst_count"] != 0 or \
                derived["same_team_rb_pair_count"] != 0:
            raise LegalSoftLawError(f"{label} does not satisfy incumbent support")
    elif sleeve == "exact_one":
        if derived["qb_partner_count"] != 1 or \
                derived["bring_back_count"] < 1 or \
                derived["salary_total"] < 49_000 or \
                derived["rb_vs_dst_count"] != 0 or \
                derived["same_team_rb_pair_count"] != 0:
            raise LegalSoftLawError(f"{label} does not satisfy exact-one support")

    score = _finite(value["model_score"], label=f"{label}.model_score")
    p_line = _finite(value["tie_break_p_line"], label=f"{label}.tie_break_p_line")
    q99 = _finite(value["tie_break_q99"], label=f"{label}.tie_break_q99")
    if not 0.0 <= score <= 1.0 or not 0.0 <= p_line <= 1.0:
        raise LegalSoftLawError(f"{label} probability is outside [0, 1]")
    return {
        "roster_key": roster_key,
        "support_sleeve": sleeve,
        "model_score": score,
        "tie_break_p_line": p_line,
        "tie_break_q99": q99,
        "soft_features": dict(features),
    }


def rank_treatment(candidates: Sequence[Mapping[str, object]]) -> list[str]:
    """Rank a legal candidate pool with no support-sleeve or shape quota."""
    ordered = sorted(
        candidates,
        key=lambda row: (
            -float(row["model_score"]),
            -float(row["tie_break_p_line"]),
            -float(row["tie_break_q99"]),
            str(row["roster_key"]),
        ),
    )
    return [str(row["roster_key"]) for row in ordered[:ENTRIES]]


def _validate_arm(
    value: object, *, label: str, arm: str, candidate_budget: int,
) -> tuple[list[dict[str, object]], list[str]]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} is not an arm")
    expected = {"candidates", "selected_roster_keys"} if arm == "control" \
        else {"candidates"}
    _require_keys(value, expected, label=label)
    rows = value["candidates"]
    if not isinstance(rows, list) or len(rows) != candidate_budget:
        raise LegalSoftLawError(f"{label} does not fill its candidate budget")
    candidates = [
        _validate_candidate(row, label=f"{label}.candidates[{index}]", arm=arm)
        for index, row in enumerate(rows)
    ]
    roster_keys = [str(row["roster_key"]) for row in candidates]
    if len(set(roster_keys)) != candidate_budget:
        raise LegalSoftLawError(f"{label} contains duplicate rosters")

    if arm == "control":
        selected_raw = value["selected_roster_keys"]
        if not isinstance(selected_raw, list) or len(selected_raw) != ENTRIES or \
                len(set(selected_raw)) != ENTRIES or \
                not set(selected_raw) <= set(roster_keys):
            raise LegalSoftLawError(f"{label} is not the incumbent exact-80 book")
        selected = list(selected_raw)
    else:
        sleeve_counts = Counter(str(row["support_sleeve"]) for row in candidates)
        expected_counts = {
            "incumbent": INCUMBENT_SUPPORT,
            "exact_one": EXACT_ONE_SUPPORT,
            "legality_only": candidate_budget - INCUMBENT_SUPPORT - EXACT_ONE_SUPPORT,
        }
        if dict(sleeve_counts) != expected_counts:
            raise LegalSoftLawError(f"{label} support-sleeve allocation differs")
        selected = rank_treatment(candidates)
    return candidates, selected


def _validate_scores(
    value: object, *, roster_keys: set[str], label: str,
) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise LegalSoftLawError(f"{label} mock scores are not an object")
    if set(value) != roster_keys:
        raise LegalSoftLawError(f"{label} mock score coverage differs")
    return {
        str(key): _finite(score, label=f"{label}.{key}")
        for key, score in value.items()
    }


def _threshold_counts(values: Sequence[float]) -> dict[str, int]:
    return {
        str(threshold): sum(value >= threshold for value in values)
        for threshold in THRESHOLDS
    }


def evaluate_payload(payload: object) -> dict[str, Any]:
    """Validate and evaluate one entirely mocked policy contract."""
    if not isinstance(payload, Mapping):
        raise LegalSoftLawError("payload is not an object")
    base_fields = {
        "protocol_id", "protocol_status", "mocked", "mode",
        "prerequisites", "snapshot", "slates",
    }
    _require_keys(payload, base_fields, label="payload")
    if payload["protocol_id"] != PROTOCOL_ID or \
            payload["protocol_status"] != PROTOCOL_STATUS:
        raise LegalSoftLawError("protocol identity/status differs")
    _literal_bool(payload["mocked"], label="mocked", expected=True)
    mode = payload["mode"]
    if mode not in {"mocked-outcome-blind", "mocked-historical"}:
        raise LegalSoftLawError("only mocked scaffold modes are available")
    if mode == "mocked-outcome-blind":
        forbidden = _find_forbidden_key(payload)
        if forbidden is not None:
            raise LegalSoftLawError(f"outcome-blind forbidden field: {forbidden}")

    prerequisites = validate_prerequisites(payload["prerequisites"])
    snapshot = _validate_snapshot(payload["snapshot"])
    slates = payload["slates"]
    if not isinstance(slates, list) or not slates:
        raise LegalSoftLawError("slates must be a nonempty mocked list")

    seen_cells: set[tuple[int, int]] = set()
    slate_reports: list[dict[str, object]] = []
    control_selected_maxima: list[float] = []
    treatment_selected_maxima: list[float] = []
    treatment_candidate_maxima: list[float] = []

    for index, slate in enumerate(slates):
        label = f"slates[{index}]"
        if not isinstance(slate, Mapping):
            raise LegalSoftLawError(f"{label} is not an object")
        expected_fields = {"season", "week", "budget", "control", "treatment"}
        if mode == "mocked-historical":
            expected_fields.add("mock_outcomes")
        _require_keys(slate, expected_fields, label=label)
        season = _exact_int(slate["season"], label=f"{label}.season", minimum=2023)
        week = _exact_int(slate["week"], label=f"{label}.week", minimum=1)
        cell = season, week
        if cell in seen_cells:
            raise LegalSoftLawError(f"duplicate mocked slate {cell}")
        seen_cells.add(cell)

        budget = _validate_budget(slate["budget"], label=label)
        control, control_selected = _validate_arm(
            slate["control"], label=f"{label}.control", arm="control",
            candidate_budget=int(budget["candidate_budget"]),
        )
        treatment, treatment_selected = _validate_arm(
            slate["treatment"], label=f"{label}.treatment", arm="treatment",
            candidate_budget=int(budget["candidate_budget"]),
        )
        selected_sleeves = Counter(
            str(row["support_sleeve"])
            for row in treatment
            if row["roster_key"] in set(treatment_selected)
        )
        report: dict[str, object] = {
            "season": season,
            "week": week,
            "budget": budget,
            "control_selected_roster_keys": control_selected,
            "treatment_selected_roster_keys": treatment_selected,
            "treatment_pool_sleeves": dict(Counter(
                str(row["support_sleeve"]) for row in treatment
            )),
            "treatment_selected_sleeves": {
                sleeve: selected_sleeves.get(sleeve, 0)
                for sleeve in SUPPORT_SLEEVES
            },
        }

        if mode == "mocked-historical":
            outcomes = slate["mock_outcomes"]
            if not isinstance(outcomes, Mapping):
                raise LegalSoftLawError(f"{label}.mock_outcomes is not an object")
            _require_keys(
                outcomes, {"control_scores", "treatment_scores"},
                label=f"{label}.mock_outcomes",
            )
            control_scores = _validate_scores(
                outcomes["control_scores"],
                roster_keys={str(row["roster_key"]) for row in control},
                label=f"{label}.control_scores",
            )
            treatment_scores = _validate_scores(
                outcomes["treatment_scores"],
                roster_keys={str(row["roster_key"]) for row in treatment},
                label=f"{label}.treatment_scores",
            )
            control_c = max(control_scores.values())
            treatment_c = max(treatment_scores.values())
            control_s = max(control_scores[key] for key in control_selected)
            treatment_s = max(treatment_scores[key] for key in treatment_selected)
            if control_s > control_c or treatment_s > treatment_c:
                raise LegalSoftLawError(f"{label} selected maximum exceeds ceiling")
            report["mock_scores"] = {
                "control_candidate_ceiling": control_c,
                "treatment_candidate_ceiling": treatment_c,
                "control_selected_max": control_s,
                "treatment_selected_max": treatment_s,
                "treatment_conversion_gap": treatment_c - treatment_s,
            }
            control_selected_maxima.append(control_s)
            treatment_selected_maxima.append(treatment_s)
            treatment_candidate_maxima.append(treatment_c)
        slate_reports.append(report)

    historical_gate: dict[str, object] | None = None
    licenses = {
        "real_artifact_smoke_licensed": False,
        "freeze_licensed": False,
        "historical_execution_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    mocked_would_license = {
        "prospective_shadow_design": False,
        "target_200_track": False,
    }
    if mode == "mocked-outcome-blind":
        disposition = "legal-soft-law-mocked-mechanics-pass"
    else:
        control_counts = _threshold_counts(control_selected_maxima)
        treatment_counts = _threshold_counts(treatment_selected_maxima)
        control_mean = mean(control_selected_maxima)
        treatment_mean = mean(treatment_selected_maxima)
        ceiling_mean = mean(treatment_candidate_maxima)
        gap_mean = mean(
            candidate - selected
            for candidate, selected in zip(
                treatment_candidate_maxima, treatment_selected_maxima, strict=True,
            )
        )
        selection_gates = {
            "mean_weekly_max_improves": treatment_mean > control_mean,
            "ge200_count_improves": (
                treatment_counts["200"] > control_counts["200"]
            ),
            "ge194_count_noninferior": (
                treatment_counts["194"] >= control_counts["194"]
            ),
            "ge210_count_noninferior": (
                treatment_counts["210"] >= control_counts["210"]
            ),
        }
        target_gates = {
            "mean_candidate_ceiling_at_least_205": ceiling_mean >= 205.0,
            "mean_conversion_gap_at_most_5": gap_mean <= 5.0,
        }
        selection_pass = all(selection_gates.values())
        target_pass = all(target_gates.values())
        if selection_pass and target_pass:
            disposition = "legal-soft-law-mocked-on-track"
            mocked_would_license["prospective_shadow_design"] = True
            mocked_would_license["target_200_track"] = True
        elif selection_pass:
            disposition = "legal-soft-law-mocked-incremental-only"
            mocked_would_license["prospective_shadow_design"] = True
        else:
            disposition = "legal-soft-law-mocked-historical-fail"
        historical_gate = {
            "control": {
                "mean_weekly_max": control_mean,
                "threshold_counts": control_counts,
            },
            "treatment": {
                "mean_weekly_max": treatment_mean,
                "threshold_counts": treatment_counts,
                "mean_candidate_ceiling": ceiling_mean,
                "mean_conversion_gap": gap_mean,
            },
            "selection_gates": selection_gates,
            "target_gates": target_gates,
            "selection_pass": selection_pass,
            "target_pass": target_pass,
        }

    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_status": PROTOCOL_STATUS,
        "mocked": True,
        "mode": mode,
        "disposition": disposition,
        "prerequisites": prerequisites,
        "snapshot": snapshot,
        "policy": {
            "hard_constraints": [
                "dk_classic_legality", "point_in_time", "exact_80",
                "fixed_budget", "provenance", "outcome_firewall",
            ],
            "soft_law_features": list(SOFT_LAW_FEATURES),
            "support_sleeves": {
                "incumbent": INCUMBENT_SUPPORT,
                "exact_one": EXACT_ONE_SUPPORT,
                "legality_only": "candidate_budget_minus_160",
            },
            "final_book_structure_quotas": {},
        },
        "slates": slate_reports,
        "historical_gate": historical_gate,
        "mocked_would_license": mocked_would_license,
        "licenses": licenses,
        "production_change_licensed": False,
    }


__all__ = [
    "A2A_PASS_DISPOSITION",
    "B1_MODEL_VERSION",
    "B1_REPORT_VERSION",
    "ENTRIES",
    "EXACT_ONE_SUPPORT",
    "INCUMBENT_SUPPORT",
    "LegalSoftLawError",
    "MIN_NATIVE_CANDIDATES",
    "PROTOCOL_ID",
    "PROTOCOL_STATUS",
    "SOFT_LAW_FEATURES",
    "SUPPORT_SLEEVES",
    "WORLD_BLOCKS",
    "WORLDS_PER_BLOCK",
    "canonical_json",
    "canonical_sha256",
    "evaluate_payload",
    "rank_treatment",
    "validate_prerequisites",
]
