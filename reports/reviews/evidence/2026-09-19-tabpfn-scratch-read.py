"""Frozen cache support/parity/influence reader; no current outcome tables."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

PROJECT = 'nfl-predictions-503414'
ROOT = Path(__file__).parent
OUT = ROOT / '2026-09-19-tabpfn-scratch-read.json'
LOCAL = Path('/home/erich/projects/review-evidence/overnight-20260918/tabpfn-cache-results')
KEYS = ['season', 'week', 'gsis_id']
QCOLS = ['q01','q05','q10','q20','q30','q40','q50','q60','q70','q80','q90','q95','q99']
VALUES = ['mean', *QCOLS]


def main():
    assert not OUT.exists() and not LOCAL.exists()
    LOCAL.mkdir()
    client = bigquery.Client(project=PROJECT)
    frames, receipts = {}, {}
    for arm in ('control', 'salaryfix'):
        table = f'{PROJECT}.nfl_features_{arm}.tabpfn_projections'
        before = client.get_table(table)
        j = client.query(f'SELECT {",".join(KEYS+VALUES)} FROM `{table}` ORDER BY season,week,gsis_id',
                         job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
        df = j.result(timeout=300).to_dataframe()
        after = client.get_table(table)
        assert (before.etag,before.modified,before.num_rows)==(after.etag,after.modified,after.num_rows)
        assert len(df) and not df[KEYS].isna().any().any() and not df.duplicated(KEYS).any()
        assert np.isfinite(df[VALUES].to_numpy(float)).all()
        assert not (np.diff(df[QCOLS].to_numpy(float),axis=1)<-1e-8).any()
        target = df[df.season.eq(2026)&df.week.eq(2)]
        assert len(target)==target.gsis_id.nunique()==877
        assert hashlib.sha256(json.dumps(sorted(target.gsis_id.astype(str)),separators=(',',':')).encode()).hexdigest()=='625317ad1854b0221ef2a86ae87e561bea4cdec6b2965d605ea90ca26e317eff'
        path=LOCAL/(arm+'.parquet');df.to_parquet(path,index=False)
        frames[arm]=df.set_index(KEYS)
        receipts[arm]=dict(table=table,rows=len(df),target_rows=len(target),etag=before.etag,
                           modified=before.modified.isoformat(),job_id=j.job_id,bytes_processed=j.total_bytes_processed,
                           file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),path=str(path))
    a,b=frames['control'],frames['salaryfix']
    assert a.index.equals(b.index),'cache target keysets differ'
    historical=np.asarray(a.index.get_level_values('season')<2026)
    diff=b[VALUES].to_numpy(float)-a[VALUES].to_numpy(float)
    hist=diff[historical];current=diff[~historical]
    def summaries(delta):
        return {col:dict(mean_signed=float(delta[:,i].mean()),mean_absolute=float(np.abs(delta[:,i]).mean()),
                         max_absolute=float(np.abs(delta[:,i]).max()),changed_rows=int((delta[:,i]!=0).sum()))
                for i,col in enumerate(VALUES)}
    result=dict(receipts=receipts,all_support_checks_pass=True,historical_rows=int(historical.sum()),
                historical_exact_equal=bool((hist==0).all()),historical_differences=summaries(hist),
                upcoming_differences=summaries(current),scope='cache influence; no outcome read or efficacy claim')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
