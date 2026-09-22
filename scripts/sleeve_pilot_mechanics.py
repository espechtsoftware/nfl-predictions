#!/usr/bin/env python3
"""Outcome-disabled mechanics pilot: production stack vs exploration sleeve.

Assigned to production by the coordinating laptop in nfl2
`handoffs/2026-09-21-production-assignment-sleeve-pilot.md`.

What this is: 40 BOOM solves under the ordinary production stack against 40
extra-profile exploration solves, on ONE archived pre-lock frame, ONE draw bank,
the SAME draw columns in the SAME visit order, zero LEV, identical salary and
punt settings. It isolates the construction change.

What this is NOT: it computes no outcomes, selects no book, and concludes
nothing about efficacy. Realized scores are never read.

Design notes that matter for correctness:

* Both arms receive the same `world_order_override`, computed once on the shared
  eligible frame. Ordinary boom visits `order[0:40]`; the exploration profile is
  configured `start=0, count=40` so it visits *the same forty worlds*. Without
  this the arms would be compared on different draws.
* The arms are generated STANDALONE. `existing=` is deliberately not passed
  between them: doing so would delete from the treatment every candidate the
  control had already found, which is exactly the shared core, and would make
  the sleeve look far more novel than it is. The union is computed afterwards.
* BOOM optimises on `proj_sim`, taken from the draw column. Rewriting `proj`
  would not move this arm at all -- that is the laptop's point about
  `generate_candidates` using draws for BOOM and `proj_tourney` for LEV.

Run:
    PYTHONPATH=<nfl2 worktree>/src:<nfl2 worktree> \
      <nfl2 venv>/python scripts/sleeve_pilot_mechanics.py --frame <frame.parquet> \
      --receipt <source_receipt.json> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def eligible_universe(frame):
    """One documented universe, applied identically to both arms BEFORE generation.

    Uses only evidence present in the frame at its own cutoff:

    inactive  -- `roster_status` must be ACT, or null which in this frame means a
                 team defence (all 26 nulls are DST). This archived frame carries
                 NO 'O'/'IR' rows at all: DraftKings' pre-lock pool had already
                 excluded them, so the inactive filter is a verified no-op here
                 rather than an unimplemented one. It is applied anyway and its
                 removal count is recorded, so a frame that DOES carry inactives
                 is handled without a code change.
    starter   -- quarterbacks must have `depth_rank == 1`. Non-starting QBs in
                 this frame project at mean 1.58 and are the population behind
                 the known backup-QB valuation defect; a relaxed-construction arm
                 is exactly what would reach for them. QBs with a missing
                 depth_rank are excluded: absent evidence is not evidence of
                 being a starter.
    """
    n0 = len(frame)
    is_dst = frame["pos"].astype(str).str.upper().eq("DST")
    active = frame["roster_status"].astype("string").fillna("") .eq("ACT") | is_dst
    after_active = frame[active]
    n_inactive = n0 - len(after_active)

    is_qb = after_active["pos"].astype(str).str.upper().eq("QB")
    depth = after_active.get("depth_rank")
    qb_ok = (~is_qb) | (depth.notna() & depth.eq(1))
    out = after_active[qb_ok].reset_index(drop=True)
    return out, {
        "rows_in": int(n0),
        "removed_inactive": int(n_inactive),
        "removed_non_starter_qb": int(len(after_active) - len(out)),
        "rows_out": int(len(out)),
        "rule": "roster_status==ACT or DST; QB requires depth_rank==1",
    }


def ledger_counts(ledger) -> dict:
    c = Counter(r.get("status", "?") for r in ledger)
    return {
        "attempted": len(ledger),
        "new": int(c.get("new", 0)),
        "duplicate": int(c.get("dup", 0)),
        "infeasible": int(c.get("infeasible", 0)),
        "error": int(c.get("error", 0)),
        "exhausted": int(c.get("exhausted", 0)),
        "other": int(sum(v for k, v in c.items()
                         if k not in {"new", "dup", "infeasible", "error", "exhausted"})),
    }


def roster_key(lu) -> tuple:
    return tuple(sorted(str(p.get("id")) for p in lu.players))


def pair_support(lineups) -> dict:
    """Achievable-pair denominator and partner coverage, matching the contract in
    production's scripts/pool_pair_support.py -- a raw pair count flags nothing."""
    ids = sorted({str(p.get("id")) for lu in lineups for p in lu.players})
    pairs = set()
    for lu in lineups:
        for a, b in combinations(sorted(str(p.get("id")) for p in lu.players), 2):
            pairs.add((a, b))
    n = len(ids)
    possible = n * (n - 1) // 2
    achievable = min(possible, len(lineups) * 36)  # 9 players -> C(9,2)=36 pairs per lineup
    partners = {i: set() for i in ids}
    for a, b in pairs:
        partners[a].add(b)
        partners[b].add(a)
    peers = max(1, n - 1)
    cov = sorted((len(v) / peers) for v in partners.values())
    return {
        "players": n,
        "distinct_pairs": len(pairs),
        "possible_pairs": possible,
        "achievable_pairs": achievable,
        "share_of_achievable": (len(pairs) / achievable) if achievable else None,
        "partner_coverage_min": cov[0] if cov else None,
        "partner_coverage_median": cov[len(cov) // 2] if cov else None,
        "partner_coverage_max": cov[-1] if cov else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--solves", type=int, default=40)
    ap.add_argument("--sims", type=int, default=10_000)
    a = ap.parse_args()

    import numpy as np
    import pandas as pd
    from nfl2.pipeline import (PRODUCTION_ENV, PRODUCTION_STACK, generate_candidates,
                               simulate_slate, slate_seed, world_order)
    from nfl2.exploration_sleeve import (EXPLORATION_ENV, SleeveConfig, profile,
                                         validate_lineup)

    frame_p, receipt_p = Path(a.frame), Path(a.receipt)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    src = json.loads(receipt_p.read_text())
    season, week = int(src["season"]), int(src["week"])
    seed_bank = int(src["banks"]["generation_seed"])

    full = pd.read_parquet(frame_p)
    frame, elig = eligible_universe(full)
    qb_safe = {str(x) for x in frame.loc[frame.pos.astype(str).str.upper().eq("QB"), "id"]}

    sseed = slate_seed(seed_bank, season, week)
    t0 = time.time()
    draws = simulate_slate(frame, n_sims=a.sims, seed=sseed, law_env=PRODUCTION_ENV)
    t_sim = time.time() - t0
    order = world_order(frame, draws)          # computed ONCE, shared by both arms

    arms, results = {}, {}
    for name, kwargs in (
        ("control_production_stack", dict(
            n_lev=0, n_boom=a.solves, stack=PRODUCTION_STACK, env=dict(PRODUCTION_ENV))),
        ("treatment_exploration_sleeve", dict(
            n_lev=0, n_boom=0,
            extra_profiles=profile(SleeveConfig(count=a.solves, start=0)),
            env={**PRODUCTION_ENV, **EXPLORATION_ENV})),
    ):
        led: list = []
        t = time.time()
        cands = generate_candidates(frame, draws, ledger=led,
                                    world_order_override=order, **kwargs)
        elapsed = time.time() - t
        arms[name] = cands
        legal, qb_fail, other_fail = 0, 0, []
        for lu in cands:
            try:
                validate_lineup(lu, inactive_ids=(), qb_safe_ids=qb_safe)
                legal += 1
            except ValueError as exc:
                (qb_fail := qb_fail + 1) if "quarterback" in str(exc) else other_fail.append(str(exc))
        results[name] = {
            **ledger_counts(led),
            "returned_lineups": len(cands),
            "elapsed_seconds": round(elapsed, 2),
            "worlds_visited": sorted({r["world"] for r in led if r.get("world") is not None}),
            "legality_passed": legal,
            "legality_failed_qb_safety": qb_fail,
            "legality_failed_other": other_fail[:5],
            "roster_hashes": sorted(hashlib.sha256("|".join(roster_key(lu)).encode()).hexdigest()[:16]
                                    for lu in cands),
            "pair_support": pair_support(cands),
        }

    c, t_ = arms["control_production_stack"], arms["treatment_exploration_sleeve"]
    kc, kt = {roster_key(l) for l in c}, {roster_key(l) for l in t_}
    receipt = {
        "schema": "sleeve-mechanics-pilot/v1",
        "generated_utc": datetime.now(UTC).isoformat(),
        "outcomes_read": False,
        "assignment": "nfl2 handoffs/2026-09-21-production-assignment-sleeve-pilot.md",
        "inputs": {
            "frame_path": str(frame_p), "frame_sha256": sha256_file(frame_p),
            "receipt_path": str(receipt_p), "receipt_sha256": sha256_file(receipt_p),
            "season": season, "week": week,
            "draft_group": src.get("draft_group"),
            "serving_commit": src["identity"]["sha"], "serving_dirty": src["identity"]["dirty"],
            "cutoff_salary_pull": str(src.get("salary_pull")),
            "cutoff_built_utc": str(src.get("built_utc")),
            "lock_utc": str(src.get("lock_utc")),
            "generation_seed_bank": seed_bank, "derived_slate_seed": sseed,
            "n_sims": a.sims, "simulate_seconds": round(t_sim, 2),
            "player_order_sha256": hashlib.sha256(
                "|".join(str(x) for x in frame.id).encode()).hexdigest(),
            "draws_shape": list(draws.shape),
            "draws_sha256": hashlib.sha256(np.ascontiguousarray(draws).tobytes()).hexdigest(),
            "world_order_head": [int(x) for x in order[:a.solves]],
        },
        "eligible_universe": elig,
        "qb_safe_set_size": len(qb_safe),
        "arms": results,
        "union": {
            "control_unique": len(kc), "treatment_unique": len(kt),
            "shared": len(kc & kt), "union": len(kc | kt),
            "treatment_only": len(kt - kc), "control_only": len(kc - kt),
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__, "pandas": pd.__version__,
            "nfl2_commit": src["identity"]["sha"],
        },
    }
    (out / "pilot-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in ("eligible_universe", "union")}, indent=2))
    for k, v in results.items():
        print(f"\n{k}: attempted={v['attempted']} new={v['new']} dup={v['duplicate']} "
              f"infeasible={v['infeasible']} error={v['error']} "
              f"legal={v['legality_passed']}/{v['returned_lineups']} "
              f"elapsed={v['elapsed_seconds']}s")
    print(f"\nreceipt: {out / 'pilot-receipt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
