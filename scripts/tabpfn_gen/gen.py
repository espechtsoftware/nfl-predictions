"""Walk-forward TabPFN-v2 projection quantiles (the sim's default
marginals since Addendum 50). Runs on Cloud Run L4 (job: tabpfn-gen).

Modes:
- default: for each season in SEASONS, context = strictly-earlier panel
  rows, predict all rows -> features.tabpfn_projections (WRITE_TRUNCATE).
- TABPFN_UPCOMING="2026:1": ALSO predict the upcoming week's rows from
  player_week_inference (context = all prior TRAINING rows) and append
  them — this is what makes the lever live on Sundays. Run weekly.
"""
import gc
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT"]
OUTPUT_TABLE = os.environ.get(
    "TABPFN_OUTPUT_TABLE", "tabpfn_projections").strip()
CODE_SHA = os.environ.get("CODE_SHA", "").strip()
PIT_OUTPUT_TABLE = "tabpfn_projections_pit_v2"
OUTPUT_PREFIX = "TABPFN_GEN_JSON="
UPCOMING_ONLY = os.environ.get("TABPFN_UPCOMING_ONLY", "").strip()
UPCOMING = os.environ.get("TABPFN_UPCOMING", "").strip()
QS = [0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
      0.60, 0.70, 0.80, 0.90, 0.95, 0.99]
QCOLS = [f"q{int(q*100):02d}" for q in QS]
OUTPUT_COLUMNS = ["season", "week", "gsis_id", "mean", *QCOLS]
CTX_MAX = 28_000
SEASONS = [2019, 2021, 2022, 2023, 2024, 2025]

bq = bigquery.Client(project=PROJECT)
feature_bytes = Path("/app/features.txt").read_bytes()
feats = feature_bytes.decode("utf-8").split()
feature_sha = hashlib.sha256(feature_bytes).hexdigest()
if OUTPUT_TABLE not in {"tabpfn_projections", PIT_OUTPUT_TABLE}:
    raise ValueError(f"unlicensed TABPFN_OUTPUT_TABLE={OUTPUT_TABLE!r}")
if UPCOMING_ONLY not in {"", "0", "1"}:
    raise ValueError("TABPFN_UPCOMING_ONLY must be empty, 0, or 1")
if UPCOMING_ONLY == "1" and not UPCOMING:
    raise ValueError("TABPFN_UPCOMING_ONLY=1 requires TABPFN_UPCOMING=season:week")
if UPCOMING_ONLY == "1" and OUTPUT_TABLE != "tabpfn_projections":
    raise ValueError("upcoming-only refresh is allowed only for the mutable live cache")
if OUTPUT_TABLE == PIT_OUTPUT_TABLE:
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("PIT-clean canonical cache requires immutable CODE_SHA")
    forbidden = {
        "TABPFN_COMPONENTS": os.environ.get("TABPFN_COMPONENTS", ""),
        "TABPFN_UPCOMING": UPCOMING,
        "TABPFN_UPCOMING_ONLY": UPCOMING_ONLY,
        "TABPFN_SEASONS": os.environ.get("TABPFN_SEASONS", ""),
        "TABPFN_WRITE": os.environ.get("TABPFN_WRITE", ""),
    }
    active = sorted(name for name, value in forbidden.items() if value.strip())
    if active:
        raise ValueError(
            f"PIT-clean canonical cache has forbidden envs: {active}")


def prep(df):
    df = df[df.position.isin(["QB", "RB", "WR", "TE"])].copy()
    df["pos_code"] = df.position.map(
        {p: i for i, p in enumerate(["QB", "RB", "WR", "TE"])})
    for c in X_cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


X_cols = sorted(feats) + ["pos_code"]
source_table = f"{PROJECT}.nfl_features.player_week_training"
source_meta = bq.get_table(source_table)
panel = bq.query(f"SELECT * FROM `{source_table}`").to_dataframe()
source_checksum = int(bq.query(f"""
    SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
    FROM `{source_table}` t
""").to_dataframe().iloc[0]["checksum"])
source_schema = json.dumps(
    [(field.name, field.field_type, field.mode)
     for field in source_meta.schema],
    separators=(",", ":"),
)
source_schema_sha = hashlib.sha256(source_schema.encode()).hexdigest()
panel = prep(panel)
print(f"panel {len(panel):,} rows {panel.season.min()}-{panel.season.max()}",
      flush=True)

from tabpfn import TabPFNRegressor

rng = np.random.default_rng(7)


def fit_predict(tr, te):
    if len(tr) > CTX_MAX:
        tr = tr.iloc[rng.choice(len(tr), CTX_MAX, replace=False)]
    reg = TabPFNRegressor(device="cuda" if torch.cuda.is_available() else "cpu",
                          n_estimators=4, ignore_pretraining_limits=True,
                          random_state=7)
    reg.fit(tr[X_cols].to_numpy(np.float32),
            tr.y_dk_points.to_numpy(np.float32))
    try:
        qs = reg.predict(te[X_cols].to_numpy(np.float32),
                         output_type="quantiles", quantiles=QS)
        mean = reg.predict(te[X_cols].to_numpy(np.float32))
        f = te[["season", "week", "gsis_id"]].copy()
        f["mean"] = np.asarray(mean, float)
        for c, arr in zip(QCOLS, qs):
            f[c] = np.maximum(np.asarray(arr, float), 0.0)
    finally:
        # TabPFN/PyTorch retains native allocator state across repeated fits.
        # Release it explicitly so a full walk-forward refresh does not grow
        # until the container is terminated between adjacent seasons.
        del reg
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return f


def validate_output_frame(frame, label):
    missing = set(OUTPUT_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{label} is empty")
    if frame[["season", "week", "gsis_id"]].isna().any().any():
        raise ValueError(f"{label} contains null target keys")
    if frame.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError(f"{label} target keys are not unique")
    values = frame[["mean", *QCOLS]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} contains non-finite predictions")
    if np.any(np.diff(frame[QCOLS].to_numpy(float), axis=1) < -1e-8):
        raise ValueError(f"{label} contains unordered quantiles")


upcoming_target = None
if UPCOMING:
    if not re.fullmatch(r"\d{4}:\d{1,2}", UPCOMING):
        raise ValueError("TABPFN_UPCOMING must have season:week form")
    upcoming_target = tuple(int(x) for x in UPCOMING.split(":"))

out = []
base_cache = None
if UPCOMING_ONLY == "1":
    us, uw = upcoming_target
    cache_table = f"{PROJECT}.nfl_features.{OUTPUT_TABLE}"
    cache_meta = bq.get_table(cache_table)
    if not cache_meta.etag or cache_meta.modified is None:
        raise ValueError("existing live cache lacks immutable metadata")
    schema_names = [field.name for field in cache_meta.schema]
    if schema_names != OUTPUT_COLUMNS:
        raise ValueError("existing live cache schema/order differs")
    cached = bq.query(
        f"SELECT {','.join(OUTPUT_COLUMNS)} FROM `{cache_table}`"
    ).to_dataframe()
    validate_output_frame(cached, "existing live cache")
    missing_seasons = sorted(set(SEASONS) - set(cached.season.astype(int)))
    if missing_seasons:
        raise ValueError(
            f"existing live cache lacks historical seasons {missing_seasons}"
        )
    base_checksum = int(bq.query(f"""
        SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{cache_table}` t
    """).to_dataframe().iloc[0]["checksum"])
    cached = cached[
        ~(
            cached.season.astype(int).eq(us)
            & cached.week.astype(int).eq(uw)
        )
    ].copy()
    out.append(cached)
    base_cache = {
        "table": cache_table,
        "etag": cache_meta.etag,
        "last_modified": cache_meta.modified.isoformat(),
        "rows": int(cache_meta.num_rows),
        "content_checksum": base_checksum,
    }
    print(
        f"upcoming-only: preserving {len(cached):,} validated cache rows",
        flush=True,
    )
else:
    for S in SEASONS:
        tr = panel[(panel.season < S) & panel.y_dk_points.notna()]
        te = panel[panel.season == S]
        if tr.empty or te.empty:
            print(f"skip {S}", flush=True)
            continue
        t0 = time.time()
        out.append(fit_predict(tr, te))
        print(f"season {S}: pred {len(te):,} ({time.time()-t0:.0f}s)", flush=True)

# TABPFN_COMPONENTS=1: instead of dk-points quantiles, generate
# walk-forward per-COMPONENT means (the 11 component-model targets,
# with their exact training-subset definitions) into
# features.tabpfn_components. TABPFN_SEASONS="2019,2021,2022" splits
# the work across executions (the 1h GPU task cap); TABPFN_WRITE=append
# accumulates the second half.
if os.environ.get("TABPFN_COMPONENTS", "") not in ("", "0"):
    if UPCOMING_ONLY == "1":
        raise ValueError("component mode cannot be combined with upcoming-only")
    seasons = [int(s) for s in os.environ.get(
        "TABPFN_SEASONS", ",".join(map(str, SEASONS))).split(",")]
    y = panel
    def specs(tr):
        recv = tr[tr.position != "QB"]
        qb = tr[tr.position == "QB"]
        caught = recv[recv.y_targets > 0]
        with_rec = recv[recv.y_receptions > 0]
        rushed = tr[tr.y_carries > 0]
        att = qb[qb.y_pass_attempts > 0]
        return {
            "targets": (recv, recv.y_targets),
            "catch_rate": (caught, caught.y_receptions / caught.y_targets),
            "ypr": (with_rec, with_rec.y_rec_yards / with_rec.y_receptions),
            "rec_tds": (recv, recv.y_rec_tds),
            "carries": (tr, tr.y_carries),
            "ypc": (rushed, rushed.y_rush_yards / rushed.y_carries),
            "rush_tds": (tr, tr.y_rush_tds),
            "pass_attempts": (qb, qb.y_pass_attempts),
            "ypa": (att, att.y_pass_yards / att.y_pass_attempts),
            "pass_tds": (qb, qb.y_pass_tds),
            "interceptions": (qb, qb.y_interceptions),
        }
    frames = []
    for S in seasons:
        tr_all = panel[(panel.season < S) & panel.y_dk_points.notna()]
        te = panel[panel.season == S]
        if tr_all.empty or te.empty:
            continue
        f = te[["season", "week", "gsis_id"]].copy()
        for name, (rows, label) in specs(tr_all).items():
            ok = label.notna() & np.isfinite(label)
            rows, label = rows[ok], label[ok]
            if len(rows) > CTX_MAX:
                ix = rng.choice(len(rows), CTX_MAX, replace=False)
                rows, label = rows.iloc[ix], label.iloc[ix]
            t0 = time.time()
            reg = TabPFNRegressor(
                device="cuda" if torch.cuda.is_available() else "cpu",
                n_estimators=2, ignore_pretraining_limits=True,
                random_state=7)
            reg.fit(rows[X_cols].to_numpy(np.float32),
                    label.to_numpy(np.float32))
            f[name] = np.asarray(
                reg.predict(te[X_cols].to_numpy(np.float32)), float)
            del reg
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"comp {S}/{name}: ctx {len(rows):,} ({time.time()-t0:.0f}s)",
                  flush=True)
        frames.append(f)
    allc = pd.concat(frames, ignore_index=True)
    disp = ("WRITE_APPEND" if os.environ.get("TABPFN_WRITE") == "append"
            else "WRITE_TRUNCATE")
    bq.load_table_from_dataframe(
        allc, f"{PROJECT}.nfl_features.tabpfn_components",
        job_config=bigquery.LoadJobConfig(write_disposition=disp)).result()
    print(f"loaded {len(allc):,} component rows ({disp}); TABPFN_GEN_DONE",
          flush=True)
    raise SystemExit(0)

if upcoming_target is not None:
    us, uw = upcoming_target
    inf = bq.query(
        f"SELECT * FROM `{PROJECT}.nfl_features.player_week_inference` "
        f"WHERE season={us} AND week={uw}").to_dataframe()
    inf = prep(inf)
    tr = panel[panel.y_dk_points.notna()]
    if not inf.empty:
        t0 = time.time()
        out.append(fit_predict(tr, inf))
        print(f"upcoming {us} w{uw}: pred {len(inf):,} "
              f"({time.time()-t0:.0f}s)", flush=True)
    else:
        print(f"upcoming {us} w{uw}: no inference rows", flush=True)

allf = pd.concat(out, ignore_index=True).drop_duplicates(
    ["season", "week", "gsis_id"], keep="last")
validate_output_frame(allf, "TabPFN canonical cache")
if base_cache is not None:
    current_cache_meta = bq.get_table(base_cache["table"])
    if (
        current_cache_meta.etag != base_cache["etag"]
        or int(current_cache_meta.num_rows) != base_cache["rows"]
        or current_cache_meta.modified.isoformat() != base_cache["last_modified"]
    ):
        raise ValueError("live cache changed after upcoming-only read")
disposition = (bigquery.WriteDisposition.WRITE_EMPTY
               if OUTPUT_TABLE == PIT_OUTPUT_TABLE
               else bigquery.WriteDisposition.WRITE_TRUNCATE)
job = bq.load_table_from_dataframe(
    allf, f"{PROJECT}.nfl_features.{OUTPUT_TABLE}",
    job_config=bigquery.LoadJobConfig(write_disposition=disposition))
job.result()
report = {
    "disposition": "tabpfn-canonical-cache-generated",
    "code_sha": CODE_SHA,
    "output_table": f"{PROJECT}.nfl_features.{OUTPUT_TABLE}",
    "write_disposition": str(disposition),
    "output_rows": len(allf),
    "unique_keys": int(
        allf[["season", "week", "gsis_id"]].drop_duplicates().shape[0]),
    "target_seasons": [] if UPCOMING_ONLY == "1" else SEASONS,
    "upcoming_target": list(upcoming_target) if upcoming_target else None,
    "upcoming_only": UPCOMING_ONLY == "1",
    "base_cache": base_cache,
    "context_law": "all-prior-nonnull-labels",
    "context_max": CTX_MAX,
    "random_seed": 7,
    "n_estimators": 4,
    "feature_contract_sha256": feature_sha,
    "training_source": {
        "table": source_table,
        "last_modified": source_meta.modified.isoformat(),
        "schema_sha256": source_schema_sha,
        "content_checksum": source_checksum,
        "rows": len(panel),
        "active_rows": int(panel.was_active.fillna(False).astype(bool).sum()),
        "inactive_rows": int((~panel.was_active.fillna(False).astype(bool)).sum()),
    },
}
print(f"loaded {len(allf):,} rows; TABPFN_GEN_DONE", flush=True)
print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)
