"""Outcome-blind roster support census for a possible later, separately frozen study."""
import hashlib
import json
from pathlib import Path
import pandas as pd

E = Path(__file__).resolve().parent
SAFE = Path('/home/erich/projects/review-evidence/overnight-20260918/historical-candidate-safe.parquet')
COLUMNS = ['season', 'week', 'players', 'cand_ix', 'salary']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    assert sha(SAFE) == 'd29f26c056735ac5562be7e85830af977780878e8eb92fb580feabb44f299fe8'
    candidates = pd.read_parquet(SAFE, columns=COLUMNS)
    support = json.loads((E/'2026-09-19-law-weight-support.json').read_text())
    source = next(x for x in support['files'] if '/snap_pitclean_k1/' in x['uri'])
    assert sha(source['path']) == source['sha256']
    cols = ['season', 'week', 'id', 'pos', 'game_id', 'salary']
    frame = pd.read_parquet(source['path'], columns=cols)
    expected = {(x['season'], x['week']) for x in support['slates']}
    assert set(candidates.groupby(['season', 'week']).groups) == expected
    assert not candidates.duplicated(['season', 'week', 'cand_ix']).any()
    records = []
    for (season, week), rows in candidates.groupby(['season', 'week'], sort=True):
        fr = frame[(frame.season == season) & (frame.week == week)].set_index('id')
        assert fr.index.is_unique
        seen = set(); bad = []; salary_mismatch = 0
        for row in rows.itertuples(index=False):
            ids = str(row.players).split(',')
            reason = None
            if len(ids) != 9 or len(set(ids)) != 9: reason = 'not_nine_distinct_players'
            elif not set(ids) <= set(fr.index): reason = 'unmapped_id'
            else:
                sub = fr.loc[ids]; counts = sub.pos.value_counts().to_dict()
                salary = float(sub.salary.sum())
                if (counts.get('QB', 0) != 1 or counts.get('DST', 0) != 1 or
                    not 2 <= counts.get('RB', 0) <= 3 or not 3 <= counts.get('WR', 0) <= 4 or
                    not 1 <= counts.get('TE', 0) <= 2 or set(counts) != {'QB','RB','WR','TE','DST'}):
                    reason = 'position_counts'
                elif salary > 50000 or salary <= 0: reason = 'salary'
                elif sub.game_id.nunique() < 2: reason = 'games'
                if salary != float(row.salary): salary_mismatch += 1
            if reason: bad.append({'cand_ix':int(row.cand_ix),'reason':reason})
            seen.add(tuple(sorted(ids)))
        records.append({'season':int(season),'week':int(week),'candidates':len(rows),
                        'distinct_rosters':len(seen),'invalid':bad,'salary_mismatches':salary_mismatch})
    result = {'scope':'Support census only; old K1 panel, not adopted D800; no efficacy read',
              'candidate_uri':'gs://nfl-2-506823-lab/benchmark/v1/panel107/cands_pitclean_k1/000000000000.parquet',
              'candidate_generation':'1787937215335871','candidate_bytes':31627972,
              'candidate_crc32c':'z1nFlA==','safe_extract_sha256':sha(SAFE),
              'candidate_columns_read':COLUMNS,'frame_columns_read':cols,'frame_sha256':source['sha256'],
              'outcomes_read':False,'slates':records,
              'totals':{'slates':len(records),'candidates':len(candidates),
                        'distinct_rosters':sum(x['distinct_rosters'] for x in records),
                        'invalid':sum(len(x['invalid']) for x in records),
                        'salary_mismatches':sum(x['salary_mismatches'] for x in records)}}
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__ == '__main__': main()
