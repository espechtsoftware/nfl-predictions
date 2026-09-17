import ast, pathlib, sys, json, tempfile, subprocess, csv, os
import numpy as np
import pandas as pd
prod=pathlib.Path(__file__).resolve().parents[3]
lab=pathlib.Path(os.environ.get('NFL2_REVIEW_REPO', '/home/erich/projects/nfl2'))
sys.path.insert(0,str(prod/'src'))
from nfl_dfs.models.prop_market import latest_pre_main_lock
rows=[]
for line,ts in [(49.5,'2026-09-20T09:00:00Z'),(59.5,'2026-09-20T16:00:00Z')]:
 for side in ('Over','Under'):
  rows.append(dict(season=2026,week=2,bookmaker='test',market='player_reception_yds',outcome_name=side,player='Synthetic Receiver',price=-110,point=line,snapshot_ts=ts))
sched=pd.DataFrame([dict(season=2026,week=2,gameday='2026-09-20',gametime='13:00',game_type='REG',weekday='Sunday')])
out,_=latest_pre_main_lock(pd.DataFrame(rows),sched)
print('PROP_LATEST retained lines:',sorted(out.point.unique().tolist()),'(latest should only be 59.5)')
# Extract pure validation/estimator helpers only. No reader entrypoint, provider access or real result data.
reader_source=subprocess.check_output(['git','-C',str(lab),'show','c06b2cd903a6de211c4d221b3ac56f710f715500:scripts/prereg099_report.py'],text=True)
tree=ast.parse(reader_source)
names={'_ratio','_preflight_runs','_validate_books','GateFailure'}
body=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in names]
ns=dict(np=np,pd=pd,re=__import__('re'),BANKS={990},RUN_PREFIXES={990:'119b990r1-'},FULL='F',CONTROL='C',ARMS=('A',))
exec(compile(ast.Module(body=body,type_ignores=[]),'<pure-reader-helpers>','exec'),ns)
try:ns['_preflight_runs'](['119b991r1-20260917T230652Z'])
except Exception as e:print('READER_991:',str(e))
q=ns['_ratio'](pd.DataFrame([dict(season=2021,week=1,bank=990,F_supply_ge240=0,C_supply_ge240=0)]),240,draws=10)
print('ZERO_DENOM result keys:',sorted(q))
try:print(q['slates_with_any_full'])
except KeyError as e:print('ZERO_PRIMARY formatting fails:',repr(e))
ns['_validate_books']({'A':[dict(season=2021,week=1,bank=990,rank=1,actual=0)]*80},pd.DataFrame([dict(season=2021,week=1,bank=990)]))
print('BOOK_VALIDATION accepted 80 duplicate rank-1 rows')
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp); ent=p/'enter';ent.mkdir();out=p/'out'
 contests=[dict(name='synthetic',contest_id='123',entries=2,keep=2)]
 (p/'contests.json').write_text(json.dumps(contests))
 slots=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST']
 with (p/'template.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['Entry ID','Contest Name','Contest ID','Entry Fee',*slots]);w.writerow(['fake-1','synthetic','123','0',*['OLD']*9]);w.writerow(['fake-2','synthetic','123','0',*['OLD']*9])
 with (ent/'ENTER-synthetic-123-2-entries-KEEP-first-2.csv').open('w') as f:
  w=csv.writer(f);w.writerow(slots);w.writerow([str(i) for i in range(9)])
 r=subprocess.run([sys.executable,str(prod/'scripts/fill_dk_entries.py'),str(p/'template.csv'),'--contests',str(p/'contests.json'),'--enter-dir',str(ent),'--out-dir',str(out)],capture_output=True,text=True)
 final=list(csv.reader((out/'DKEntries-FILLED-keepers-first.csv').open()))
 print('PARTIAL_FILL exit:',r.returncode,'second lineup untouched:',final[2][4:]==['OLD']*9)
 t=ast.parse((prod/'scripts/fill_dk_entries.py').read_text())
 for n in ast.walk(t):
  if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--out-dir':
   print('FILL_DEFAULT out-dir:',next(ast.literal_eval(k.value) for k in n.keywords if k.arg=='default'))
print('LATE_STATUS D->OUT new set:',{'player'}-{'player'})
