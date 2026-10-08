#!/usr/bin/env python3
"""Did the T-70 build's DraftKings pull carry the 10:30 CT inactives? (O-59; the operator 10-08: "Add a 10:47 pull", with a
loud warning.) In W2-W4 DraftKings posted the inactive statuses AFTER the 10:33 pull (W4: 90 out at 09:59 and at 10:33,
109 at 10:59), so the T-70 frame ran on pre-inactives statuses. check_salary_pull.py checks the pull's TIME; this checks
its CONTENT.

    python scripts/check_t70_statuses.py <run dir> --group G --inactives-utc <the T-70 gate's MIN_PROJ_GENERATED_AT>

It compares the receipt's `salary_pull` with the newest pull of the same draft group made before the inactives (the
morning pull):
  * OUT / IR / D / O count, and the Questionable count (DK clears most Questionables when the inactives land:
    W4 13 -> 5, W3 16 -> 5, W2 9 -> 5).
  * POST-INACTIVES = the out count rose OR the Questionable count fell.
  * PRE-INACTIVES = neither moved: one loud banner saying the ~11:00 pre-upload status check is the only safety net today.
It never refuses the build (the operator chose a warning). Exit 0 always; a check that cannot run says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_dir_publishable import parse_utc  # noqa: E402

OUT_STATUSES = ("OUT", "IR", "D", "O")
Q_STATUSES = ("Q", "QUESTIONABLE")
BANNER = "!" * 96


def decide(morning: tuple[int, int], build: tuple[int, int]) -> tuple[str, str]:
    """(verdict, line) from (out, questionable) counts of the morning pull and the build's pull."""
    (out_m, q_m), (out_b, q_b) = morning, build
    moved = out_b > out_m or q_b < q_m
    detail = f"out {out_m} -> {out_b}, questionable {q_m} -> {q_b}"
    if moved:
        return "POST", f"DK STATUSES POST-INACTIVES: {detail} (the T-70 pull carries DraftKings' inactive update)"
    return "PRE", (f"DK STATUSES LOOK PRE-INACTIVES: {detail} -- the T-70 build's pull shows no inactive update; THE ~11:00 "
                   "PRE-UPLOAD STATUS CHECK IS THE ONLY SAFETY NET TODAY (O-59)")


def pull_counts(group: str) -> list[tuple[object, int, int]]:
    """(pulled_at, out, questionable) per DraftKings pull of the draft group, from nfl_raw.dk_salaries."""
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    c = bigquery.Client(project=settings.project)
    q = f"""SELECT pulled_at,
                   COUNTIF(UPPER(status) IN UNNEST(@o)) AS n_out, COUNTIF(UPPER(status) IN UNNEST(@q)) AS n_q
            FROM `{settings.raw}.dk_salaries` WHERE CAST(draft_group_id AS STRING) = @g GROUP BY pulled_at"""
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("g", "STRING", str(group)),
        bigquery.ArrayQueryParameter("o", "STRING", list(OUT_STATUSES)),
        bigquery.ArrayQueryParameter("q", "STRING", list(Q_STATUSES))])
    return [(r.pulled_at, int(r.n_out), int(r.n_q)) for r in c.query(q, job_config=cfg).result()]


def check(run: Path, group: str, inactives_utc: str, counts=pull_counts) -> tuple[str, str]:
    try:
        pull = json.loads((Path(run) / "receipt.json").read_text()).get("salary_pull")
        build_t, inact = parse_utc(pull), parse_utc(inactives_utc)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return "UNAVAILABLE", f"DK STATUS CHECK UNAVAILABLE: no readable receipt salary_pull / inactives time ({exc})"
    rows = sorted((parse_utc(str(t)), o, q) for t, o, q in counts(group))
    morning = [r for r in rows if r[0] < inact]
    build = [r for r in rows if r[0] <= build_t]
    if not morning or not build:
        return "UNAVAILABLE", (f"DK STATUS CHECK UNAVAILABLE: group {group} has no pull before the inactives "
                               f"({len(morning)}) or at the build's pull {pull} ({len(build)})")
    m, b = morning[-1], build[-1]
    verdict, line = decide((m[1], m[2]), (b[1], b[2]))
    return verdict, f"{line}; morning pull {m[0].isoformat()}, build pull {b[0].isoformat()}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path); ap.add_argument("--group", required=True); ap.add_argument("--inactives-utc", required=True)
    a = ap.parse_args(argv)
    try:
        verdict, line = check(a.run, a.group, a.inactives_utc)
    except Exception as exc:                                  # a warning tool: never fail the build
        verdict, line = "UNAVAILABLE", f"DK STATUS CHECK UNAVAILABLE: {type(exc).__name__}: {exc}"
    if verdict == "PRE":
        print(f"\n{BANNER}\n!!! {line}\n{BANNER}\n")
    else:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
