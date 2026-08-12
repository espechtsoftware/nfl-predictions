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
 9. immutable player snapshots independently reconstruct every candidate's
    salary, actual score, roster shape, and Sunday-main-slate eligibility
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import client as bq_client, query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.candidate_features import (  # noqa: E402
    FEATURE_DEF_VERSION)
from nfl_dfs.research.panel_compare import candidate_mean_parity  # noqa: E402

STAGING = "replay_candidates_staging"
RESEARCH = "replay_candidates"
EXPECTED_SEASONS = (2019, 2021, 2022, 2023, 2024, 2025)
CAND_RANGE = (80, 400)      # default CAND_MULT=2 plausible pool size

# BigQuery INSERT ... SELECT is positional unless the destination columns are
# named.  Keep the accepted table additive and make promotion explicit so a
# newly persisted mask cannot either break promotion or land in an older
# column with the same physical type.  This is the complete candidate
# persistence contract emitted by backtest.engine.
PROMOTION_SCHEMA = (
    ("generated_at", "TIMESTAMP"),
    ("panel_run_id", "STRING"),
    ("slate_run_id", "STRING"),
    ("run_type", "STRING"),
    ("code_sha", "STRING"),
    ("code_dirty", "BOOL"),
    ("config_hash", "STRING"),
    ("lever_env", "STRING"),
    ("seeds", "STRING"),
    ("labels_complete", "BOOL"),
    ("research_eligible", "BOOL"),
    ("season", "INT64"),
    ("week", "INT64"),
    ("cand_ix", "INT64"),
    ("tag", "STRING"),
    ("all_tags", "STRING"),
    ("selected", "BOOL"),
    ("selected_rank", "INT64"),
    ("salary", "INT64"),
    ("p_line", "FLOAT64"),
    ("sim_mean", "FLOAT64"),
    ("sim_sd", "FLOAT64"),
    ("sim_q50", "FLOAT64"),
    ("sim_q90", "FLOAT64"),
    ("sim_q99", "FLOAT64"),
    ("sim_rank_p_line", "INT64"),
    ("actual_score", "FLOAT64"),
    ("actual_rank", "INT64"),
    ("tail_line", "FLOAT64"),
    ("n_entries", "INT64"),
    ("n_sims", "INT64"),
    ("n_locks", "INT64"),
    ("n_theses", "INT64"),
    ("players", "STRING"),
    ("n_worlds", "INT64"),
    ("bitorder", "STRING"),
    ("clear_bits", "STRING"),
    ("clear_bits_187", "STRING"),
    ("clear_bits_194", "STRING"),
    ("clear_bits_200", "STRING"),
    ("clear_bits_210", "STRING"),
    ("clear_bits_220", "STRING"),
    ("score_artifact_uri", "STRING"),
    ("score_artifact_sha256", "STRING"),
)


def _missing_promotion_fields(existing_names: set[str]
                              ) -> tuple[tuple[str, str], ...]:
    """Return known candidate fields absent from an older accepted table."""
    return tuple(
        field for field in PROMOTION_SCHEMA if field[0] not in existing_names)


def _ensure_promotion_schema(dataset: str) -> tuple[str, ...]:
    """Apply all missing nullable fields in one BigQuery table update.

    BigQuery counts each DDL ALTER as a table update even when
    ``IF NOT EXISTS`` makes it a no-op.  A complete 44-statement migration can
    therefore hit the metadata rate limit before reaching the actually new
    fields.  The schema API performs one update containing only missing
    fields.
    """
    from google.cloud import bigquery

    client = bq_client()
    table = client.get_table(f"{dataset}.{RESEARCH}")
    missing = _missing_promotion_fields(
        {field.name for field in table.schema})
    if not missing:
        return ()
    table.schema = list(table.schema) + [
        bigquery.SchemaField(name, data_type, mode="NULLABLE")
        for name, data_type in missing]
    client.update_table(table, ["schema"])
    return tuple(name for name, _ in missing)


def _promotion_insert_sql(dataset: str, panel_run_id: str) -> str:
    """Atomic, name-aligned candidate/snapshot promotion statement."""
    names = [name for name, _ in PROMOTION_SCHEMA]
    destination = ", ".join(f"`{name}`" for name in names)
    source = ", ".join(
        "TRUE AS `research_eligible`"
        if name == "research_eligible" else f"`{name}`"
        for name in names)
    return f"""
        BEGIN TRANSACTION;
        INSERT INTO `{dataset}.{RESEARCH}` ({destination})
        SELECT {source}
        FROM `{dataset}.{STAGING}`
        WHERE panel_run_id = '{panel_run_id}';
        UPDATE `{dataset}.slate_player_features`
        SET research_eligible = TRUE
        WHERE panel_run_id = '{panel_run_id}';
        COMMIT TRANSACTION;"""


def _candidate_count_contract(rows: pd.DataFrame, entries_expected: int,
                              multiple_expected: int
                              ) -> tuple[tuple[int, int], list[str]]:
    """Bind a multiplier-aware count range to persisted provenance."""
    failures: list[str] = []
    multiples: set[int] = set()
    for value in rows.get("lever_env", pd.Series(dtype=str)).fillna(""):
        fields = {}
        for item in str(value).split(","):
            if "=" in item:
                key, field_value = item.split("=", 1)
                fields[key] = field_value
        try:
            multiples.add(int(fields.get("CAND_MULT", "2")))
        except ValueError:
            failures.append("persisted CAND_MULT is not an integer")
            break
    if not multiples:
        failures.append("candidate rows have no multiplier provenance")
    elif multiples != {multiple_expected}:
        failures.append(
            f"persisted CAND_MULT values {sorted(multiples)} do not equal "
            f"declared {multiple_expected}")
    # Preserve the original default ceiling. The +2 allowance bounds all
    # non-leverage generators already present in the frozen generation path.
    upper = max(CAND_RANGE[1], entries_expected * (multiple_expected + 2))
    return (CAND_RANGE[0], upper), failures


def _expected_slate_pairs(seasons: tuple[int, ...]) -> set[tuple[int, int]]:
    """Return the exact regular-season replay slate keys for a panel.

    The historical 2019 schedule has 17 weeks; the other supported replay
    seasons have 18. Making this explicit lets a preregistered partial panel
    pass acceptance without weakening the default six-season contract.
    """
    return {
        (season, week)
        for season in seasons
        for week in range(1, 18 if season == 2019 else 19)
    }


def _bits(hexs: str, n: int) -> np.ndarray:
    return np.unpackbits(
        np.frombuffer(bytes.fromhex(hexs), dtype=np.uint8),
        bitorder="big")[:n].astype(bool)


def _snapshot_contract_failures(candidates: pd.DataFrame,
                                features: pd.DataFrame,
                                main_pairs: pd.DataFrame) -> list[str]:
    """Independent candidate legality and slate-boundary reconstruction."""
    fails: list[str] = []
    if features.empty:
        return ["empty immutable player-feature rows"]
    feat_key = ["slate_run_id", "id"]
    if features.duplicated(feat_key).any():
        fails.append("duplicate player ids within immutable slate snapshots")
        return fails

    expected = set(map(tuple, main_pairs[
        ["season", "week", "team", "opp"]].drop_duplicates().values))
    null_pairs = int(features[["team", "opp"]].isna().any(axis=1).sum())
    if null_pairs:
        fails.append(
            f"snapshot contains {null_pairs} players without team/opponent")
    observed = set(map(tuple, features.dropna(subset=["team", "opp"])[
        ["season", "week", "team", "opp"]].drop_duplicates().values))
    outside = observed - expected
    if outside:
        fails.append(
            f"snapshot contains {len(outside)} off-main team/opponent pairs; "
            f"examples={sorted(outside)[:4]}")
    dst_observed = set(map(tuple, features[
        features.pos.astype(str).str.upper().eq("DST")][
            ["season", "week", "team", "opp"]].drop_duplicates().values))
    missing_dst = expected - dst_observed
    extra_dst = dst_observed - expected
    if missing_dst or extra_dst:
        fails.append(
            f"DST snapshot does not exactly cover main slate: "
            f"missing={len(missing_dst)} extra={len(extra_dst)}")

    by_run = {str(run): g.set_index("id")
              for run, g in features.groupby("slate_run_id")}
    counts = {k: 0 for k in (
        "roster_size", "missing_player", "salary", "actual", "position")}
    samples: dict[str, list[str]] = {k: [] for k in counts}
    for row in candidates.itertuples(index=False):
        label = f"{int(row.season)}w{int(row.week)}c{int(row.cand_ix)}"
        ids = str(row.players or "").split(",")
        if len(ids) != 9 or len(set(ids)) != 9:
            counts["roster_size"] += 1
            samples["roster_size"].append(label)
            continue
        frame = by_run.get(str(row.slate_run_id))
        if frame is None or any(pid not in frame.index for pid in ids):
            counts["missing_player"] += 1
            samples["missing_player"].append(label)
            continue
        roster = frame.loc[ids]
        salaries = pd.to_numeric(roster.salary, errors="coerce")
        actuals = pd.to_numeric(roster.actual, errors="coerce")
        salary = float(salaries.sum()) if salaries.notna().all() else np.nan
        actual = float(actuals.sum()) if actuals.notna().all() else np.nan
        if (not np.isfinite(salary) or abs(salary - float(row.salary)) > 1e-6
                or salary > 50_000):
            counts["salary"] += 1
            samples["salary"].append(label)
        if (not np.isfinite(actual)
                or abs(actual - float(row.actual_score)) > 1e-6):
            counts["actual"] += 1
            samples["actual"].append(label)
        pos = roster.pos.astype(str).str.upper().value_counts()
        legal_shape = (
            int(pos.get("QB", 0)) == 1
            and 2 <= int(pos.get("RB", 0)) <= 3
            and 3 <= int(pos.get("WR", 0)) <= 4
            and 1 <= int(pos.get("TE", 0)) <= 2
            and int(pos.get("DST", 0)) == 1
        )
        if not legal_shape:
            counts["position"] += 1
            samples["position"].append(label)
    for kind, count in counts.items():
        if count:
            fails.append(
                f"snapshot {kind} reconstruction failed for {count} "
                f"candidates; examples={samples[kind][:4]}")
    return fails


def _authoritative_actual_failures(features: pd.DataFrame,
                                   actuals: pd.DataFrame) -> list[str]:
    """Verify persisted player labels against the canonical actual tables."""
    key = ["season", "week", "id"]
    if actuals.empty:
        return ["empty authoritative actual rows"]
    if actuals.duplicated(key).any():
        return ["duplicate authoritative actual keys"]
    authoritative = actuals.set_index(key).authoritative_actual
    unique_features = features.drop_duplicates(key)
    missing: list[str] = []
    mismatched: list[str] = []
    for row in unique_features.itertuples(index=False):
        k = (int(row.season), int(row.week), str(row.id))
        label = f"{k[0]}w{k[1]}:{k[2]}"
        if k not in authoritative.index:
            missing.append(label)
            continue
        got = pd.to_numeric(pd.Series([row.actual]), errors="coerce").iloc[0]
        expected = float(authoritative.loc[k])
        if not np.isfinite(got) or abs(float(got) - expected) > 1e-6:
            mismatched.append(label)
    fails: list[str] = []
    if missing:
        fails.append(
            f"snapshot has {len(missing)} players without authoritative "
            f"actuals; examples={missing[:4]}")
    if mismatched:
        fails.append(
            f"snapshot has {len(mismatched)} authoritative actual "
            f"mismatches; examples={mismatched[:4]}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("panel_run_id")
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--entries-expected", type=int, default=40)
    ap.add_argument("--candidate-multiple-expected", type=int, default=2)
    ap.add_argument("--allow-season-varying-config", action="store_true",
                    help="allow one config_hash/lever_env per season")
    ap.add_argument("--seasons", type=int, nargs="+",
                    default=list(EXPECTED_SEASONS))
    a = ap.parse_args()
    if not 1 <= a.entries_expected <= 150:
        ap.error("--entries-expected must be from 1 through 150")
    if not 1 <= a.candidate_multiple_expected <= 10:
        ap.error("--candidate-multiple-expected must be from 1 through 10")
    if not a.seasons or any(season < 2000 for season in a.seasons):
        ap.error("--seasons must contain valid four-digit seasons")
    if len(set(a.seasons)) != len(a.seasons):
        ap.error("--seasons may not contain duplicates")
    seasons = tuple(a.seasons)
    season_sql = ", ".join(map(str, seasons))
    expected_pairs = _expected_slate_pairs(seasons)

    d = query_df(f"""
        SELECT * FROM `{settings.predictions}.{STAGING}`
        WHERE panel_run_id = '{a.panel_run_id}'""")
    feature_rows = query_df(f"""
        SELECT season, week, slate_run_id, id, pos, team, opp, salary, actual,
               proj, mean_projection, model_points_pre, market_points,
               code_sha, research_eligible
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{a.panel_run_id}'
        """)
    main_pairs = query_df(f"""
        WITH games AS (
          SELECT season, week,
                 CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                      WHEN 'STL' THEN 'LA' ELSE home_team END AS home_team,
                 CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                      WHEN 'STL' THEN 'LA' ELSE away_team END AS away_team
          FROM `{settings.raw}.schedules`
          WHERE season IN ({season_sql})
            AND game_type = 'REG'
            AND weekday = 'Sunday'
            AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
            AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
        )
        SELECT season, week, home_team AS team, away_team AS opp FROM games
        UNION ALL
        SELECT season, week, away_team, home_team FROM games""")
    authoritative_actuals = query_df(f"""
        SELECT season, week, gsis_id AS id,
               dk_points AS authoritative_actual
        FROM `{settings.features}.player_week_actuals`
        WHERE season IN ({season_sql})
        UNION ALL
        SELECT season, week, CONCAT('DST_', team) AS id,
               dst_dk_points AS authoritative_actual
        FROM `{settings.features}.team_defense_week`
        WHERE season IN ({season_sql})
        """)
    if feature_rows.empty:
        feature_snapshots = pd.DataFrame(columns=[
            "season", "week", "slate_run_id", "n_players", "n_eligible",
            "n_bad_sha"])
    else:
        fr = feature_rows.assign(
            bad_sha=(feature_rows.code_sha.isna()
                     | feature_rows.code_sha.astype(str).str.strip().isin(
                         ("", "unknown"))))
        feature_snapshots = fr.groupby(
            ["season", "week", "slate_run_id"], as_index=False).agg(
                n_players=("id", "size"),
                n_eligible=("research_eligible", "sum"),
                n_bad_sha=("bad_sha", "sum"))
    fails: list[str] = []
    if d.empty:
        print(f"FAIL: no rows for panel {a.panel_run_id}")
        return 1
    print(f"rows: {len(d):,}  slates: {d.groupby(['season','week']).ngroups}")

    # 1 completeness
    got = set(map(tuple, d[["season", "week"]].drop_duplicates().values))
    missing = sorted(expected_pairs - got)
    if missing:
        fails.append(f"missing slates: {missing[:6]}{'...' if len(missing) > 6 else ''}")
    unexpected = sorted(got - expected_pairs)
    if unexpected:
        fails.append(
            f"unexpected slates: {unexpected[:6]}"
            f"{'...' if len(unexpected) > 6 else ''}")

    # 2 one slate_run_id per (season, week)
    dup = (d.groupby(["season", "week"]).slate_run_id.nunique() > 1)
    if dup.any():
        fails.append(f"mixed/duplicate slate runs: {dup[dup].index.tolist()[:5]}")

    # 3 selected counts
    sel = d[d.selected].groupby(["season", "week"]).size()
    bad = sel[sel != a.entries_expected]
    if len(bad):
        fails.append(
            f"selected != {a.entries_expected} in {len(bad)} slates")
    if "n_entries" not in d or not d.n_entries.eq(a.entries_expected).all():
        fails.append(
            f"persisted n_entries is not uniformly {a.entries_expected}")

    # 4 candidate counts
    candidate_range, count_contract_failures = _candidate_count_contract(
        d, a.entries_expected, a.candidate_multiple_expected)
    fails.extend(count_contract_failures)
    n_by = d.groupby(["season", "week"]).size()
    out = n_by[(n_by < candidate_range[0]) | (n_by > candidate_range[1])]
    if len(out):
        fails.append(
            f"candidate count outside {candidate_range} in {len(out)} slates")

    # 5 labels + provenance
    if not d.labels_complete.all():
        fails.append("labels_complete false somewhere")
    if d.research_eligible.any():
        fails.append("staging rows already research_eligible (must be "
                     "FALSE until promotion)")
    if d.actual_score.isna().any():
        fails.append("null actual_score in a replay panel")
    for col in ("panel_run_id", "code_sha", "config_hash"):
        if col not in d or d[col].fillna("").astype(str).str.strip().eq("").any():
            fails.append(f"missing {col} provenance")
    if d.code_sha.astype(str).eq("unknown").any():
        fails.append("unknown code_sha provenance")
    for col in ("code_sha", "seeds"):
        if d[col].fillna("").astype(str).nunique(dropna=False) != 1:
            fails.append(f"mixed {col} provenance within panel")
    for col in ("config_hash", "lever_env"):
        if a.allow_season_varying_config:
            counts = d.groupby("season")[col].apply(
                lambda values: values.fillna("").astype(str).nunique(
                    dropna=False))
            if not counts.eq(1).all():
                fails.append(f"mixed {col} provenance within a season")
        elif d[col].fillna("").astype(str).nunique(dropna=False) != 1:
            fails.append(f"mixed {col} provenance within panel")
    # Candidate rows alone are insufficient for missed-player/reranker work:
    # the point-in-time player snapshot must cover the exact same immutable
    # slate runs.  The old promotion only flipped candidate eligibility, so
    # `missed-player-analysis` could never read an otherwise accepted panel.
    cand_runs = set(map(tuple, d[["season", "week", "slate_run_id"]]
                        .drop_duplicates().values))
    feat_runs = (set(map(tuple, feature_snapshots[
                    ["season", "week", "slate_run_id"]].values))
                 if not feature_snapshots.empty else set())
    if cand_runs != feat_runs:
        fails.append("player-feature snapshots do not match candidate slate runs")
    if not feature_snapshots.empty:
        if (feature_snapshots.n_players <= 0).any():
            fails.append("empty player-feature snapshot")
        if (feature_snapshots.n_eligible != 0).any():
            fails.append("feature snapshots already research_eligible")
        if (feature_snapshots.n_bad_sha != 0).any():
            fails.append("feature snapshots have blank/unknown code provenance")
    fails.extend(_snapshot_contract_failures(d, feature_rows, main_pairs))
    fails.extend(_authoritative_actual_failures(
        feature_rows, authoritative_actuals))
    parity_report, parity_failures = candidate_mean_parity(d, feature_rows)
    print("\n=== REPLAY/LIVE MEAN PARITY ===")
    print(json.dumps(parity_report, indent=2, sort_keys=True))
    fails.extend(f"replay/live parity: {failure}"
                 for failure in parity_failures)
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
        # Older accepted tables predate the 210/220 masks now persisted in
        # staging.  Additive migration is safe for prior nullable rows.
        _ensure_promotion_schema(settings.predictions)
        # research_eligible is FALSE in staging by construction; the
        # promotion is what makes rows eligible.
        # Both target and source columns are named explicitly.  This remains
        # correct even when additive migrations append fields in a different
        # physical order from a newly-created staging table.
        # Candidates and their immutable player snapshots become eligible in
        # one transaction.  A half-promotion would strand analysis in the same
        # state as the old candidates-only implementation.
        query_df(_promotion_insert_sql(
            settings.predictions, a.panel_run_id))
        print(f"promoted panel {a.panel_run_id} -> {RESEARCH} plus player snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
