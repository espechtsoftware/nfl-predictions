"""In-season weekly import of SIS game-grain team context (operator directive 2026-09-21).

The frozen tranche importers (`sis_team_context`, `sis_team_run_context`) accept only their historical 108-artifact
plans. This module reads the artifacts of an in-season plan (season 2026, a small week window, the same reports)
with the SAME artifact validators (manifest hash, schema, identities, game grain) and the same merge law, and appends
the resulting team-game rows to the same two tables:

* pass-defense / pass-rush / blocking reports -> ``nfl_raw.sis_team_context_game``
* passing / rushing / run-defense reports      -> ``nfl_raw.sis_team_run_context_game``

Append-once by canonical (season, week, team): rows whose key already exists in the table are reported and never
rewritten; a week is loaded even when charting is incomplete (SIS posts games over the following days), and the
audit records which games have both sides. Column sets are checked against the live table before any write (fail
closed). Nothing is substituted; every skipped key is named in the audit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..ops.sis_downloads import artifact_name, load_plan
from . import sis_team_context as ctx
from . import sis_team_run_context as run_ctx

FAMILIES = {
    "context": {"module": ctx, "reports": tuple(ctx.EXPECTED_REPORTS), "table": ctx.TABLE},
    "run_context": {"module": run_ctx, "reports": tuple(run_ctx.EXPECTED_REPORTS), "table": run_ctx.TABLE},
}
KEY = ("season", "week", "team")


def _merge_family(root: Path, specs, module, reports: tuple[str, ...]) -> pd.DataFrame | None:
    """Read every artifact of one family present in the plan and merge the reports on team-game keys."""
    parts: dict[str, list[pd.DataFrame]] = {}
    for spec in specs:
        if spec.report not in reports:
            continue
        artifact = root / artifact_name(spec)
        manifest = artifact.with_suffix(".manifest.json")
        if not artifact.is_file() or not manifest.is_file():
            raise FileNotFoundError(artifact if not artifact.is_file() else manifest)
        parts.setdefault(spec.report, []).append(module._read_artifact(artifact, manifest, spec.report))
    if not parts:
        return None
    missing = [r for r in reports if r not in parts]
    if missing:
        raise ValueError(f"family artifacts incomplete: missing reports {missing}")
    frames = {}
    for report, chunks in parts.items():
        combined = pd.concat(chunks, ignore_index=True)
        if combined.duplicated(list(ctx.KEY_COLUMNS)).any():
            raise ValueError(f"SIS {report} repeats a team-game across windows")
        frames[report] = combined
    base = frames[reports[0]]
    for report in reports[1:]:
        incoming = frames[report]
        if set(map(tuple, base[list(ctx.KEY_COLUMNS)].to_numpy())) != set(map(tuple, incoming[list(ctx.KEY_COLUMNS)].to_numpy())):
            raise ValueError(f"SIS {report} team-game universe differs from {reports[0]}")
        if "team_id" in incoming:
            incoming = incoming.drop(columns=["team_id"])
        base = base.merge(incoming, on=list(ctx.KEY_COLUMNS), how="inner", validate="one_to_one")
    name_to_id = {}
    for frame in frames.values():
        for row in frame[["team_name", "team_id"]].drop_duplicates().itertuples(index=False):
            prior = name_to_id.setdefault(str(row.team_name), int(row.team_id))
            if prior != int(row.team_id):
                raise ValueError(f"SIS team name maps to multiple IDs: {row.team_name}")
    if missing := (set(base.team_name) | set(base.opp_name)) - set(ctx.TEAM_ABBREVIATIONS):
        raise ValueError(f"SIS team abbreviations missing: {sorted(missing)}")
    if missing := set(base.opp_name) - set(name_to_id):
        raise ValueError(f"SIS opponent IDs missing: {sorted(missing)}")
    base["team"] = base.team_name.map(ctx.TEAM_ABBREVIATIONS)
    base["opp"] = base.opp_name.map(ctx.TEAM_ABBREVIATIONS)
    base["opp_team_id"] = base.opp_name.map(name_to_id).astype(int)
    base["game_key"] = base.apply(lambda row: f"{row.season}-{row.week:02d}-" + "-".join(sorted((row.team, row.opp))), axis=1)
    if base.duplicated(list(KEY)).any():
        raise ValueError("SIS weekly table repeats a canonical team-week")
    return base.sort_values(["season", "week", "team_id"]).reset_index(drop=True)


def plan_append(frame: pd.DataFrame, existing_keys: set[tuple]) -> tuple[pd.DataFrame, list[tuple]]:
    """Split the merged frame into rows to append and keys already present (never rewritten)."""
    keys = [tuple(int(v) if c != "team" else str(v) for c, v in zip(KEY, row)) for row in frame[list(KEY)].to_numpy()]
    mask = [k not in existing_keys for k in keys]
    skipped = sorted(k for k, m in zip(keys, mask) if not m)
    return frame[mask].reset_index(drop=True), skipped


def coverage(frame: pd.DataFrame) -> dict:
    out = {}
    for (season, week), g in frame.groupby(["season", "week"]):
        sides = g.groupby("game_key").size()
        out[f"{int(season)}-{int(week):02d}"] = {"rows": int(len(g)), "games": int(len(sides)), "games_with_both_sides": int((sides == 2).sum()), "games_one_side": int((sides == 1).sum())}
    return out


def run(input_dir: str | Path, plan_path: str | Path, *, write: bool = False, now: datetime | None = None) -> dict:
    """Validate, merge, compare against the live tables and (optionally) append. Returns the audit."""
    from ..bq import client, load_dataframe, query_df
    from ..config import settings

    root, plan = Path(input_dir), Path(plan_path)
    specs = load_plan(plan)
    source_run_id = f"sis-team-context-weekly:{plan.stem}"
    audit: dict = {"plan": str(plan), "plan_sha256": ctx._sha256(plan), "input_dir": str(root), "source_run_id": source_run_id,
                   "write_requested": bool(write), "families": {}, "checked_at_utc": (now or datetime.now(timezone.utc)).isoformat()}
    for family, spec in FAMILIES.items():
        frame = _merge_family(root, specs, spec["module"], spec["reports"])
        if frame is None:
            audit["families"][family] = {"status": "no artifacts in this plan"}
            continue
        table_ref = f"{settings.raw}.{spec['table']}"
        live_cols = [f.name for f in client().get_table(table_ref).schema]
        frame["source_run_id"] = source_run_id
        frame["ingested_at"] = now or datetime.now(timezone.utc)
        extra = sorted(set(frame.columns) - set(live_cols)); absent = sorted(set(live_cols) - set(frame.columns))
        if extra:
            raise ValueError(f"{family}: columns not in the live table {spec['table']}: {extra}")
        seasons = sorted(int(s) for s in frame.season.unique()); weeks = sorted(int(w) for w in frame.week.unique())
        existing = query_df(f"SELECT season, week, team, team_name, source_run_id FROM `{table_ref}` WHERE season IN ({', '.join(map(str, seasons))}) AND week IN ({', '.join(map(str, weeks))})")
        existing_keys = {(int(r.season), int(r.week), str(r.team)) for r in existing.itertuples() if pd.notna(r.team)}
        # rows already in the table for these weeks that carry no canonical team key (an unreceipted load) cannot be
        # matched by key; they are named here so the collision is visible, never silently doubled or deleted
        degenerate = existing[existing.team.isna()]
        to_append, skipped = plan_append(frame, existing_keys)
        rec = {"status": "audited", "table": table_ref, "rows_merged": int(len(frame)), "rows_to_append": int(len(to_append)),
               "keys_already_present": [list(k) for k in skipped], "columns_absent_in_frame_filled_null": absent,
               "existing_rows_without_team_key": {"rows": int(len(degenerate)), "weeks": sorted(int(w) for w in degenerate.week.unique()) if len(degenerate) else [],
                                                  "source_run_ids": sorted({str(v) for v in degenerate.source_run_id.unique()}) if len(degenerate) else []},
               "coverage_merged": coverage(frame), "coverage_appended": coverage(to_append) if len(to_append) else {},
               "artifact_sha256": sorted({str(v) for c in frame.columns if c.startswith("source_sha256_") for v in frame[c].unique()})}
        if write and len(to_append):
            for c in absent:
                to_append[c] = None
            load_dataframe(to_append[live_cols], table_ref, write_disposition="WRITE_APPEND")
            rec["status"] = "appended"
        elif write:
            rec["status"] = "nothing to append (all keys present)"
        audit["families"][family] = rec
    return audit
