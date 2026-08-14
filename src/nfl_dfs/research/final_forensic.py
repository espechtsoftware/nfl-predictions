"""Fail-closed primitives for the final preseason forensic closure.

This module deliberately separates two phases:

* manifest/inventory validation is outcome-free and is safe before the freeze;
* H/P/C/S decomposition consumes realized scores only after the manifest
  containing the immutable analyzer image has been committed.

The functions are pure apart from reading files supplied by the caller.  Cloud
and BigQuery access belongs in the guarded launcher/analyzer scripts so tests
can exercise every invariant offline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import pulp


PROTOCOL_ID = "20260814-final-preseason-forensic-v1"
TAILS = (240, 230, 220, 210, 200, 194, 187)
REQUIRED_OUTPUTS = (
    "provenance_and_arm_ledger",
    "opportunity_decomposition",
    "portfolio_entry_count_and_money",
    "player_capture_calibration_and_dependence",
    "construction_selection_regime_and_data_quality",
    "experiment_meta_analysis_and_kill_list",
    "week1_operational_readiness",
    "prospective_charter_and_opportunity_register",
    "exhaustion_certificate",
)
REQUIRED_MECHANISM_FAMILIES = (
    "player_marginals_and_calibration",
    "availability_and_role_change",
    "market_and_vendor_data",
    "game_and_player_dependence",
    "candidate_generation",
    "roster_construction",
    "portfolio_selection",
    "ownership_and_field_modeling",
    "contest_choice",
    "entry_count_and_bankroll",
    "data_and_pit_integrity",
    "operations",
)
LEDGER_STATUSES = frozenset({
    "selected",
    "rejected",
    "neutral",
    "invalid_repaired",
    "not_run_prerequisite_failed",
    "prospective_only",
    "duplicate_mechanism",
    "operational_complete",
    "deferred_with_falsifier",
})
REQUIRED_LEDGER_FIELDS = frozenset({
    "id",
    "family",
    "stage",
    "status",
    "protocol_paths",
    "result_paths",
    "execution_ids",
    "gate",
    "operator_override",
    "cloud_cost_status",
    "production_relevance",
    "transfer_boundary",
})


class FreezeManifestError(ValueError):
    """Raised when a closure freeze is incomplete or internally inconsistent."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def report_inventory(
    repo_root: str | Path,
    paths: Iterable[str | Path] | None = None,
) -> list[dict[str, Any]]:
    """Return a deterministic byte-level inventory of tracked report inputs."""
    root = Path(repo_root).resolve()
    selected = paths
    if selected is None:
        selected = sorted((root / "reports").glob("*.md"))
    rows: list[dict[str, Any]] = []
    for value in selected:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise FreezeManifestError(f"report outside repository: {path}") from exc
        if not path.is_file():
            raise FreezeManifestError(f"missing report: {relative}")
        name = path.name
        if name.endswith("-protocol.md"):
            kind = "protocol"
        elif name.endswith("-result.md"):
            kind = "result"
        elif "reconciliation" in name:
            kind = "reconciliation"
        elif "review" in name or "feedback" in name:
            kind = "review"
        elif "plan" in name or "roadmap" in name or "queue" in name:
            kind = "plan"
        elif "audit" in name or "inventory" in name:
            kind = "audit"
        else:
            kind = "supporting"
        rows.append({
            "path": relative.as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "kind": kind,
        })
    return sorted(rows, key=lambda row: row["path"])


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Hash canonical JSON, excluding an optional recorded self digest."""
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_freeze_manifest(
    manifest: Mapping[str, Any],
    *,
    repo_root: str | Path,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Validate the complete pre-outcome forensic freeze contract.

    The validator intentionally rejects open-ended ledger labels, unpinned
    images, unaccounted protocols, and output/taxonomy omissions.  It does not
    inspect or query a realized score.
    """
    root = Path(repo_root).resolve()
    failures: list[str] = []
    if manifest.get("protocol_id") != PROTOCOL_ID:
        failures.append("protocol_id differs")
    image = str(manifest.get("analysis_image", ""))
    if "@sha256:" not in image or len(image.rsplit("@sha256:", 1)[-1]) != 64:
        failures.append("analysis_image is not an immutable sha256 digest")
    if manifest.get("outcome_query_after_freeze_only") is not True:
        failures.append("outcome-query firewall is not enabled")
    production = manifest.get("production", {})
    for key in (
        "policy_id", "fallback_policy_id", "service_revision",
        "service_image", "component_panel", "position_panel", "cbwu_panel",
    ):
        if not str(production.get(key, "")).strip():
            failures.append(f"production.{key} is missing")

    outputs = manifest.get("analysis_contract", [])
    output_ids = [str(item.get("id", "")) for item in outputs]
    if tuple(output_ids) != REQUIRED_OUTPUTS:
        failures.append("analysis_contract does not exactly name nine outputs")
    for item in outputs:
        if not item.get("output_path") or not item.get("schema"):
            failures.append(f"analysis output is incomplete: {item.get('id')}")

    families = manifest.get("mechanism_taxonomy", [])
    family_ids = [str(item.get("id", "")) for item in families]
    if tuple(family_ids) != REQUIRED_MECHANISM_FAMILIES:
        failures.append("mechanism taxonomy is incomplete or reordered")
    for item in families:
        if not item.get("disposition_rule") or not item.get("falsifier_rule"):
            failures.append(f"taxonomy rule is incomplete: {item.get('id')}")

    ledger = manifest.get("arm_ledger", [])
    ledger_ids: set[str] = set()
    referenced_protocols: set[str] = set()
    referenced_results: set[str] = set()
    for row in ledger:
        missing = REQUIRED_LEDGER_FIELDS - set(row)
        if missing:
            failures.append(
                f"ledger {row.get('id', '<unknown>')} lacks {sorted(missing)}"
            )
        arm_id = str(row.get("id", ""))
        if not arm_id or arm_id in ledger_ids:
            failures.append(f"duplicate/empty ledger id: {arm_id!r}")
        ledger_ids.add(arm_id)
        if row.get("status") not in LEDGER_STATUSES:
            failures.append(f"ledger {arm_id} has open status {row.get('status')!r}")
        if row.get("family") not in REQUIRED_MECHANISM_FAMILIES:
            failures.append(f"ledger {arm_id} has unknown family")
        if not str(row.get("gate", "")).strip():
            failures.append(f"ledger {arm_id} has no gate/disposition text")
        if row.get("status") == "deferred_with_falsifier" and not str(
            row.get("transfer_boundary", "")
        ).strip():
            failures.append(f"deferred ledger {arm_id} lacks falsifier boundary")
        referenced_protocols.update(map(str, row.get("protocol_paths", [])))
        referenced_results.update(map(str, row.get("result_paths", [])))

    inventory = manifest.get("report_inventory", [])
    inventory_paths = [str(row.get("path", "")) for row in inventory]
    if len(inventory_paths) != len(set(inventory_paths)):
        failures.append("report_inventory repeats paths")
    protocol_paths = {
        row["path"] for row in inventory if row.get("kind") == "protocol"
    }
    exclusions = manifest.get("protocol_exclusions", [])
    excluded_paths = {str(row.get("path", "")) for row in exclusions}
    for row in exclusions:
        if not str(row.get("reason", "")).strip():
            failures.append(f"protocol exclusion lacks reason: {row.get('path')}")
    unaccounted = protocol_paths - referenced_protocols - excluded_paths
    if unaccounted:
        failures.append(f"unaccounted protocols: {sorted(unaccounted)}")
    overclaimed = referenced_protocols - protocol_paths
    if overclaimed:
        failures.append(f"ledger references uninventoried protocols: {sorted(overclaimed)}")

    result_paths = {
        row["path"] for row in inventory if row.get("kind") == "result"
    }
    result_exclusions = manifest.get("result_exclusions", [])
    excluded_results = {str(row.get("path", "")) for row in result_exclusions}
    for row in result_exclusions:
        if not str(row.get("reason", "")).strip():
            failures.append(f"result exclusion lacks reason: {row.get('path')}")
    unaccounted_results = result_paths - referenced_results - excluded_results
    if unaccounted_results:
        failures.append(f"unaccounted results: {sorted(unaccounted_results)}")
    overclaimed_results = referenced_results - result_paths
    if overclaimed_results:
        failures.append(
            "ledger references uninventoried results: "
            f"{sorted(overclaimed_results)}"
        )

    for panel in manifest.get("panels", []):
        for key in (
            "id", "table", "expected_rows", "expected_slates", "seasons",
            "prelock_row_hash", "estimand", "scope_boundary",
        ):
            if panel.get(key) in (None, "", []):
                failures.append(f"panel {panel.get('id')} lacks {key}")
    if len(manifest.get("panels", [])) < 3:
        failures.append("component, position and CBWU panel scopes are required")

    if verify_files:
        for row in inventory:
            path = root / str(row.get("path", ""))
            if not path.is_file():
                failures.append(f"inventoried file missing: {row.get('path')}")
                continue
            if path.stat().st_size != int(row.get("bytes", -1)):
                failures.append(f"inventoried size drift: {row.get('path')}")
            elif sha256_file(path) != row.get("sha256"):
                failures.append(f"inventoried hash drift: {row.get('path')}")
        for artifact in manifest.get("artifacts", []):
            path = root / str(artifact.get("path", ""))
            if not path.is_file():
                failures.append(f"artifact missing: {artifact.get('path')}")
            elif sha256_file(path) != artifact.get("sha256"):
                failures.append(f"artifact hash drift: {artifact.get('path')}")

    recorded_digest = manifest.get("manifest_sha256")
    computed_digest = manifest_digest(manifest)
    if recorded_digest and recorded_digest != computed_digest:
        failures.append("manifest_sha256 differs")
    if failures:
        raise FreezeManifestError("; ".join(failures))
    return {
        "protocol_id": PROTOCOL_ID,
        "manifest_sha256": computed_digest,
        "reports": len(inventory),
        "protocols": len(protocol_paths),
        "ledger_entries": len(ledger),
        "outputs": len(outputs),
        "mechanism_families": len(families),
    }


def _normalise_player_frame(players: pd.DataFrame) -> pd.DataFrame:
    required = {"id", "pos", "team", "opp", "game_id", "salary", "actual"}
    missing = required - set(players)
    if missing:
        raise ValueError(f"player frame lacks {sorted(missing)}")
    frame = players.copy()
    frame["id"] = frame.id.astype(str)
    frame["pos"] = frame.pos.astype(str).str.upper().replace({"DEF": "DST"})
    frame["team"] = frame.team.astype(str)
    frame["opp"] = frame.opp.astype(str)
    frame["game_id"] = frame.game_id.astype(str)
    frame["salary"] = pd.to_numeric(frame.salary, errors="raise").astype(int)
    frame["actual"] = pd.to_numeric(frame.actual, errors="raise").astype(float)
    if frame.id.duplicated().any():
        raise ValueError("player ids repeat within slate")
    if not frame.pos.isin(("QB", "RB", "WR", "TE", "DST")).all():
        raise ValueError("player frame contains an unsupported position")
    if not np.isfinite(frame.actual).all() or not np.isfinite(frame.salary).all():
        raise ValueError("player frame contains non-finite score/salary")
    return frame.sort_values("id", kind="stable").reset_index(drop=True)


def audit_roster(
    players: pd.DataFrame,
    roster_ids: Sequence[str],
    *,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Independently reconstruct one roster's score and frozen legality."""
    frame = _normalise_player_frame(players).set_index("id", drop=False)
    ids = tuple(map(str, roster_ids))
    failures: list[str] = []
    if len(ids) != 9 or len(set(ids)) != 9:
        failures.append("roster does not contain nine unique ids")
    unknown = sorted(set(ids) - set(frame.index))
    if unknown:
        failures.append(f"unknown player ids: {unknown}")
        chosen = frame.iloc[0:0]
    else:
        chosen = frame.loc[list(ids)]
    counts = chosen.pos.value_counts().to_dict()
    expected = {
        "QB": counts.get("QB", 0) == 1,
        "DST": counts.get("DST", 0) == 1,
        "RB": 2 <= counts.get("RB", 0) <= 3,
        "WR": 3 <= counts.get("WR", 0) <= 4,
        "TE": 1 <= counts.get("TE", 0) <= 2,
    }
    failures.extend(f"invalid {pos} count" for pos, valid in expected.items() if not valid)
    salary = int(chosen.salary.sum())
    if not min_salary <= salary <= salary_cap:
        failures.append("salary outside frozen range")
    if chosen.team.value_counts().max() > 8:
        failures.append("more than eight players from one team")
    if chosen.game_id.nunique() < 2:
        failures.append("fewer than two games")
    qbs = chosen[chosen.pos.eq("QB")]
    if len(qbs) == 1:
        team = str(qbs.iloc[0].team)
        if not ((chosen.team.eq(team)) & chosen.pos.isin(("WR", "TE"))).any():
            failures.append("QB lacks a same-team WR/TE")
    if (chosen[chosen.pos.eq("RB")].team.value_counts() > 1).any():
        failures.append("two RBs from one team")
    dsts = chosen[chosen.pos.eq("DST")]
    if len(dsts) == 1:
        dst_opp = str(dsts.iloc[0].opp)
        if ((chosen.pos.eq("RB")) & chosen.team.eq(dst_opp)).any():
            failures.append("RB faces selected DST")
    return {
        "valid": not failures,
        "failures": failures,
        "salary": salary,
        "actual_score": float(chosen.actual.sum()),
        "players": sorted(ids),
    }


def _solve_oracle(
    players: pd.DataFrame,
    allowed_ids: set[str] | None = None,
    *,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Solve the exact frozen legal-lineup oracle with deterministic ties."""
    frame = _normalise_player_frame(players)
    if allowed_ids is not None:
        frame = frame[frame.id.isin(set(map(str, allowed_ids)))].copy()
    if frame.empty:
        raise ValueError("oracle player support is empty")
    rows = list(frame.itertuples(index=False))
    problem = pulp.LpProblem("forensic_oracle", pulp.LpMaximize)
    decision = {
        row.id: pulp.LpVariable(f"x_{index}", cat="Binary")
        for index, row in enumerate(rows)
    }
    score_expr = pulp.lpSum(decision[row.id] * row.actual for row in rows)
    salary_expr = pulp.lpSum(decision[row.id] * row.salary for row in rows)
    problem += score_expr
    problem += salary_expr <= salary_cap
    problem += salary_expr >= min_salary
    problem += pulp.lpSum(decision.values()) == 9

    def count(position: str):
        return pulp.lpSum(decision[row.id] for row in rows if row.pos == position)

    problem += count("QB") == 1
    problem += count("DST") == 1
    problem += count("RB") >= 2
    problem += count("RB") <= 3
    problem += count("WR") >= 3
    problem += count("WR") <= 4
    problem += count("TE") >= 1
    problem += count("TE") <= 2
    for team in sorted(frame.team.unique()):
        ids = [row.id for row in rows if row.team == team]
        problem += pulp.lpSum(decision[player] for player in ids) <= 8
        rbs = [row.id for row in rows if row.team == team and row.pos == "RB"]
        if len(rbs) > 1:
            problem += pulp.lpSum(decision[player] for player in rbs) <= 1
    games = sorted(frame.game_id.unique())
    if len(games) >= 2:
        for game in games:
            problem += pulp.lpSum(
                decision[row.id] for row in rows if row.game_id != game
            ) >= 1
    for qb in (row for row in rows if row.pos == "QB"):
        catchers = [
            row.id for row in rows
            if row.team == qb.team and row.pos in ("WR", "TE")
        ]
        problem += pulp.lpSum(decision[player] for player in catchers) >= decision[qb.id]
    for dst in (row for row in rows if row.pos == "DST"):
        for rb in (
            row for row in rows if row.pos == "RB" and row.team == dst.opp
        ):
            problem += decision[dst.id] + decision[rb.id] <= 1

    solver = pulp.PULP_CBC_CMD(msg=0)
    problem.solve(solver)
    if pulp.LpStatus[problem.status] != "Optimal":
        raise ValueError(f"oracle is {pulp.LpStatus[problem.status]}")
    optimum = float(pulp.value(score_expr))
    # Freeze the primary optimum, then prefer the lowest stable id-rank sum.
    problem += score_expr >= optimum - 1e-7
    problem.sense = pulp.LpMinimize
    rank = {row.id: index + 1 for index, row in enumerate(rows)}
    problem.setObjective(pulp.lpSum(decision[row.id] * rank[row.id] for row in rows))
    problem.solve(solver)
    if pulp.LpStatus[problem.status] != "Optimal":
        raise ValueError("oracle deterministic tie solve failed")
    chosen = sorted(row.id for row in rows if decision[row.id].value() > 0.5)
    audit = audit_roster(
        frame, chosen, min_salary=min_salary, salary_cap=salary_cap
    )
    if not audit["valid"] or not np.isclose(
        audit["actual_score"], optimum, rtol=0.0, atol=1e-6
    ):
        raise ValueError("oracle failed independent legality/score reconstruction")
    audit["solver_status"] = "Optimal"
    return audit


def decompose_slate(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    selected_rosters: Sequence[str] | None = None,
    expected_entries: int = 80,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Compute the corrected H/P/C/S decomposition for one frozen slate."""
    frame = _normalise_player_frame(players)
    required = {"players", "actual_score"}
    if not required <= set(candidates):
        raise ValueError(f"candidate frame lacks {sorted(required - set(candidates))}")
    pool = candidates.copy()
    roster_ids: list[tuple[str, ...]] = []
    audits: list[dict[str, Any]] = []
    for row in pool.itertuples(index=False):
        ids = tuple(item for item in str(row.players).split(",") if item)
        audit = audit_roster(
            frame, ids, min_salary=min_salary, salary_cap=salary_cap
        )
        if not audit["valid"]:
            raise ValueError(f"illegal candidate roster: {audit['failures']}")
        if not np.isclose(
            audit["actual_score"], float(row.actual_score), rtol=0.0, atol=1e-6
        ):
            raise ValueError("candidate actual score fails reconstruction")
        roster_ids.append(ids)
        audits.append(audit)
    canonical = [tuple(sorted(ids)) for ids in roster_ids]
    if len(canonical) != len(set(canonical)):
        raise ValueError("candidate pool contains duplicate rosters")
    pool = pool.reset_index(drop=True)
    pool["roster_key"] = [",".join(ids) for ids in canonical]

    if selected_rosters is None:
        if "selected" not in pool:
            raise ValueError("selected membership is absent")
        selected = pool[pool.selected.fillna(False).astype(bool)].copy()
        if "selected_rank" in selected:
            selected = selected.sort_values("selected_rank", kind="stable")
        selected_keys = selected.roster_key.tolist()
    else:
        selected_keys = [
            ",".join(sorted(item for item in str(value).split(",") if item))
            for value in selected_rosters
        ]
        if not set(selected_keys) <= set(pool.roster_key):
            raise ValueError("selected roster is absent from the candidate pool")
        selected = pool.set_index("roster_key").loc[selected_keys].reset_index()
    if len(selected_keys) != expected_entries or len(set(selected_keys)) != expected_entries:
        raise ValueError(f"selected book is not exact-{expected_entries}")

    support = set().union(*(set(ids) for ids in roster_ids)) if roster_ids else set()
    full_oracle = _solve_oracle(
        frame, min_salary=min_salary, salary_cap=salary_cap
    )
    support_oracle = _solve_oracle(
        frame, support, min_salary=min_salary, salary_cap=salary_cap
    )
    candidate_row = pool.sort_values(
        ["actual_score", "roster_key"], ascending=[False, True], kind="stable"
    ).iloc[0]
    selected_row = selected.sort_values(
        ["actual_score", "roster_key"], ascending=[False, True], kind="stable"
    ).iloc[0]
    h_score = float(full_oracle["actual_score"])
    p_score = float(support_oracle["actual_score"])
    c_score = float(candidate_row.actual_score)
    s_score = float(selected_row.actual_score)
    if not (h_score + 1e-6 >= p_score >= c_score - 1e-6 >= s_score - 1e-6):
        raise ValueError("H/P/C/S ordering invariant failed")
    return {
        "H": full_oracle,
        "P": support_oracle,
        "C": {
            "actual_score": c_score,
            "players": str(candidate_row.roster_key).split(","),
        },
        "S": {
            "actual_score": s_score,
            "players": str(selected_row.roster_key).split(","),
        },
        "gaps": {
            "player_support": h_score - p_score,
            "construction": p_score - c_score,
            "selection": c_score - s_score,
        },
        "thresholds": {
            str(tail): {
                "H": h_score >= tail,
                "P": p_score >= tail,
                "C": c_score >= tail,
                "S": s_score >= tail,
                "first_failed_layer": (
                    "player_support" if h_score >= tail > p_score
                    else "construction" if p_score >= tail > c_score
                    else "selection" if c_score >= tail > s_score
                    else "none"
                ),
            }
            for tail in TAILS
        },
        "candidate_count": len(pool),
        "supported_player_count": len(support),
        "selected_count": len(selected_keys),
    }


__all__ = [
    "FreezeManifestError",
    "LEDGER_STATUSES",
    "PROTOCOL_ID",
    "REQUIRED_MECHANISM_FAMILIES",
    "REQUIRED_OUTPUTS",
    "TAILS",
    "audit_roster",
    "decompose_slate",
    "manifest_digest",
    "report_inventory",
    "sha256_file",
    "validate_freeze_manifest",
]
