"""Authenticate and compare benchmark versus archived-frame game inputs; no scores."""
import hashlib,json,subprocess
from pathlib import Path
import pandas as pd
R=Path('reports/reviews/evidence')
OUT=R/'2026-09-19-hsim-schedule-input-census.json'
assert not OUT.exists()
frpath=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay/frame.parquet')
schpath=Path('/home/erich/.cache/nfl2/v0/warehouse/raw_schedules/000000000000.parquet')
assert hashlib.sha256(frpath.read_bytes()).hexdigest()=='90a762654111126aefad1950217044443291251918ab70edb925ff341d226635'
assert hashlib.sha256(schpath.read_bytes()).hexdigest()=='d80725d03695a33c5f67bf655fc059b09109b201fb79c76bb0d8562b1e9da1ad'
f=pd.read_parquet(frpath,columns=['id','team','game_id','game_total','spread'])
assert f.groupby('team')[['game_id','game_total','spread']].nunique().max().max()==1
s=pd.read_parquet(schpath,columns=['season','week','game_id','home_team','away_team','total_line','spread_line'])
s=s[(s.season==2026)&(s.week==2)]
x=f.drop_duplicates('team').merge(s,on='game_id',validate='many_to_one')
assert len(x)==f.team.nunique()==26 and x.game_id.nunique()==13
x['benchmark_team_spread']=x.spread_line.where(x.team==x.home_team,-x.spread_line)
x['total_difference']=x.game_total-x.total_line
x['spread_difference']=x.spread-x.benchmark_team_spread
out=dict(frame_sha256=hashlib.sha256(frpath.read_bytes()).hexdigest(),schedule_sha256=hashlib.sha256(schpath.read_bytes()).hexdigest(),
    teams=len(x),games=x.game_id.nunique(),teams_different_total=int((x.total_difference.abs()>1e-8).sum()),
    games_different_total=x.loc[x.total_difference.abs()>1e-8,'game_id'].nunique(),
    teams_different_spread=int((x.spread_difference.abs()>1e-8).sum()),
    games_different_spread=x.loc[x.spread_difference.abs()>1e-8,'game_id'].nunique(),
    rows=json.loads(x.to_json(orient='records')),
    scope='Pre-lock snapshot/source-path comparison only; archived live-frame versus frozen benchmark inputs.',
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
with OUT.open('x') as h:json.dump(out,h,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
