"""Read-only current quote support census; no outcome or projection comparison."""
import hashlib,json,sys
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
REPO=Path(__file__).resolve().parents[3]
OUT=Path('/home/erich/projects/review-evidence/overnight-20260918/prop-snapshot-census')
def main():
    OUT.mkdir(exist_ok=False);sys.path.insert(0,str(REPO/'src'))
    from nfl_dfs.models.prop_market import latest_pre_main_lock,STANDARD_MARKETS
    c=bigquery.Client(project='nfl-predictions-503414');queries=[]
    def read(sql,name,table):
        before=c.get_table(table);j=c.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1000000000))
        d=j.result(timeout=300).to_dataframe();after=c.get_table(table);assert before.etag==after.etag
        p=OUT/(name+'.parquet');d.to_parquet(p,index=False)
        queries.append(dict(sql=sql,job_id=j.job_id,bytes_processed=j.total_bytes_processed,source_modified=str(before.modified),source_etag=before.etag,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=len(d)))
        return d
    props=read('SELECT * FROM `nfl-predictions-503414.nfl_raw.prop_lines` WHERE season=2026 AND week=2','props','nfl-predictions-503414.nfl_raw.prop_lines')
    sched=read('SELECT season,week,gameday,gametime,game_type,weekday FROM `nfl-predictions-503414.nfl_raw.schedules` WHERE season=2026 AND week=2','schedules','nfl-predictions-503414.nfl_raw.schedules')
    props=props[props.market.isin(STANDARD_MARKETS)].copy();kept,audit=latest_pre_main_lock(props,sched)
    assert not kept.empty
    keys=['season','week','event_id','bookmaker','market','player']
    kept['_ts']=pd.to_datetime(kept.snapshot_ts,utc=True);latest=kept.groupby(keys,dropna=False)._ts.transform('max')
    stale=kept._ts.lt(latest)
    ou=kept[kept.outcome_name.isin(['Over','Under'])].copy()
    pair=ou.groupby(keys+['point'],dropna=False).agg(n_sides=('outcome_name','nunique'),n_times=('_ts','nunique'))
    recent=kept[~stale].copy();recent_ou=recent[recent.outcome_name.isin(['Over','Under'])]
    points=recent_ou.groupby(keys,dropna=False).point.nunique()
    conflicts=recent.groupby(keys+['point','outcome_name','_ts'],dropna=False).price.nunique()
    result=dict(scope='Week2 retained quote support only; no model scores or NFL outcomes',current_consumer_audit=audit,
      standard_rows=len(props),current_kept_rows=len(kept),old_snapshot_rows_retained=int(stale.sum()),
      player_book_market_groups_with_stale_rows=int(kept[stale].groupby(keys,dropna=False).ngroups),
      distinct_players_with_stale_rows=int(kept[stale].player.nunique()),
      complete_ou_pairs=int(pair.n_sides.eq(2).sum()),complete_pairs_mixing_timestamps=int((pair.n_sides.eq(2)&pair.n_times.gt(1)).sum()),
      newest_snapshot_market_groups_with_multiple_points=int(points.gt(1).sum()),
      newest_identical_key_price_conflicts=int(conflicts.gt(1).sum()),outcome_names_by_market={str(k):sorted(d.outcome_name.dropna().unique()) for k,d in recent.groupby('market')},
      queries=queries,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (OUT/'census.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
