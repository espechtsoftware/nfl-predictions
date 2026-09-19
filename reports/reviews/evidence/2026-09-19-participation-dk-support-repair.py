"""Raw DK week is NULL: capture by exact draft group and assert its game dates.

The original empty week-filtered capture remains unchanged. Same time-travel cutoff.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from google.cloud import bigquery

OUT = Path('/home/erich/projects/review-evidence/overnight-20260918/participation-transfer-inputs')


def main():
    cutoff = datetime.fromisoformat(json.loads((OUT/'capture.json').read_text())['cutoff'])
    sql = '''SELECT pulled_at, season, week, draft_group_id, dk_player_id, dk_draftable_id,
        display_name, team_abbr, position, salary, status, game_start
        FROM `nfl-predictions-503414.nfl_raw.dk_salaries` FOR SYSTEM_TIME AS OF @cutoff
        WHERE season=2026 AND draft_group_id=153428 AND pulled_at<=@cutoff
        AND pulled_at=(SELECT MAX(pulled_at) FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
            FOR SYSTEM_TIME AS OF @cutoff WHERE season=2026 AND draft_group_id=153428 AND pulled_at<=@cutoff)'''
    c=bigquery.Client(project='nfl-predictions-503414')
    cfg=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000,query_parameters=[bigquery.ScalarQueryParameter('cutoff','TIMESTAMP',cutoff)])
    job=c.query(sql,job_config=cfg); fr=job.result().to_dataframe()
    assert len(fr)>0 and fr.dk_player_id.is_unique
    assert set(fr.game_start.dt.strftime('%Y-%m-%d'))=={'2026-09-20'}
    assert fr.game_start.min().hour==17 and fr.game_start.max().hour<=21
    path=OUT/'dk_salaries_by_group.parquet';assert not path.exists();fr.to_parquet(path,index=False)
    result=dict(cutoff=cutoff.isoformat(),sql=sql,job_id=job.job_id,bytes_processed=job.total_bytes_processed,
        rows=len(fr),path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        repair='raw DK week is NULL; exact draft group, season and asserted Sunday-main game times identify this slate',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (OUT/'dk-capture-repair.json').open('x') as f:json.dump(result,f,indent=2)
    print(fr.status.value_counts(dropna=False).to_dict(),fr.pulled_at.unique(),flush=True)


if __name__=='__main__':main()
