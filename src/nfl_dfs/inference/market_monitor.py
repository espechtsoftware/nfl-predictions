"""Assessment of one market_source_log batch (pure; the script does the warehouse read)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def assess_batch(rows: pd.DataFrame, *, now: datetime, max_age_minutes: float = 120.0, min_props_share: float = 0.30) -> dict:
    if rows is None or len(rows) == 0:
        return {"ok": False, "line": "FAIL market monitor: no batch for this season/week/path", "counts": {}, "model_only_names": []}
    gen = pd.to_datetime(rows["generated_at"].iloc[0], utc=True)
    age_min = (now.astimezone(timezone.utc) - gen.to_pydatetime()).total_seconds() / 60.0
    counts = rows["source"].value_counts().to_dict()
    non_dst = int((rows["position"].astype(str).str.upper() != "DST").sum())
    props = int(counts.get("props", 0)); share = (props / non_dst) if non_dst else 0.0
    problems = []
    if age_min > max_age_minutes: problems.append(f"batch is {age_min:.0f} min old (limit {max_age_minutes:.0f})")
    if non_dst and share < min_props_share: problems.append(f"props cover {share:.0%} of non-DST rows (minimum {min_props_share:.0%})")
    if counts.get("unmatched_in_feed", 0): problems.append("batch carries unmatched_in_feed rows, which a written batch must never contain")
    model_only = rows[rows["source"].astype(str).str.startswith("model_only_no_line")]
    names = sorted(str(n) for n in model_only.get("display_name", pd.Series(dtype=object)).tolist())
    status = "OK" if not problems else "FAIL"
    line = (f"{status} market monitor: batch {gen.isoformat()} ({age_min:.0f} min old), rows {len(rows)}, sources "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f"; props share of non-DST {share:.0%}; model-only (no line) {len(names)}"
            + ("" if not problems else "; PROBLEMS: " + "; ".join(problems)))
    return {"ok": not problems, "line": line, "counts": counts, "props_share": share, "age_minutes": age_min, "model_only_names": names}
