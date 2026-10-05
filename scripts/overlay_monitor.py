#!/usr/bin/env python3
"""Read-only DraftKings overlay monitor (path-to-winning plan item 1, 2026-10-05; reviewer cleared the design).

An OVERLAY is a guaranteed contest whose prize pool exceeds the entry fees collected: pool / (entries x fee) > 1. That
ratio is already net of rake. It is the expected return multiple of an average entrant, so above 1.0 a field-average
lineup is +EV. The only structural +EV seen in Weeks 1-4 was one (P1: the W2 FFWC 4x supersat, pool ratio 1.22).

The monitor FLAGS ONLY; the operator decides what to enter. Two steps:

  flag      before lock: from the hourly `nfl_raw.dk_contest_fills` snapshots, every guaranteed NFL contest of the
            slate, its LATEST snapshot (time, minutes before lock, entries/max, fee, pool), the pool ratio NOW
            (assuming no further entries), and the entries at which it stops being an overlay. Writes
            flags-<slate>-<utc>.csv.
  finalize  after lock: fetch every flagged contest's FINAL entries from the public contest API (no login;
            scripts/dk_contest_details.fetch) and record the final pool ratio and whether the overlay materialised.
            Writes <flags>-final.csv and prints the materialisation rate. That log is how we learn whether
            early-snapshot overlays are real (contests fill most in the last hour; the snapshots are hourly and
            stop at lock).

    python scripts/overlay_monitor.py flag --slate 2026-10-11 [--out-dir ~/overlay] [--min-ratio 1.0]
    python scripts/overlay_monitor.py finalize --flags ~/overlay/flags-2026-10-11-<utc>.csv

Outputs go to --out-dir (default ~/overlay), never under a ~/weekN-sunday tree (O-24). No dollar amounts in tracked
files: the CSVs carry contest fees and pools, which are public contest facts, not the operator's stake.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT = "nfl-predictions-503414"
DEFAULT_OUT = Path.home() / "overlay"


def latest_snapshots(snaps: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per contest: its latest snapshot strictly before lock (and before `now`, if given)."""
    s = snaps[snaps.pulled_at < snaps.start_time]
    if now is not None:
        s = s[s.pulled_at <= now]
    s = s.sort_values(["contest_id", "pulled_at"]).groupby("contest_id", as_index=False).tail(1)
    return s.reset_index(drop=True)


def overlay_table(latest: pd.DataFrame, min_ratio: float = 1.0) -> pd.DataFrame:
    """Guaranteed, paid contests with entries; the pool ratio now; flagged when it exceeds min_ratio."""
    t = latest[(latest.is_guaranteed.fillna(False)) & (latest.entry_fee > 0) & (latest.entries > 0)].copy()
    t["pool_ratio_now"] = t.prize_pool / (t.entries * t.entry_fee)
    t["breakeven_entries"] = (t.prize_pool / t.entry_fee).apply(lambda x: int(x) if x == int(x) else int(x) + 1)
    t["mins_before_lock"] = ((t.start_time - t.pulled_at).dt.total_seconds() / 60).round(1)
    t["fill_rate_now"] = t.entries / t.max_entries
    t["flag"] = t.pool_ratio_now > min_ratio
    cols = ["contest_id", "name", "entry_fee", "max_entries", "entries", "fill_rate_now", "prize_pool",
            "pool_ratio_now", "breakeven_entries", "pulled_at", "start_time", "mins_before_lock", "flag"]
    return t[cols].sort_values(["flag", "pool_ratio_now"], ascending=[False, False]).reset_index(drop=True)


def finalize(flags: pd.DataFrame, fetch, sleep: float = 0.4) -> pd.DataFrame:
    """Attach each flagged contest's final entries (from `fetch(cid) -> dict` with 'entries') and the final ratio."""
    rows = []
    for r in flags[flags.flag].itertuples():
        try:
            d = fetch(str(r.contest_id))
            final = int(d["entries"])
            err = ""
        except Exception as exc:  # noqa: BLE001 - recorded per contest, never silently dropped
            final, err = None, str(exc)[:200]
        ratio = (r.prize_pool / (final * r.entry_fee)) if final else None
        rows.append({"contest_id": r.contest_id, "final_entries": final,
                     "final_pool_ratio": ratio, "materialised": (ratio is not None and ratio > 1.0), "error": err})
        time.sleep(sleep)
    f = pd.DataFrame(rows, columns=["contest_id", "final_entries", "final_pool_ratio", "materialised", "error"])
    return flags.merge(f, on="contest_id", how="left")


def load_snapshots(slate: str) -> pd.DataFrame:
    from google.cloud import bigquery
    q = f"""SELECT contest_id, name, entry_fee, max_entries, entries, prize_pool, is_guaranteed, pulled_at, start_time
            FROM `{PROJECT}.nfl_raw.dk_contest_fills`
            WHERE sport = 'NFL' AND DATE(start_time, 'America/Chicago') = @slate"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("slate", "DATE", slate)])
    df = bigquery.Client(project=PROJECT).query(q, job_config=cfg).to_dataframe()
    for c in ("pulled_at", "start_time"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def cmd_flag(a) -> int:
    snaps = load_snapshots(a.slate)
    if snaps.empty:
        print(f"overlay_monitor: no NFL contest snapshots for slate {a.slate}", file=sys.stderr)
        return 2
    t = overlay_table(latest_snapshots(snaps, pd.Timestamp.now(tz="UTC")), a.min_ratio)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out_dir / f"flags-{a.slate}-{stamp}.csv"
    t.to_csv(out, index=False)
    fl = t[t.flag]
    print(f"{len(t)} guaranteed paid contests with entries; {len(fl)} overlaid at their latest snapshot -> {out}")
    print("NOTE: a snapshot hours before lock overstates overlays (contests fill late); judge by mins_before_lock, "
          "and run `finalize` after lock to log what materialised.")
    show = fl.head(a.show)[["contest_id", "name", "entry_fee", "entries", "max_entries", "pool_ratio_now",
                            "breakeven_entries", "mins_before_lock"]]
    if len(show):
        print(show.to_string(index=False))
    return 0


def cmd_finalize(a) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dk_contest_details import fetch
    flags = pd.read_csv(a.flags)
    out = finalize(flags, fetch, a.sleep)
    dst = a.flags.with_name(a.flags.stem + "-final.csv")
    out.to_csv(dst, index=False)
    f = out[out.flag]
    ok = f.final_entries.notna()
    print(f"{len(f)} flagged; final entries fetched for {int(ok.sum())}; "
          f"overlay materialised in {int(f.materialised.fillna(False).sum())} -> {dst}")
    if (~ok).any():
        print(f"fetch failures: {int((~ok).sum())} (see the error column)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flag"); f.add_argument("--slate", required=True, help="slate date (America/Chicago), YYYY-MM-DD")
    f.add_argument("--out-dir", type=Path, default=DEFAULT_OUT); f.add_argument("--min-ratio", type=float, default=1.0)
    f.add_argument("--show", type=int, default=25)
    z = sub.add_parser("finalize"); z.add_argument("--flags", type=Path, required=True)
    z.add_argument("--sleep", type=float, default=0.4)
    a = ap.parse_args(argv)
    if a.cmd == "flag":
        if "-sunday" in str(a.out_dir):
            print("overlay_monitor: refusing to write under a week's input tree (O-24)", file=sys.stderr)
            return 2
        return cmd_flag(a)
    return cmd_finalize(a)


if __name__ == "__main__":
    raise SystemExit(main())
