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
from nfl_dfs.research.candidate_features import (  # noqa: E402
    FEATURE_DEF_VERSION)

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
    if d.research_eligible.any():
        fails.append("staging rows already research_eligible (must be "
                     "FALSE until promotion)")
    if d.actual_score.isna().any():
        fails.append("null actual_score in a replay panel")
    tags = d.all_tags.map(lambda s: json.loads(s) if isinstance(s, str) else [])
    if tags.map(len).max() < 2:
        fails.append("no multi-producer roster recorded (provenance suspect)")

    # 6-7 masks + selection reproduction on EVERY slate (Sol audit 3:
    # sampling is monitoring, not acceptance), using the SAME selector
    # helper production used — so the mean-total tiebreak is exercised.
    from nfl_dfs.optimizer.lineup import select_from_support
    for (s_, w_), g in d.groupby(["season", "week"]):
        g = g.sort_values("cand_ix")
        n = int(g.n_worlds.iloc[0])
        if g.cand_ix.duplicated().any():
            fails.append(f"duplicate cand_ix {s_} wk{w_}")
            continue
        if not (g.n_worlds == n).all():
            fails.append(f"n_worlds disagrees within slate {s_} wk{w_}")
        try:
            base = np.stack([_bits(b, n) for b in g.clear_bits])
            m187 = np.stack([_bits(b, n) for b in g.clear_bits_187])
            m194 = np.stack([_bits(b, n) for b in g.clear_bits_194])
            m200 = np.stack([_bits(b, n) for b in g.clear_bits_200])
        except Exception as e:
            fails.append(f"mask decode failed {s_} wk{w_}: {e}")
            continue
        if base.shape[1] != n:
            fails.append(f"mask length != n_worlds {s_} wk{w_}")
        # element-wise nesting, not just aggregate counts
        if not (np.all(m194 <= m187) and np.all(m200 <= m194)):
            fails.append(f"mask nesting violated (element-wise) {s_} wk{w_}")
        sel_rows = g[g.selected].sort_values("selected_rank")
        if len(sel_rows) == 0:
            fails.append(f"zero selected entries {s_} wk{w_}")
            continue
        ranks = sel_rows.selected_rank.tolist()
        if ranks != list(range(len(ranks))):
            fails.append(f"selected_rank not contiguous/unique {s_} wk{w_}")
        picked = select_from_support(base, g.p_line.to_numpy(),
                                     g.sim_mean.to_numpy(), len(sel_rows))
        if list(picked) != sel_rows.cand_ix.tolist():
            fails.append(f"selection not reproducible {s_} wk{w_}")

    # 6b artifacts must EXIST and match (Sol audit 3: an optional,
    # unverified artifact means a panel can pass without the data the
    # reranker needs).
    try:
        from google.cloud import storage
        client = storage.Client()
        for (s_, w_), g in d.groupby(["season", "week"]):
            uri = str(g.score_artifact_uri.iloc[0] or "")
            sha = str(g.score_artifact_sha256.iloc[0] or "")
            if not uri or not sha:
                fails.append(f"missing score artifact {s_} wk{w_}")
                continue
            bkt, _, path = uri.replace("gs://", "").partition("/")
            blob = client.bucket(bkt).blob(path)
            if not blob.exists():
                fails.append(f"artifact object absent {uri}")
                continue
            payload = blob.download_as_bytes()
            import hashlib
            if hashlib.sha256(payload).hexdigest() != sha:
                fails.append(f"artifact sha mismatch {uri}")
                continue
            import io
            z = np.load(io.BytesIO(payload))
            totals = z["totals"]
            if totals.shape[0] != len(g):
                fails.append(f"artifact rows {totals.shape[0]} != {len(g)} "
                             f"{s_} wk{w_}")
            elif totals.shape[1] != int(g.n_worlds.iloc[0]):
                fails.append(f"artifact worlds != n_worlds {s_} wk{w_}")
            else:
                # scores must reproduce the persisted masks exactly
                gg = g.sort_values("cand_ix")
                recon = totals[gg.cand_ix.to_numpy()] >= 194.0
                stored = np.stack([_bits(b, int(gg.n_worlds.iloc[0]))
                                   for b in gg.clear_bits_194])
                if not np.array_equal(recon, stored):
                    fails.append(f"artifact scores disagree with mask "
                                 f"{s_} wk{w_}")
    except Exception as e:
        fails.append(f"artifact verification failed: {e}")

    # 8 acceptance REPORT (scoring plan §6) + the §6.1 decision gate,
    # computed mechanically so the reranker go/no-go is not a judgment
    # call made after seeing the numbers.
    per_slate = d.groupby(["season", "week"]).apply(
        lambda g: pd.Series({
            "sel_best": g[g.selected].actual_score.max(),
            "oracle": g.actual_score.max(),
            "oracle_simrank": int(
                g.loc[g.actual_score.idxmax(), "sim_rank_p_line"]),
            "oracle_selected": bool(
                g.loc[g.actual_score.idxmax(), "selected"]),
            "oracle_tag": g.loc[g.actual_score.idxmax(), "tag"],
            "n_cand": len(g)}), include_groups=False).reset_index()
    per_slate["regret"] = per_slate.oracle - per_slate.sel_best

    print("\n=== ACCEPTANCE REPORT (plan §6) ===")
    print(f"definition version: {FEATURE_DEF_VERSION}")
    for thr in (187, 194, 200):
        sc = int((per_slate.sel_best >= thr).sum())
        oc = int((per_slate.oracle >= thr).sum())
        print(f"  >={thr}: selected {sc:3d}  pool-oracle {oc:3d}  "
              f"recoverable {oc - sc:3d}")
    print("\nby season (selected / oracle clears at 194):")
    bys = per_slate.groupby("season").apply(
        lambda g: pd.Series({
            "slates": len(g),
            "sel194": int((g.sel_best >= 194).sum()),
            "orc194": int((g.oracle >= 194).sum()),
            "mean_sel": round(g.sel_best.mean(), 1),
            "mean_regret": round(g.regret.mean(), 1)}),
        include_groups=False)
    print(bys.to_string())

    rec = per_slate[(per_slate.oracle >= 194) & (per_slate.sel_best < 194)]
    print(f"\nRECOVERABLE WEEKS ({len(rec)}):")
    if len(rec):
        print(rec[["season", "week", "sel_best", "oracle", "regret",
                   "oracle_simrank", "oracle_tag"]].to_string(index=False))
    print(f"\noracle sim-rank: median {per_slate.oracle_simrank.median():.0f} "
          f"of median pool {per_slate.n_cand.median():.0f}; "
          f"oracle already selected {per_slate.oracle_selected.mean():.1%}")
    # honest correlation: unconditional AND selection-conditioned
    unsel = per_slate[~per_slate.oracle_selected]
    if len(unsel) > 2:
        print(f"corr(sim-rank, regret): all {np.corrcoef(per_slate.oracle_simrank, per_slate.regret)[0,1]:+.3f}"
              f"  |  oracle-unselected only {np.corrcoef(unsel.oracle_simrank, unsel.regret)[0,1]:+.3f}")

    # generator shares with exclusive vs shared provenance (plan §6)
    tag_list = d.all_tags.map(lambda s: json.loads(s) if isinstance(s, str) else [])
    d2 = d.assign(n_tags=tag_list.map(len))
    print("\ngenerator shares (candidate / selected / exclusive):")
    for tg in sorted({t for lst in tag_list for t in lst}):
        has = tag_list.map(lambda L, t=tg: t in L)
        excl = has & (d2.n_tags == 1)
        print(f"  {tg:<8} cand {has.mean():6.1%}  sel "
              f"{(has & d.selected).sum() / max(int(d.selected.sum()), 1):6.1%}"
              f"  exclusive {excl.mean():6.1%}")

    # --- §6.1 PREREGISTERED DECISION GATE ---
    rec_seasons = rec.season.nunique()
    gate_pass = (len(rec) >= 4) and (rec_seasons >= 3)
    print("\n=== §6.1 DECISION GATE (preregistered) ===")
    print(f"  recoverable weeks {len(rec)} (need >=4), "
          f"spread over {rec_seasons} seasons (need >=3)")
    print(f"  VERDICT: {'PROCEED to Workstream A (reranker)' if gate_pass else 'DO NOT build the reranker — prioritize generation (B/C)'}")

    if fails:
        print("\nACCEPTANCE FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\nACCEPTANCE PASSED — panel eligible for promotion")
    if a.promote:
        # idempotent: refuse if the panel is already promoted (Sol audit 3)
        try:
            ex = query_df(f"""
                SELECT COUNT(*) AS n FROM `{settings.predictions}.{RESEARCH}`
                WHERE panel_run_id = '{a.panel_run_id}'""")
            if int(ex.n.iloc[0]) > 0:
                print(f"REFUSED: panel {a.panel_run_id} already promoted "
                      f"({int(ex.n.iloc[0])} rows)")
                return 1
        except Exception:
            pass  # research table does not exist yet
        query_df(f"""
            CREATE TABLE IF NOT EXISTS `{settings.predictions}.{RESEARCH}`
            LIKE `{settings.predictions}.{STAGING}`""")
        # research_eligible is FALSE in staging by construction; the
        # promotion is what makes rows eligible.
        query_df(f"""
            INSERT INTO `{settings.predictions}.{RESEARCH}`
            SELECT * EXCEPT (research_eligible), TRUE AS research_eligible
            FROM `{settings.predictions}.{STAGING}`
            WHERE panel_run_id = '{a.panel_run_id}'""")
        print(f"promoted panel {a.panel_run_id} -> {RESEARCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
