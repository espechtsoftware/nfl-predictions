"""Pure guards and summaries for the frozen served-tail Stage B replay."""

from __future__ import annotations

import json
import re

import pandas as pd

from .candidate_union import tail_first_decision
from .panel_compare import metrics, slate_scores


SOURCE_PANEL = "20260810-lockfix-e80-k1-role12union-8677d21"
EVALUATION_SEASONS = (2023, 2024, 2025)
HISTORICAL_SEASONS = (2019, 2021, 2022)
SOURCE_SEASONS = HISTORICAL_SEASONS + EVALUATION_SEASONS
SOURCE_CODE_SHA = "8677d21"
SCALE = 1.025
CANDIDATE_MEAN_ATOL = 1e-4
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)


def _generator_family(value: str) -> str:
    """Collapse per-draw provenance without losing mechanism identity."""
    tag = str(value)
    if tag.startswith("epi:role_draw:"):
        return "epi:role_draw"
    return tag


def generator_summary(rows: pd.DataFrame) -> list[dict]:
    """Summarize generator provenance without unbounded per-seed log output."""
    if rows.empty:
        return []
    provenance = rows.all_tags.map(
        lambda value: json.loads(value) if isinstance(value, str) else []
    ).map(lambda tags: sorted({_generator_family(tag) for tag in tags}))
    generators = sorted({tag for tags in provenance for tag in tags})
    report: list[dict] = []
    for generator in generators:
        has = provenance.map(lambda tags, tag=generator: tag in tags)
        report.append({
            "generator": generator,
            "candidates": int(has.sum()),
            "selected": int((has & rows.selected).sum()),
            "exclusive_candidates": int(
                (has & provenance.map(len).eq(1)).sum()),
        })
    return report


def panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def lever_values(value: str) -> dict[str, str]:
    """Parse persisted KEY=value fields, including comma-bearing values."""
    raw = str(value or "")
    matches = list(re.finditer(r"(?:^|,)([A-Z][A-Z0-9_]*)=", raw))
    out: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        out[match.group(1)] = raw[start:stop].rstrip(",")
    return out


def expected_slate_pairs(seasons: tuple[int, ...]) -> set[tuple[int, int]]:
    return {
        (season, week)
        for season in seasons
        for week in range(1, 18 if season == 2019 else 19)
    }


def validate_candidate_panel(
    name: str,
    rows: pd.DataFrame,
    *,
    seasons: tuple[int, ...],
    promoted: bool,
    expected_code_sha: str | None = None,
    allow_season_config: bool = False,
) -> list[str]:
    """Validate exact slate/entry/label/provenance mechanics."""
    failures: list[str] = []
    required = {
        "season", "week", "cand_ix", "players", "selected",
        "selected_rank", "actual_score", "labels_complete",
        "research_eligible", "code_sha", "config_hash", "lever_env",
        "seeds",
    }
    missing = required - set(rows.columns)
    if missing:
        return [f"{name} missing columns {sorted(missing)}"]
    if rows.empty:
        return [f"{name} is empty"]

    got = set(zip(rows.season.astype(int), rows.week.astype(int)))
    expected = expected_slate_pairs(seasons)
    if got != expected:
        failures.append(
            f"{name} slate set differs: missing={len(expected - got)} "
            f"unexpected={len(got - expected)}")
    if rows.duplicated(["season", "week", "players"]).any():
        failures.append(f"{name} has duplicate slate/roster keys")
    if rows.duplicated(["season", "week", "cand_ix"]).any():
        failures.append(f"{name} has duplicate candidate indexes")
    if not rows.labels_complete.fillna(False).all():
        failures.append(f"{name} has incomplete labels")
    if pd.to_numeric(rows.actual_score, errors="coerce").isna().any():
        failures.append(f"{name} has missing actual scores")
    if not rows.research_eligible.eq(promoted).all():
        failures.append(f"{name} has wrong research eligibility")
    for column in ("code_sha", "seeds"):
        if rows[column].fillna("").astype(str).nunique(dropna=False) != 1:
            failures.append(f"{name} has mixed {column}")
    for column in ("config_hash", "lever_env"):
        if allow_season_config:
            counts = rows.groupby("season")[column].apply(
                lambda values: values.fillna("").astype(str).nunique(
                    dropna=False))
            if not counts.eq(1).all():
                failures.append(f"{name} has mixed {column} within a season")
        elif rows[column].fillna("").astype(str).nunique(dropna=False) != 1:
            failures.append(f"{name} has mixed {column}")
    if expected_code_sha is not None and not rows.code_sha.astype(str).eq(
            expected_code_sha).all():
        failures.append(f"{name} code SHA is not {expected_code_sha}")

    grouped = rows.groupby(["season", "week"], sort=False)
    selected = grouped.selected.sum()
    if not selected.eq(80).all():
        failures.append(f"{name} does not select exactly 80 every slate")
    for (season, week), slate in grouped:
        picked = slate.loc[slate.selected].sort_values("selected_rank")
        if picked.selected_rank.astype(int).tolist() != list(range(80)):
            failures.append(
                f"{name} selected ranks are invalid at {season} week {week}")
            break
    return failures


def mechanism_failures(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidate_audit: dict,
    *,
    treatment_code_sha: str,
) -> list[str]:
    """Require the fitted scale to be the only replay lever change."""
    failures: list[str] = []
    if source.empty or treatment.empty:
        return failures
    if source.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("source and treatment seed identities differ")
    if treatment.code_sha.iloc[0] != treatment_code_sha:
        failures.append("treatment code SHA differs from immutable image commit")

    source_levers = lever_values(source.lever_env.iloc[0])
    treatment_levers = lever_values(treatment.lever_env.iloc[0])
    source_scale = float(source_levers.get("SERVED_TAIL_SCALE", "1") or 1)
    treatment_scale = float(
        treatment_levers.get("SERVED_TAIL_SCALE", "nan"))
    if source_scale not in (0.0, 1.0):
        failures.append("source served-tail scale is not identity")
    if treatment_scale != SCALE:
        failures.append(f"treatment served-tail scale is not {SCALE}")

    frozen = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
    }
    for key, value in frozen.items():
        if source_levers.get(key) != value:
            failures.append(f"source {key} is not {value}")
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not {value}")
    source_other = {
        key: value for key, value in source_levers.items()
        if key != "SERVED_TAIL_SCALE"
    }
    treatment_other = {
        key: value for key, value in treatment_levers.items()
        if key != "SERVED_TAIL_SCALE"
    }
    if source_other != treatment_other:
        failures.append("treatment changes replay levers other than served-tail scale")

    if (feature_audit.get("source_rows")
            != feature_audit.get("treatment_rows")):
        failures.append("source and treatment player-row counts differ")
    for field in (
        "source_only_rows", "treatment_only_rows", "mismatch_rows",
    ):
        if feature_audit.get(field):
            failures.append(f"player snapshots differ in {field}")
    if float(feature_audit.get("max_numeric_abs_delta", 0.0)) > 1e-12:
        failures.append("player snapshot numeric values differ")

    if candidate_audit.get("paired_slates") != 54:
        failures.append("candidate audit does not cover 54 evaluation slates")
    if candidate_audit.get("common_rows", 0) <= 0:
        failures.append("source and treatment have no shared rosters")
    for field in ("common_actual_mismatch", "common_sim_mean_mismatch"):
        if candidate_audit.get(field):
            failures.append(f"shared candidate rows differ in {field}")
    return failures


def combine_source_and_treatment(
    source_rows: pd.DataFrame,
    treatment_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return source, evaluation treatment and full 107-slate challenger."""
    source = slate_scores(source_rows)
    treatment = slate_scores(treatment_rows)
    historical = source[source.season.isin(HISTORICAL_SEASONS)]
    combined = pd.concat([historical, treatment], ignore_index=True)
    if set(zip(combined.season.astype(int), combined.week.astype(int))) != \
            expected_slate_pairs(SOURCE_SEASONS):
        raise ValueError("combined challenger is not the exact 107-slate panel")
    return source, treatment, combined


def lineup_decision(source_metrics: dict, treatment_metrics: dict) -> dict:
    """Apply the frozen tail-first law, flagging any mixed result for review."""
    decision = tail_first_decision(source_metrics, treatment_metrics)
    mixed = any(value < 0 for value in decision["deltas"].values()) and any(
        value > 0 for value in decision["deltas"].values())
    decision["mixed_high_threshold_result"] = mixed
    decision["operator_review_required"] = bool(
        decision["promotion_candidate"] and mixed)
    decision["passes"] = bool(
        decision["promotion_candidate"]
        and decision["pareto_nonworse_210_plus"])
    return decision


def comparison_report(
    source_rows: pd.DataFrame,
    treatment_rows: pd.DataFrame,
) -> dict:
    """Build score diagnostics after all external mechanical audits pass."""
    source, treatment, combined = combine_source_and_treatment(
        source_rows, treatment_rows)
    source_eval = source[source.season.isin(EVALUATION_SEASONS)].copy()
    source_metrics = metrics(source)
    combined_metrics = metrics(combined)
    evaluation_source_metrics = metrics(source_eval)
    evaluation_treatment_metrics = metrics(treatment)
    decision = lineup_decision(source_metrics, combined_metrics)

    changed = source_eval.merge(
        treatment, on=["season", "week"], suffixes=("_source", "_treatment"),
        validate="one_to_one",
    )
    changed["selected_delta"] = (
        changed.selected_best_treatment - changed.selected_best_source)
    changed["oracle_delta"] = changed.oracle_treatment - changed.oracle_source
    changed = changed[
        changed.selected_delta.abs().gt(1e-9)
        | changed.oracle_delta.abs().gt(1e-9)
    ].sort_values(["selected_delta", "oracle_delta"], ascending=False)

    season_metrics: list[dict] = []
    for season in SOURCE_SEASONS:
        control = source[source.season.eq(season)]
        challenge = combined[combined.season.eq(season)]
        row: dict[str, float | int] = {
            "season": season,
            "slates": int(len(control)),
            "source_mean_best": float(control.selected_best.mean()),
            "treatment_mean_best": float(challenge.selected_best.mean()),
        }
        for threshold in (187, 194, 200, 210, 220, 230, 240):
            row[f"source_{threshold}"] = int(
                control.selected_best.ge(threshold).sum())
            row[f"treatment_{threshold}"] = int(
                challenge.selected_best.ge(threshold).sum())
        season_metrics.append(row)
    return {
        "source_metrics": source_metrics,
        "combined_treatment_metrics": combined_metrics,
        "evaluation_source_metrics": evaluation_source_metrics,
        "evaluation_treatment_metrics": evaluation_treatment_metrics,
        "season_metrics": season_metrics,
        "changed_weeks": changed.to_dict("records"),
        "tail_first_decision": decision,
    }
