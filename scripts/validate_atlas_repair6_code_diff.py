#!/usr/bin/env python3
"""Validate the exact score-free repair5 -> repair6 numerical code diff."""

from __future__ import annotations

import argparse
import difflib
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path("src/nfl_dfs/analysis/atlas_world_ranking.py")
PROTOCOL = Path(
    "reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md"
)
REPAIR5_CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
REPAIR5_SOURCE_SHA256 = (
    "f3280a30ca499c48ea5d8b69b93b9bb894d454e1e4a9da025ef44f917c528287"
)
REPAIR6_SOURCE_SHA256 = (
    "7ccec773b4b3da31860081b0525f496d394ff0bf8f0a7229f32a691be5849f33"
)
REPAIR6_DIFF_SHA256 = (
    "3c4124b2a3fc6a86d00a278324533ddedf07cdbdd3227bfdacd8aae72838dda9"
)
PROTOCOL_SHA256 = (
    "b4a98543b1dcd776d50ae00e380fbc695346debb0de6452131fdfd0ba7c2820a"
)
TOLERANCES = (1e-6, 1e-5, 1e-4)


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _repair5_source(after: bytes) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{REPAIR5_CODE_SHA}:{RELATIVE}"],
            check=True, capture_output=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Cloud Build validates a clean ``git archive`` with no repository
        # history. Reconstruct the exact repair5 source by reversing only the
        # frozen repair6 extension, then let the pinned before/after/diff
        # hashes below prove that the reconstruction is byte-exact.
        source = after.decode("utf-8")
        replacements = (
            (
                "EXACT_IDENTITY_TOLERANCE = 1e-6\n"
                "EXACT_IDENTITY_TOLERANCES = (1e-6, 1e-5, 1e-4)\n",
                "EXACT_IDENTITY_TOLERANCE = 1e-6\n",
            ),
            (
                "        lineup = None\n"
                "        identity_tolerance = None\n"
                "        for tolerance in EXACT_IDENTITY_TOLERANCES:\n"
                "            lineup = optimize(\n"
                "                tied_players,\n"
                "                stack=stack,\n"
                "                objective_col=\"atlas_identity_score\",\n"
                "                objective_floor_col=\"atlas_world_score\",\n"
                "                objective_floor=optimum - tolerance,\n"
                "                env=env,\n"
                "            )\n"
                "            if lineup is not None:\n"
                "                identity_tolerance = tolerance\n"
                "                break\n"
                "        if lineup is None:\n"
                "            raise RuntimeError(\n"
                "                f\"ATLAS world {world} identity tiebreak is infeasible\"\n"
                "            )\n"
                "        if identity_tolerance is None:  # pragma: no cover - loop invariant\n"
                "            raise AssertionError(\"ATLAS identity tolerance was not recorded\")\n",
                "        lineup = optimize(\n"
                "            tied_players,\n"
                "            stack=stack,\n"
                "            objective_col=\"atlas_identity_score\",\n"
                "            objective_floor_col=\"atlas_world_score\",\n"
                "            objective_floor=optimum - EXACT_IDENTITY_TOLERANCE,\n"
                "            env=env,\n"
                "        )\n"
                "        if lineup is None:\n"
                "            raise RuntimeError(\n"
                "                f\"ATLAS world {world} identity tiebreak is infeasible\"\n"
                "            )\n",
            ),
            (
                "        if roster_score < optimum - identity_tolerance - 1e-8:\n",
                "        if roster_score < optimum - EXACT_IDENTITY_TOLERANCE - 1e-8:\n",
            ),
            (
                '            "identity_tolerance": identity_tolerance,\n',
                '            "identity_tolerance": EXACT_IDENTITY_TOLERANCE,\n',
            ),
            (
                '    "EXACT_IDENTITY_TOLERANCES",\n',
                "",
            ),
        )
        for current, repair5 in replacements:
            if source.count(current) != 1:
                raise RuntimeError(
                    "ATLAS repair6 clean-archive reconstruction differs"
                )
            source = source.replace(current, repair5)
        return source.encode("utf-8")


def _canonical_diff(before: bytes, after: bytes) -> bytes:
    text = "".join(difflib.unified_diff(
        before.decode("utf-8").splitlines(keepends=True),
        after.decode("utf-8").splitlines(keepends=True),
        fromfile=f"repair5/{RELATIVE}", tofile=f"repair6/{RELATIVE}",
    ))
    return text.encode("utf-8")


def validate() -> dict[str, Any]:
    after = (ROOT / RELATIVE).read_bytes()
    before = _repair5_source(after)
    protocol = (ROOT / PROTOCOL).read_bytes()
    diff = _canonical_diff(before, after)
    observed = {
        "repair5_source_sha256": _digest(before),
        "repair6_source_sha256": _digest(after),
        "repair6_diff_sha256": _digest(diff),
        "protocol_sha256": _digest(protocol),
    }
    expected = {
        "repair5_source_sha256": REPAIR5_SOURCE_SHA256,
        "repair6_source_sha256": REPAIR6_SOURCE_SHA256,
        "repair6_diff_sha256": REPAIR6_DIFF_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
    }
    if observed != expected:
        raise RuntimeError("ATLAS repair6 frozen code diff differs")
    source = after.decode("utf-8")
    if "EXACT_IDENTITY_TOLERANCES = (1e-6, 1e-5, 1e-4)" not in source or \
            "for tolerance in EXACT_IDENTITY_TOLERANCES:" not in source or \
            "objective_floor=optimum - tolerance" not in source:
        raise RuntimeError("ATLAS repair6 tolerance law differs")
    return {
        "version": "atlas-repair6-code-diff-proof-v1",
        "protocol_id": "20260817-atlas-matched-diversity-mvp-v1-repair6",
        "repair5_code_sha": REPAIR5_CODE_SHA,
        "tolerances": list(TOLERANCES),
        **observed,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "disposition": "valid-exact-identity-tiebreak-extension",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate()
    raw = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(raw)
    print("ATLAS_REPAIR6_CODE_DIFF " + raw.strip())


if __name__ == "__main__":
    main()
