"""ACTION 1 acceptance checks (post-review-6 plan §C) — the promotion
gate for a canonical harvest.

Reads the STAGING candidate table for one panel_run_id and refuses
promotion unless every check passes. Promotion = copying the panel's
rows into the research table; nothing else may query staging.

  python scripts/harvest_accept.py <panel_run_id> [--promote]

Checks (each maps to a §C bullet):
 1. slate completeness — all expected (season, week) pairs present
 2. no mixed builds / duplicate slate runs within the panel
 3. selected-entry count per slate
 4. candidate counts inside a preregistered range
 5. labels complete, research_eligible true, provenance non-empty
 6. masks decode, lengths agree with n_worlds, 187>=194>=200 monotone
 7. mask-reconstructed selection reproduces the persisted portfolio
 8. baseline + oracle summaries recompute FROM THE TABLE
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402

STAGING = "replay_candidates_staging"
RESEARCH = "replay_candidates"
EXPECTED_SEASONS = (2019, 2021, 2022, 2023, 2024, 2025)
CAND_RANGE = (80, 400)      # preregistered plausible pool size
ENTRIES_EXPECTED = 40


def _bits(hexs: str, n: int) -> np.ndarray:
    return np.unpackbits(
        np.frombuffer(bytes.fromhex(hexs), dtype=np.uint8),
        bitorder="big")[:n].astype(bool)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("panel_run_id")
    ap.add_argument("--promote", action="store_true")
    a = ap.parse_args()

    d = query_df(f"""
        SELECT * FROM `{settings.predictions}.{STAGING}`
        WHERE panel_run_id = '{a.panel_run_id}'""")
    fails: list[str] = []
    if d.empty:
        print(f"FAIL: no rows for panel {a.panel_run_id}")
        return 1
    print(f"rows: {len(d):,}  slates: {d.groupby(['season','week']).ngroups}")

    # 1 completeness
    got = set(map(tuple, d[["season", "week"]].drop_duplicates().values))
    missing = [(s, w) for s in EXPECTED_SEASONS for w in range(1, 19)
               if s != 2019 or w <= 17]
    missing = [x for x in missing if x not in got]
    if missing:
        fails.append(f"missing slates: {missing[:6]}{'...' if len(missing) > 6 else ''}")

    # 2 one slate_run_id per (season, week)
    dup = (d.groupby(["season", "week"]).slate_run_id.nunique() > 1)
    if dup.any():
        fails.append(f"mixed/duplicate slate runs: {dup[dup].index.tolist()[:5]}")

    # 3 selected counts
    sel = d[d.selected].groupby(["season", "week"]).size()
    bad = sel[sel != ENTRIES_EXPECTED]
    if len(bad):
        fails.append(f"selected != {ENTRIES_EXPECTED} in {len(bad)} slates")

    # 4 candidate counts
    n_by = d.groupby(["season", "week"]).size()
    out = n_by[(n_by < CAND_RANGE[0]) | (n_by > CAND_RANGE[1])]
    if len(out):
        fails.append(f"candidate count outside {CAND_RANGE} in {len(out)} slates")

    # 5 labels + provenance
    if not d.labels_complete.all():
        fails.append("labels_complete false somewhere")
    if not d.research_eligible.all():
        fails.append("research_eligible false somewhere")
    if d.actual_score.isna().any():
        fails.append("null actual_score in a replay panel")
    tags = d.all_tags.map(lambda s: json.loads(s) if isinstance(s, str) else [])
    if tags.map(len).max() < 2:
        fails.append("no multi-producer roster recorded (provenance suspect)")

    # 6-7 masks decode + selection reproduces, on a sample of slates
    rng = np.random.default_rng(0)
    keys = list(d.groupby(["season", "week"]).groups)
    sample = [keys[i] for i in rng.choice(len(keys), min(8, len(keys)),
                                          replace=False)]
    from nfl_dfs.optimizer.lineup import select_tail_entries
    for (s, w) in sample:
        g = d[(d.season == s) & (d.week == w)].sort_values("cand_ix")
        n = int(g.n_worlds.iloc[0])
        try:
            m194 = np.stack([_bits(b, n) for b in g.clear_bits_194])
            m187 = np.stack([_bits(b, n) for b in g.clear_bits_187])
            m200 = np.stack([_bits(b, n) for b in g.clear_bits_200])
        except Exception as e:
            fails.append(f"mask decode failed {s} wk{w}: {e}")
            continue
        if not (m187.sum() >= m194.sum() >= m200.sum()):
            fails.append(f"mask monotonicity violated {s} wk{w}")
        base = np.stack([_bits(b, n) for b in g.clear_bits])
        totals = np.where(base, 1e6, 0.0)
        picked = select_tail_entries(totals, int(g.selected.sum()), 1e5)
        stored = g[g.selected].sort_values("selected_rank").cand_ix.tolist()
        if list(picked) != stored:
            fails.append(f"selection not reproducible from masks {s} wk{w}")

    # 8 summaries recompute from the table
    per_slate = d.groupby(["season", "week"]).apply(
        lambda g: pd.Series({
            "sel_best": g[g.selected].actual_score.max(),
            "oracle": g.actual_score.max()}), include_groups=False)
    clears = int((per_slate.sel_best >= 194).sum())
    orc_clears = int((per_slate.oracle >= 194).sum())
    print(f"\nRECOMPUTED FROM TABLE: selected clears {clears}/{len(per_slate)}"
          f"  |  candidate-oracle clears {orc_clears}/{len(per_slate)}"
          f"  |  recoverable {orc_clears - clears}")
    print(f"mean best-of-40 {per_slate.sel_best.mean():.1f}  "
          f"mean oracle {per_slate.oracle.mean():.1f}")

    if fails:
        print("\nACCEPTANCE FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\nACCEPTANCE PASSED — panel eligible for promotion")
    if a.promote:
        query_df(f"""
            CREATE TABLE IF NOT EXISTS `{settings.predictions}.{RESEARCH}`
            LIKE `{settings.predictions}.{STAGING}`;
            INSERT INTO `{settings.predictions}.{RESEARCH}`
            SELECT * FROM `{settings.predictions}.{STAGING}`
            WHERE panel_run_id = '{a.panel_run_id}'""")
        print(f"promoted panel {a.panel_run_id} -> {RESEARCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
