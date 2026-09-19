"""Read-only falsification of the research rule; no app mutation or outcomes."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

REPO = Path(__file__).resolve().parents[3]
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918')
OUT = ROOT / 'prop-event-identity-check'
TABLE = 'nfl-predictions-503414.nfl_raw.prop_lines'
MARKETS = "('player_pass_yds','player_pass_tds','player_rush_yds','player_reception_yds','player_receptions','player_anytime_td')"
GROUP = ['season', 'week', 'bookmaker', 'market', 'player']


def main():
    OUT.mkdir(exist_ok=False)
    sys.path.insert(0, str(REPO / 'src'))
    from nfl_dfs.models.prop_market import latest_pre_main_lock
    source = Path(__file__).with_name('2026-09-19-prop-snapshot-impact-v2.py')
    spec = importlib.util.spec_from_file_location('frozen_contrast', source)
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    c = bigquery.Client(project='nfl-predictions-503414')
    before = c.get_table(TABLE)
    queries = []

    def query(sql):
        j = c.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
        df = j.result(timeout=120).to_dataframe()
        queries.append(dict(sql=sql, job_id=j.job_id, bytes_processed=j.total_bytes_processed, rows=len(df)))
        return df

    base = f'''WITH g AS (
      SELECT season,week,bookmaker,market,player,COUNT(*) AS n_rows,
        COUNT(DISTINCT event_id) AS n_events
      FROM `{TABLE}` WHERE market IN {MARKETS}
      GROUP BY season,week,bookmaker,market,player)
    '''
    counts = query(base + '''SELECT season,COUNT(*) AS n_groups,
      COUNTIF(n_events>1) AS multi_event_groups,
      SUM(IF(n_events>1,n_rows,0)) AS affected_rows,MAX(n_events) AS max_events
      FROM g GROUP BY season ORDER BY season''')
    affected = query(base + f'''SELECT p.* FROM `{TABLE}` p JOIN g
      USING(season,week,bookmaker,market,player)
      WHERE g.n_events>1 ORDER BY season,week,player,snapshot_ts,event_id''')
    schedules = query('''SELECT season,week,gameday,gametime,game_type,weekday
      FROM `nfl-predictions-503414.nfl_raw.schedules`
      WHERE season=2026 AND week=1''')
    assert before.etag == c.get_table(TABLE).etag, 'source changed during census'
    assert len(affected) == 45 and affected.groupby(GROUP).ngroups == 2
    assert set(affected.season) == {2026} and set(affected.week) == {1}
    old, _ = latest_pre_main_lock(affected, schedules)
    proposed, _ = experiment.coherent(affected, schedules)
    assert len(old) == 2 and len(proposed) == 4
    details = []
    for name, frame in [('production', old), ('experimental', proposed)]:
        d = frame.copy()
        assert d.market.eq('player_anytime_td').all() and d.outcome_name.eq('Yes').all()
        price = d.price.astype(float)
        p = np.where(price > 0, 100 / (price + 100), -price / (-price + 100))
        d['td_component'] = 6 * (-np.log(1 - np.clip(p / 1.15, 1e-6, 1-1e-6)))
        details.append(dict(arm=name, rows=d[['player', 'event_id', 'snapshot_ts', 'price', 'td_component']].to_dict('records')))
        d.to_parquet(OUT / (name + '.parquet'), index=False)
    affected.to_parquet(OUT / 'affected-raw.parquet', index=False)
    schedules.to_parquet(OUT / 'schedules.parquet', index=False)

    # Separate synthetic counterexample: two event identifiers, same player/book,
    # sequential prelock prices. Preserve the frozen experimental function.
    fixture = pd.DataFrame([
        dict(season=2026, week=1, bookmaker='book', market='player_anytime_td',
             player='Synthetic', outcome_name='Yes', point=np.nan,
             event_id=e, snapshot_ts=t, price=p)
        for e, t, p in [('old-id','2026-09-10T14:00:00Z',550),
                        ('new-id','2026-09-12T14:00:00Z',340)]
    ])
    current_fixture, _ = latest_pre_main_lock(fixture, schedules)
    proposed_fixture, _ = experiment.coherent(fixture, schedules)
    assert len(current_fixture) == 1 and len(proposed_fixture) == 2
    result = dict(scope='Identity support and counterexample only; not a revised treatment or efficacy experiment',
        source_modified=str(before.modified), source_etag=before.etag,
        by_season=counts.to_dict('records'), retained=details,
        synthetic_production_rows=len(current_fixture), synthetic_experimental_rows=len(proposed_fixture),
        interpretation='Event-specific latest timestamps preserve superseded identities. Disjoint timestamps alone do not prove provider re-keying of the same scheduled game.',
        queries=queries, frozen_experiment_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        artifacts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.glob('*.parquet')})
    with (OUT/'result.json').open('x') as f:
        json.dump(result, f, indent=2, default=str, allow_nan=False)
    print(json.dumps(dict(by_season=result['by_season'], retained=details,
        synthetic_counterexample='CONFIRMED'), indent=2, default=str))


if __name__ == '__main__':
    main()
