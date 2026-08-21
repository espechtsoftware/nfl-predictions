#!/usr/bin/env python3
"""REVIEWER INSTRUMENT — independent recomputation of the A7 co-primaries.

This is not part of the A7 arm. It exists to answer one question after
the fact: does the number the finisher recorded match the number the
per-slate receipts actually imply?

It deliberately shares NO code with `finish_a7_select_ladder.py`,
`research/a7_select_ladder.py`, or `research/paired_max_stats.py`. The
sign-flip test, signed-rank statistic, threshold grid and mean delta are
re-implemented here from their definitions so that a defect in the
production evaluation path cannot hide by being reused in its own check.

Why this matters for this specific arm: A7 reads outcomes exactly once
and its protocol forbids retry, refit and re-dose. Three defects in this
repository's history (the ownership-fade mislabel, the GREEN2 env typo,
the TDLEDGER season-pooling error) lived in evaluation code, produced
well-formed output, and were caught only by instrument audit. A
disposition looks equally authoritative whether or not the arithmetic
underneath it is right.

Usage:
    python scripts/review_verify_a7_coprimaries.py --result <result.json>

Exit code 0 means every recomputed statistic agreed with the recorded
one; 1 means at least one disagreed, which is a finding to investigate
BEFORE the disposition is treated as settled.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import comb, isfinite
from pathlib import Path
import re
from typing import Any, Final, Sequence

import numpy as np

# Frozen in the A7 protocol; restated here rather than imported so the
# check does not inherit a wrong constant from the code under review.
RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v2"
RESULT_VERSION: Final = "a7-select-ladder-phase-s-incumbent-v2"
PAIRED_PROTOCOL_ID: Final = "20260818-paired-max-coprimary-v1"
ENTRY_COUNT: Final = 80
PREFIX_COUNTS: Final = (4, 14, 80)
THRESHOLDS: Final = (187, 194, 200, 210, 220, 230, 240)
EXACT_NONZERO_LIMIT: Final = 20
MONTE_CARLO_RESAMPLES: Final = 200_000
MONTE_CARLO_SEED: Final = 20_260_818
CHUNK: Final = 1 << 16
EPSILON: Final = 1e-12
NONINFERIORITY_FLOOR: Final = -1

FINAL_LEDGER_NAMES: Final = frozenset({
    "manifest.json", "prepared.sha256", "launch.sha256",
    "launch-intent.json", "executions.txt", "lease-receipt.json",
    "freeze-manifest.json", "smoke-preflight.json",
    "support-preflight.json", "smoke-terminal.json",
    "support-terminal.json", "execution.json", "object-metadata.json",
    "live-lease-metadata.json", "job-claim-metadata.json",
    "science-replay.json", "report.json", "completion.txt",
})


class VerificationError(RuntimeError):
    """The supplied path is not an immutable completed A7-v2 harvest."""


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _strict_json(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is absent or linked")
    raw = path.read_bytes()

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs_hook,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite constant: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise VerificationError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise VerificationError(f"{label} is not canonical JSON")
    return value


def _completion(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError("strict completion receipt is absent or linked")
    raw = path.read_text(encoding="utf-8")
    if not raw.endswith("\n") or "\r" in raw:
        raise VerificationError("strict completion receipt encoding differs")
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if line.count("=") != 1:
            raise VerificationError("strict completion receipt row differs")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise VerificationError("strict completion receipt key differs")
        values[key] = value
    expected_keys = {
        "validated_at", "run_id", "disposition", "executions", "objects",
        "scientific_bodies", "strict_science_replay", "report_sha256",
        "science_replay_sha256", "freeze_manifest_sha256",
        "uses_realized_outcomes", "actual_score_query_executed",
        "production_change_licensed", "prospective_shadow_licensed",
        "historical_outcome_lease_release_licensed",
        "historical_outcome_lease_released",
    }
    fixed = {
        "run_id": RUN_ID, "executions": "1", "objects": "1",
        "scientific_bodies": "1", "strict_science_replay": "true",
        "uses_realized_outcomes": "true",
        "actual_score_query_executed": "true",
        "production_change_licensed": "false",
        "prospective_shadow_licensed": "false",
        "historical_outcome_lease_release_licensed": "true",
        "historical_outcome_lease_released": "false",
    }
    if set(values) != expected_keys or any(
        values.get(key) != expected for key, expected in fixed.items()
    ):
        raise VerificationError("strict realized completion receipt differs")
    return values


def _fully_harvested_result(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    if path.is_symlink() or path.name != "report.json" or not path.is_file():
        raise VerificationError("--result must be the final local report.json")
    directory = path.parent
    if directory.is_symlink() or not directory.is_dir():
        raise VerificationError("harvest directory is absent or linked")
    ledger = directory / "finish.sha256"
    if ledger.is_symlink() or not ledger.is_file():
        raise VerificationError("strict finish ledger is absent or linked")
    rows: dict[str, str] = {}
    ledger_text = ledger.read_text(encoding="utf-8")
    if not ledger_text.endswith("\n") or "\r" in ledger_text:
        raise VerificationError("strict finish ledger encoding differs")
    ledger_names: list[str] = []
    for line in ledger_text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None or match.group(2) in rows:
            raise VerificationError("strict finish ledger row differs")
        ledger_names.append(match.group(2))
        rows[match.group(2)] = match.group(1)
    if set(rows) != FINAL_LEDGER_NAMES or ledger_names != sorted(ledger_names):
        raise VerificationError("strict finish ledger population differs")
    for name, digest in rows.items():
        candidate = directory / name
        if candidate.is_symlink() or not candidate.is_file() or _sha(
            candidate
        ) != digest:
            raise VerificationError(f"strict finish ledger hash differs: {name}")
    completion = _completion(directory / "completion.txt")
    result = _strict_json(path, label="harvested A7 result")
    replay = _strict_json(
        directory / "science-replay.json", label="strict science replay",
    )
    if completion.get("report_sha256") != _sha(path) or completion.get(
        "science_replay_sha256"
    ) != _sha(directory / "science-replay.json") or completion.get(
        "freeze_manifest_sha256"
    ) != _sha(directory / "freeze-manifest.json") or replay.get(
        "version"
    ) != "a7-strict-science-replay-v1" or replay.get("run_id") != RUN_ID or \
            replay.get("outcome_replayed") is not True or replay.get(
                "baseline_reproduced"
            ) is not True or replay.get("uses_realized_outcomes") is not True or \
            replay.get("actual_score_query_executed") is not True or replay.get(
                "production_change_licensed"
            ) is not False or replay.get("disposition") != completion.get(
                "disposition"
            ):
        raise VerificationError("strict completed replay binding differs")
    return result, completion


def _pairs(result: dict, count: int) -> tuple[np.ndarray, np.ndarray, list]:
    rows = result.get("slates")
    if not isinstance(rows, list) or len(rows) != 54:
        raise VerificationError("result must contain exactly 54 per-slate rows")
    expected = [
        (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    key = str(count)
    control, treatment, keys = [], [], []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("season")) is not int or type(
            row.get("week")
        ) is not int or row.get("uses_realized_outcomes") is not True:
            raise VerificationError("per-slate realized receipt differs")
        keys.append((row["season"], row["week"]))
        for arm, target in (("control", control), ("treatment", treatment)):
            value = row.get(arm)
            realized = value.get("realized") if isinstance(value, dict) else None
            if not isinstance(realized, dict) or set(realized) != {
                "identities", "scores", "prefix_maxima",
            }:
                raise VerificationError(f"{arm} realized receipt differs")
            scores = realized.get("scores")
            identities = realized.get("identities")
            maxima = realized.get("prefix_maxima")
            if not isinstance(identities, list) or len(identities) != ENTRY_COUNT or \
                    len({
                        tuple(identity) for identity in identities
                        if isinstance(identity, list) and all(
                            isinstance(player, str) and player for player in identity
                        )
                    }) != ENTRY_COUNT or not isinstance(scores, list) or len(
                        scores
                    ) != ENTRY_COUNT or not all(
                type(item) in (int, float) and isfinite(float(item))
                for item in scores
            ) or not isinstance(maxima, dict) or set(maxima) != {
                str(item) for item in PREFIX_COUNTS
            }:
                raise VerificationError(f"{arm} ordered-book receipt differs")
            retained = maxima.get(key)
            if type(retained) not in (int, float) or not isfinite(
                float(retained)
            ) or float(retained) != float(max(float(item) for item in scores[:count])):
                raise VerificationError(f"{arm} retained S{count} differs")
            target.append(float(retained))
    if keys != expected:
        raise VerificationError("per-slate lattice or order differs")
    left, right = np.asarray(control, dtype=float), np.asarray(treatment, dtype=float)
    if not (np.isfinite(left).all() and np.isfinite(right).all()):
        raise VerificationError("per-slate maxima are non-finite")
    return left, right, keys


def _sign_flip_inference(diffs: np.ndarray) -> dict[str, Any]:
    """Both frozen two-sided sign-flip tests from one deterministic stream."""
    nonzero = diffs[diffs != 0.0]
    if not len(nonzero):
        return {
            "method": "degenerate", "n_nonzero": 0,
            "p_mean_two_sided": 1.0, "p_signed_rank_two_sided": 1.0,
            "signed_rank_statistic": 0.0,
        }
    magnitudes = np.abs(nonzero)
    order = np.argsort(magnitudes, kind="mergesort")
    ranks = np.empty(len(nonzero), dtype=float)
    sorted_magnitudes = magnitudes[order]
    start = 0
    while start < len(sorted_magnitudes):
        stop = start
        while stop + 1 < len(sorted_magnitudes) and sorted_magnitudes[
            stop + 1
        ] == sorted_magnitudes[start]:
            stop += 1
        ranks[order[start:stop + 1]] = (start + stop) / 2.0 + 1.0
        start = stop + 1
    observed_sum = float(nonzero.sum())
    observed_rank = float(ranks[nonzero > 0].sum())
    rank_center = float(ranks.sum()) / 2.0
    hits_mean = hits_rank = 0
    if len(nonzero) <= EXACT_NONZERO_LIMIT:
        total = 1 << len(nonzero)
        bits = np.arange(len(nonzero))
        for first in range(0, total, CHUNK):
            stop = min(first + CHUNK, total)
            codes = np.arange(first, stop, dtype=np.int64)
            flips = ((codes[:, None] >> bits[None, :]) & 1).astype(float)
            signs = 1.0 - 2.0 * flips
            signed_sums = signs @ nonzero
            positive_ranks = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_mean += int((
                np.abs(signed_sums) >= abs(observed_sum) - EPSILON
            ).sum())
            hits_rank += int((
                np.abs(positive_ranks - rank_center)
                >= abs(observed_rank - rank_center) - EPSILON
            ).sum())
        method = "exact_enumeration"
        p_mean = hits_mean / total
        p_rank = hits_rank / total
    else:
        rng = np.random.default_rng(MONTE_CARLO_SEED)
        completed = 0
        while completed < MONTE_CARLO_RESAMPLES:
            take = min(CHUNK, MONTE_CARLO_RESAMPLES - completed)
            signs = rng.choice((-1.0, 1.0), size=(take, len(nonzero)))
            signed_sums = signs @ nonzero
            positive_ranks = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_mean += int((
                np.abs(signed_sums) >= abs(observed_sum) - EPSILON
            ).sum())
            hits_rank += int((
                np.abs(positive_ranks - rank_center)
                >= abs(observed_rank - rank_center) - EPSILON
            ).sum())
            completed += take
        method = "monte_carlo"
        p_mean = (hits_mean + 1) / (MONTE_CARLO_RESAMPLES + 1)
        p_rank = (hits_rank + 1) / (MONTE_CARLO_RESAMPLES + 1)
    return {
        "method": method, "n_nonzero": len(nonzero),
        "p_mean_two_sided": float(min(1.0, p_mean)),
        "p_signed_rank_two_sided": float(min(1.0, p_rank)),
        "signed_rank_statistic": observed_rank,
    }


def _mcnemar(control_only: int, treatment_only: int) -> float | None:
    discordant = control_only + treatment_only
    if discordant == 0:
        return None
    smaller = min(control_only, treatment_only)
    tail = sum(comb(discordant, value) for value in range(smaller + 1)) / (
        2 ** discordant
    )
    return float(min(1.0, 2.0 * tail))


def paired_report(control: Sequence[float], treatment: Sequence[float]) -> tuple[
    dict[str, Any], bool,
]:
    left, right = np.asarray(control, dtype=float), np.asarray(treatment, dtype=float)
    if left.ndim != 1 or right.ndim != 1 or len(left) != len(right) or len(
        left
    ) < 2 or not (np.isfinite(left).all() and np.isfinite(right).all()):
        raise VerificationError("paired input vectors differ")
    diffs = right - left
    inference = _sign_flip_inference(diffs)
    grid = []
    for threshold in THRESHOLDS:
        control_clear = left >= threshold
        treatment_clear = right >= threshold
        control_only = int(np.count_nonzero(control_clear & ~treatment_clear))
        treatment_only = int(np.count_nonzero(treatment_clear & ~control_clear))
        grid.append({
            "threshold": threshold,
            "control": int(np.count_nonzero(control_clear)),
            "treatment": int(np.count_nonzero(treatment_clear)),
            "discordant_control_only": control_only,
            "discordant_treatment_only": treatment_only,
            "mcnemar_exact_p_two_sided": _mcnemar(control_only, treatment_only),
        })
    ranks_positive = inference["signed_rank_statistic"]
    nonzero = diffs[diffs != 0.0]
    rank_total = len(nonzero) * (len(nonzero) + 1) / 2.0
    return ({
        "protocol_id": PAIRED_PROTOCOL_ID,
        "labels": ["control", "treatment"],
        "n_slates": int(len(diffs)),
        "mean_diff": float(diffs.mean()),
        "median_diff": float(np.median(diffs)),
        "n_treatment_better": int(np.count_nonzero(diffs > 0)),
        "n_control_better": int(np.count_nonzero(diffs < 0)),
        "n_tied": int(np.count_nonzero(diffs == 0)),
        "inference": inference,
        "threshold_grid": grid,
        "fit_performed": False, "tuning_performed": False,
        "gate_decision": None,
    }, bool(len(nonzero) and ranks_positive > rank_total / 2.0))


def _threshold_counts(values: np.ndarray) -> dict[str, int]:
    return {
        str(threshold): int(np.count_nonzero(values >= threshold))
        for threshold in THRESHOLDS
    }


def _same(left: object, right: object) -> bool:
    return _canonical(left) == _canonical(right)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result, completion = _fully_harvested_result(args.result)
    except (OSError, UnicodeError, VerificationError) as exc:
        print(f"INVALID HARVEST: {exc}")
        return 1
    if result.get("version") != RESULT_VERSION or result.get("run_id") != RUN_ID or \
            result.get("uses_realized_outcomes") is not True or result.get(
                "actual_score_query_executed"
            ) is not True or result.get(
                "production_change_licensed"
            ) is not False or result.get(
                "prospective_shadow_licensed"
            ) is not False:
        print("INVALID HARVEST: realized A7-v2 result identity differs")
        return 1
    outcome = result.get("outcome")
    cuts = outcome.get("cuts") if isinstance(outcome, dict) else None
    if not isinstance(outcome, dict) or outcome.get(
        "protocol_id"
    ) != RUN_ID or outcome.get("uses_realized_outcomes") is not True or outcome.get(
        "production_change_licensed"
    ) is not False or outcome.get(
        "prospective_shadow_licensed"
    ) is not False or not isinstance(cuts, dict) or set(cuts) != {
        str(value) for value in PREFIX_COUNTS
    }:
        print("INVALID HARVEST: result['outcome']['cuts'] population differs")
        return 1
    findings: list[str] = []
    recomputed: dict[int, tuple[dict[str, Any], bool, np.ndarray, np.ndarray]] = {}
    for count in (80, 14, 4):
        try:
            control, treatment, keys = _pairs(result, count)
        except (KeyError, TypeError, VerificationError) as exc:
            findings.append(f"N={count}: invalid per-slate receipt: {exc}")
            continue
        paired, direction = paired_report(control, treatment)
        inference = paired["inference"]
        recomputed[count] = (paired, direction, control, treatment)
        print(f"\n== N={count} ({len(keys)} slates) ==")
        print(f"  recomputed mean delta      {paired['mean_diff']:+.6f}")
        print(f"  recomputed W+              {inference['signed_rank_statistic']:.1f}")
        print(f"  recomputed p(mean)         {inference['p_mean_two_sided']:.6f}")
        print(
            "  recomputed p(signed rank)  "
            f"{inference['p_signed_rank_two_sided']:.6f}"
        )
        print("  recomputed grid (ctrl->trt):", {
            str(row["threshold"]): f"{row['control']}->{row['treatment']}"
            for row in paired["threshold_grid"]
        })

        retained = cuts.get(str(count))
        if not isinstance(retained, dict):
            findings.append(f"N={count}: no recorded cut to compare against")
            continue
        checks = {
            "gating": count == ENTRY_COUNT,
            "control_mean": float(control.mean()),
            "treatment_mean": float(treatment.mean()),
            "control_threshold_counts": _threshold_counts(control),
            "treatment_threshold_counts": _threshold_counts(treatment),
            "paired": paired,
            "signed_rank_direction_positive": direction,
        }
        for field, expected in checks.items():
            if field not in retained or not _same(retained[field], expected):
                findings.append(
                    f"N={count}: recorded {field} != independent recomputation"
                )

    if ENTRY_COUNT in recomputed:
        paired, direction, control, treatment = recomputed[ENTRY_COUNT]
        inference = paired["inference"]
        control_counts = _threshold_counts(control)
        treatment_counts = _threshold_counts(treatment)
        conditions = {
            "mean_delta_positive": paired["mean_diff"] > 0,
            "paired_mean_p_le_0_05": inference["p_mean_two_sided"] <= 0.05,
            "signed_rank_direction_positive": direction,
            "paired_signed_rank_p_le_0_05": (
                inference["p_signed_rank_two_sided"] <= 0.05
            ),
            "194_noninferior_by_one_slate": (
                treatment_counts["194"] - control_counts["194"]
                >= NONINFERIORITY_FLOOR
            ),
            "200_noninferior_by_one_slate": (
                treatment_counts["200"] - control_counts["200"]
                >= NONINFERIORITY_FLOOR
            ),
        }
        if all(conditions.values()):
            disposition = "historical-positive-phase-s"
        elif paired["mean_diff"] < 0 or not (
            conditions["194_noninferior_by_one_slate"]
            and conditions["200_noninferior_by_one_slate"]
        ):
            disposition = "rejected-phase-s-dose"
        else:
            disposition = "historical-null-or-inconclusive-phase-s"
        licensed = disposition == "historical-positive-phase-s"
        for label, actual, expected in (
            ("conditions", outcome.get("conditions"), conditions),
            ("disposition", outcome.get("disposition"), disposition),
            (
                "transfer license",
                outcome.get("production_law_scorefree_transfer_licensed"),
                licensed,
            ),
            (
                "top-level transfer license",
                result.get("production_law_scorefree_transfer_licensed"),
                licensed,
            ),
            ("completion disposition", completion.get("disposition"), disposition),
        ):
            if not _same(actual, expected):
                findings.append(f"N=80: recorded {label} != independent result")

    print("\n" + "=" * 60)
    if findings:
        print("DISAGREEMENTS FOUND — investigate before treating the")
        print("disposition as settled:")
        for line in findings:
            print(f"  - {line}")
        return 1
    print("All recomputed statistics and disposition agree with the recorded values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
