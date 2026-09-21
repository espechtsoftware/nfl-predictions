#!/usr/bin/env python3
"""Pre-upload exposure sheet (operator directive after Week 2 2026): what the book holds, at what share, with the
market source, DraftKings status and every flag that needs a stated reason before the CSV is uploaded.

  python scripts/exposure_sheet.py --book BOOK.csv --frame frame.parquet --contests contests.json --out DIR
        [--market-source-csv market_source.csv | --season 2026 --week 3]   # latest market_source_log batch (BigQuery) unless a CSV is given
        [--status-csv status.csv | --draft-group 153428]                    # DK statuses from a CSV (id,status) or the live draftables feed
        [--field-own-csv own.csv]                                           # optional projected field ownership (id, own in 0-1)

BOOK.csv is the entered/emitted book: header row then one row of nine dk_player_ids per lineup (the chain's book.csv);
frame.parquet is the run's frame (id, dk_player_id, name, pos, team, salary, proj[, market_points]).  Writes
exposure-sheet.md and exposure-sheet.csv; exit 0 always (the sheet is a monitor; the operator decides).  Nothing here
changes the book.
"""
import argparse, csv, json, pathlib, sys
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference.exposure_sheet import build_sheet, sheet_markdown  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--book", required=True); ap.add_argument("--frame", required=True); ap.add_argument("--contests", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--market-source-csv"); ap.add_argument("--season", type=int); ap.add_argument("--week", type=int)
ap.add_argument("--status-csv"); ap.add_argument("--draft-group", type=int); ap.add_argument("--field-own-csv")
a = ap.parse_args()

book = [r for r in csv.reader(open(a.book)) if r and not r[0].startswith("QB")]
book = [[str(x).strip() for x in r] for r in book]
fr = pd.read_parquet(a.frame)
key = "dk_player_id" if "dk_player_id" in fr.columns else "id"
players = pd.DataFrame({"id": fr[key].astype(str), "name": fr["name"] if "name" in fr.columns else fr["display_name"], "pos": fr["pos"] if "pos" in fr.columns else fr["position"],
                        "team": fr["team"], "salary": fr["salary"], "proj": fr["proj"], **({"market_points": fr["market_points"]} if "market_points" in fr.columns else {})})
if "gsis_id" in fr.columns or "id" in fr.columns:
    gsis_col = "gsis_id" if "gsis_id" in fr.columns else "id"; id_by_gsis = dict(zip(fr[gsis_col].astype(str), fr[key].astype(str)))
else:
    id_by_gsis = {}
contests = json.load(open(a.contests)); contests = contests if isinstance(contests, list) else contests["contests"]

market_source = None
if a.market_source_csv:
    market_source = pd.read_csv(a.market_source_csv)
elif a.season and a.week:
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    market_source = query_df(f"""SELECT gsis_id, display_name, source, market_points, generated_at FROM `{settings.predictions}.market_source_log`
                                 WHERE season = {a.season} AND week = {a.week} AND path = 'project-slate'
                                 QUALIFY generated_at = MAX(generated_at) OVER ()""")
    print(f"market_source_log: {len(market_source)} rows from batch {market_source.generated_at.max() if len(market_source) else None}")
if market_source is not None and len(market_source) and "id" not in market_source.columns:
    market_source = market_source.assign(id=market_source.gsis_id.astype(str).map(id_by_gsis)).dropna(subset=["id"])

status = {}
if a.status_csv:
    status = {str(r["id"]): str(r.get("status") or "") for r in csv.DictReader(open(a.status_csv))}
elif a.draft_group:
    from nfl_dfs.ingest.dk_client import fetch_draftables
    for d in fetch_draftables(a.draft_group)["draftables"]:
        status[str(d.get("playerId"))] = str(d.get("status") or "")
field_own = {}
if a.field_own_csv:
    field_own = {str(r["id"]): float(r["own"]) for r in csv.DictReader(open(a.field_own_csv))}

sheet = build_sheet(book, players, contests, market_source=market_source, status=status, field_own=field_own)
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
sheet.to_csv(out / "exposure-sheet.csv", index=False); (out / "exposure-sheet.md").write_text(sheet_markdown(sheet))
print(sheet_markdown(sheet)); print(f"written: {out / 'exposure-sheet.md'} and .csv")
