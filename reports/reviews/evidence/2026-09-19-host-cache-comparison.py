"""Full keyed input comparison, including material drift in the baseline feature matrix."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from google.cloud import bigquery

P=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
host=P/'host-training.parquet'
assert hashlib.sha256(host.read_bytes()).hexdigest()=='8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7'
sys.path.insert(0,'/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/src')
from nfl2.core.featureset import NUMERIC_FEATURES
client=bigquery.Client(project='nfl-predictions-503414')
table='nfl-predictions-503414.nfl_features.player_week_training';before=client.get_table(table)
j=client.query(f'SELECT * FROM `{table}` WHERE season<=2025',job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
live=j.result(timeout=600).to_dataframe();after=client.get_table(table);assert before.etag==after.etag
raw=P/'fresh-historical-training.parquet';assert not raw.exists();live.to_parquet(raw,index=False)
a=pd.read_parquet(host);b=live;keys=['gsis_id','season','week'];assert not a.duplicated(keys).any() and not b.duplicated(keys).any()
a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index();assert a.index.equals(b.index) and set(a)==set(b)
any_change=np.zeros(len(a),bool);material=np.zeros(len(a),bool);model_material=np.zeros(len(a),bool);details=[]
for col in a:
    x,y=a[col],b[col];changed=~(x.eq(y).fillna(False)|(x.isna()&y.isna())).to_numpy(bool)
    if not changed.any():continue
    any_change|=changed;null=(x.isna()!=y.isna()).to_numpy(bool)
    numeric=pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y)
    if numeric:
        xx=x.to_numpy(float,na_value=np.nan);yy=y.to_numpy(float,na_value=np.nan);finite=np.isfinite(xx)&np.isfinite(yy)
        delta=np.abs(xx-yy);large=null|(finite&(delta>1e-6));maximum=float(delta[finite].max()) if finite.any() else None
    else:large=changed;maximum=None
    material|=large
    if col in NUMERIC_FEATURES or col in ['position','was_active']:model_material|=large
    details.append(dict(column=col,different_rows=int(changed.sum()),null_mismatches=int(null.sum()),
      max_abs_delta=maximum,material_rows=int(large.sum()),baseline_model_input_or_eligibility=col in NUMERIC_FEATURES or col in ['position','was_active']))
assert not any(d['column'] in ['salary','salary_delta_wow'] for d in details)
result=dict(rows=len(a),columns=len(a.columns)+3,keys_equal=True,host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),
    fresh_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),query_job=j.job_id,bytes_processed=j.total_bytes_processed,
    source_modified=before.modified.isoformat(),any_changed_rows=int(any_change.sum()),changed_players=int(a.index.get_level_values('gsis_id')[any_change].nunique()),
    material_definition='numeric absolute change>1e-6, any missingness change, or nonnumeric change; descriptive threshold, not an adoption gate',
    material_rows=int(material.sum()),baseline_input_or_eligibility_material_rows=int(model_material.sum()),
    per_column=details,salary_columns_rowwise_identical=True,
    scope='source input differences only; no lineup outcome or efficacy comparison')
with (P/'host-cache-comparison.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(result,indent=2),flush=True)
