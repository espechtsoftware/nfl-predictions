"""Field-sim calibration vs real contest entries (in-season queue 10a/10b).

Answers the go/no-go question for the conditional-field-sampler build:
does our field simulator's JOINT structure reproduce what the public
actually enters? Three measurements against a real contest's entry rows
(`nfl_raw.contest_entries`, imported by `import-ownership`):

1. Dupe correlation: per distinct lineup, simulated duplicate count vs
   actual — RTS benchmarks: ~0.43 for independent sampling, ~0.72 with
   conditional (anchor-aware) sampling.
2. Independence baseline: product-of-marginals expected dupes.
3. Leftover-salary distribution: real entries spend nearly the cap; a
   field sim that leaves more money produces punt-heavy phantoms that
   overstate our own uniqueness.

Run in-season: `nfl-dfs field-calibration --season S --week W
--contest-id ID` (needs live projections + salaries for that week).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def real_dupe_table(entries: pd.DataFrame) -> pd.DataFrame:
    """distinct lineup -> actual entry count, from contest_entries rows."""
    g = entries.groupby("players_key").agg(
        count=("players_key", "size"), best_rank=("rank", "min"))
    return g.reset_index()


def sim_dupe_table(field_lineups: list, id_to_name: dict) -> pd.DataFrame:
    """Same keying for simulated field lineups (arrays of player row
    indices or ids) so the two tables join on players_key."""
    keys = ["|".join(sorted(str(id_to_name.get(i, i)) for i in lu))
            for lu in field_lineups]
    s = pd.Series(keys).value_counts()
    return pd.DataFrame({"players_key": s.index, "sim_count": s.values})


def dupe_correlation(real: pd.DataFrame, sim: pd.DataFrame,
                     n_entries: int, n_sims: int) -> dict:
    """Join on distinct lineup, rescale sim counts to contest size, and
    correlate — the RTS headline number, computed identically."""
    j = real.merge(sim, on="players_key", how="left")
    j["sim_count"] = j.sim_count.fillna(0.0) * (n_entries / max(n_sims, 1))
    out = {
        "n_distinct_real": int(len(real)),
        "match_rate": float((j.sim_count > 0).mean()),
        "dupe_corr": float(j["count"].corr(j.sim_count))
        if len(j) > 2 else float("nan"),
        "max_real_dupe": int(real["count"].max()) if len(real) else 0,
    }
    return out


def independence_baseline(entries: pd.DataFrame,
                          ownership: pd.Series) -> pd.DataFrame:
    """Product-of-marginals expected dupes per distinct real lineup
    (ownership: display_name -> pct_drafted/100). The floor any joint
    model must beat."""
    n = len(entries)
    rows = []
    for key, cnt in entries.groupby("players_key").size().items():
        names = str(key).split("|")
        probs = [float(ownership.get(nm, np.nan)) for nm in names]
        exp = float(np.prod(probs)) * n if not any(np.isnan(probs)) else np.nan
        rows.append((key, cnt, exp))
    return pd.DataFrame(rows, columns=["players_key", "count", "indep_expected"])


def salary_leftover(entries: pd.DataFrame, name_to_salary: dict,
                    cap: int = 50_000) -> pd.Series:
    """Leftover salary per real entry (entries where all names priced)."""
    out = []
    for key in entries.players_key:
        sal = [name_to_salary.get(nm) for nm in str(key).split("|")]
        if all(s is not None for s in sal):
            out.append(cap - int(sum(sal)))
    return pd.Series(out, dtype=float)


def run(season: int, week: int, contest_id: str,
        n_sims: int = 20_000) -> None:
    from ..bq import query_df
    from ..config import settings
    from .. import external_proj  # _norm

    entries = query_df(
        f"""SELECT rank, players_key FROM `{settings.raw}.contest_entries`
            WHERE season={int(season)} AND week={int(week)}
              AND contest_id=@cid
            QUALIFY ROW_NUMBER() OVER (
              PARTITION BY contest_id, entry_id ORDER BY imported_at DESC
            ) = 1""", params={"cid": str(contest_id)})
    if entries.empty:
        print(f"no contest_entries for {season} wk {week} contest "
              f"{contest_id}; run import-ownership first")
        return
    own = query_df(
        f"""SELECT display_name, AVG(pct_drafted)/100 own
            FROM `{settings.raw}.contest_ownership`
            WHERE season={int(season)} AND week={int(week)}
              AND contest_id=@cid GROUP BY display_name""",
        params={"cid": str(contest_id)})
    ownership = pd.Series(own.own.values, index=own.display_name)

    real = real_dupe_table(entries)
    base = independence_baseline(entries, ownership)
    b = base.dropna()
    print(f"real: {len(entries)} entries, {len(real)} distinct, "
          f"max dupe {real['count'].max()}")
    if len(b) > 2:
        print(f"independence baseline dupe corr: "
              f"{b['count'].corr(b.indep_expected):.3f} "
              f"(RTS reference: ~0.43)")

    # Our field sim on this week's live slate
    from ..app.main import get_store
    from ..backtest.field import sample_field

    proj = get_store().projections(season, week)
    if proj.empty:
        print("no projections for the week; sim comparison skipped")
        return
    frame = pd.DataFrame({
        "id": proj.dk_player_id, "name": proj.display_name,
        "pos": proj.position, "salary": proj.salary,
        "proj": proj.proj_points})
    frame = frame.dropna(subset=["salary", "proj"])
    field = sample_field(frame, n_lineups=n_sims)
    id_to_name = dict(zip(range(len(frame)), frame.name))
    sim = sim_dupe_table(field, id_to_name)
    res = dupe_correlation(real, sim, n_entries=len(entries), n_sims=n_sims)
    print(f"OUR FIELD SIM: dupe corr {res['dupe_corr']:.3f}  "
          f"match rate {res['match_rate']:.1%}  (RTS conditional: ~0.72)")

    sal_map = dict(zip(frame.name, frame.salary.astype(int)))
    left = salary_leftover(entries, sal_map)
    if len(left):
        print(f"real leftover salary: median {left.median():.0f} "
              f"p90 {left.quantile(.9):.0f} share>$1k {(left>1000).mean():.0%}")
