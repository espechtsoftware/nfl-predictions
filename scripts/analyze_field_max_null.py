#!/usr/bin/env python3
"""Run the field-max null calibration (protocol 20260819-field-max-null-v1).

Computes, entirely under the archived production law, how extreme a
contest winner's own-roster percentile should look when the winner is the
maximum over a finite field — the null the N1 headline was missing. No
realized outcome is read; the observed N1 exceedance counts enter only as
published constants from the frozen report.

Runs exactly once per frozen protocol version after the operator-visible
freeze of reports/2026-08-19-field-max-null-protocol.md. The --smoke
mode is the outcome-blind reality check required before the freeze: it
exercises loading, stacking, the null computation, and subsample
determinism on one slate and prints contract facts only (no comparison
against the observed counts).

Inputs:
  --report    frozen N1 report JSON (slate list + observed exceedance)
  --manifest  JSON list of {"season", "week", "artifacts": [npz paths]}
  --output    report JSON path (created exclusively; never overwrites)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.analysis.field_max_null import (  # noqa: E402
    EXCEEDANCE_LEVELS,
    PROTOCOL_ID,
    FieldMaxNullError,
    combine_block_nulls,
    field_max_null_report,
    null_field_max_percentiles,
    subsample_field_null,
)

SUBSAMPLE_SIZES = (32, 64, 128)
SUBSAMPLE_REPS = 5
SUBSAMPLE_SEED = 20260819


def _load_block(path: Path) -> np.ndarray:
    with np.load(path) as artifact:
        keys = set(artifact.files)
        if not {"cand_ix", "totals"} <= keys:
            raise FieldMaxNullError(
                f"{path} lacks candidate totals (keys: {sorted(keys)})")
        cand_ix = np.asarray(artifact["cand_ix"], dtype=np.int64)
        totals = np.asarray(artifact["totals"], dtype=np.float64)
    if len(np.unique(cand_ix)) != len(cand_ix):
        raise FieldMaxNullError(f"{path} candidate indices repeat")
    if totals.ndim != 2 or totals.shape[0] != len(cand_ix):
        raise FieldMaxNullError(f"{path} totals do not align with cand_ix")
    return totals


def _slate_null(paths: list[Path]) -> dict:
    blocks = [_load_block(p) for p in paths]
    pooled = combine_block_nulls(
        [null_field_max_percentiles(totals) for totals in blocks])
    percentiles = pooled["percentiles"]
    p_beyond = {
        level: float((percentiles >= level).mean())
        for level in EXCEEDANCE_LEVELS
    }
    p_zero = float((pooled["pr_ge"] == 0.0).mean())
    subsample = {}
    for n_sub in SUBSAMPLE_SIZES:
        eligible = [t for t in blocks if n_sub <= t.shape[0]]
        if not eligible:
            continue
        subs = [
            subsample_field_null(t, n_sub, SUBSAMPLE_SEED, SUBSAMPLE_REPS)
            for t in eligible
        ]
        subsample[n_sub] = float(
            (np.concatenate(subs) >= 0.999).mean())
    return {
        "n_candidates": float(np.mean(pooled["block_candidates"])),
        "block_candidates": pooled["block_candidates"],
        "n_worlds": int(pooled["n_worlds"]),
        "p_beyond": p_beyond,
        "p_zero": p_zero,
        "subsample": subsample,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--smoke", metavar="SEASON:WEEK",
        help="outcome-blind machinery smoke on one slate (contract "
             "facts only; no observed comparison)")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    n1_report = json.loads(args.report.read_text())
    manifest = json.loads(args.manifest.read_text())
    by_slate = {
        (int(m["season"]), int(m["week"])): [Path(p) for p in m["artifacts"]]
        for m in manifest
    }

    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        paths = by_slate[(season, week)]
        blocks = [_load_block(p) for p in paths]
        first = combine_block_nulls(
            [null_field_max_percentiles(t) for t in blocks])
        second = combine_block_nulls(
            [null_field_max_percentiles(t) for t in blocks])
        if not np.array_equal(first["percentiles"], second["percentiles"]):
            raise FieldMaxNullError("null computation is not deterministic")
        sub_a = subsample_field_null(
            blocks[0], SUBSAMPLE_SIZES[0], SUBSAMPLE_SEED, SUBSAMPLE_REPS)
        sub_b = subsample_field_null(
            blocks[0], SUBSAMPLE_SIZES[0], SUBSAMPLE_SEED, SUBSAMPLE_REPS)
        if not np.array_equal(sub_a, sub_b):
            raise FieldMaxNullError("subsampling is not seed-deterministic")
        finite = bool(
            np.isfinite(first["percentiles"]).all()
            and np.isfinite(sub_a).all())
        in_range = bool(
            (first["percentiles"] >= 0.0).all()
            and (first["percentiles"] <= 1.0).all())
        print(f"SMOKE_OK slate={season}:{week} blocks={len(paths)} "
              f"block_candidates={first['block_candidates']} "
              f"contests={first['n_worlds']}")
        print(f"SMOKE_OK percentiles_finite={finite} "
              f"percentiles_in_unit_range={in_range} "
              f"deterministic=True "
              f"subsample_len={len(sub_a)}")
        return 0

    slates = sorted(
        ((int(w["season"]), int(w["week"]))
         for w in n1_report["winners"]))
    per_slate = []
    for season, week in slates:
        paths = by_slate.get((season, week))
        if not paths:
            raise FieldMaxNullError(
                f"{season} week {week}: winner slate missing from manifest")
        entry = _slate_null(paths)
        entry["season"] = season
        entry["week"] = week
        per_slate.append(entry)
        print(f"NULLED {season}:{week} "
              f"candidates={entry['n_candidates']}")

    observed = {
        level: int(
            n1_report["exceedance"]
            [f"at_or_beyond_p{str(level).replace('0.', '')}"]["observed"])
        for level in EXCEEDANCE_LEVELS
    }
    report = field_max_null_report(
        per_slate, observed, int(n1_report["n_winners"]), SUBSAMPLE_SIZES)
    report["subsample_reps"] = SUBSAMPLE_REPS
    report["subsample_seed"] = SUBSAMPLE_SEED
    report["n1_report_path"] = str(args.report)
    report["manifest_path"] = str(args.manifest)
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "FIELD_MAX_NULL_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"slates={report['n_slates']}",
        f"verdict={report['verdict']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
