"""Read the completed four fits; exact constant detection fixes float32 std drift."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
P=ROOT/'cache-order-decomposition'
NAMES=['host_values_host_order','fresh_values_fresh_order','fresh_values_host_order','host_values_fresh_order']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert (P/'result.json').exists(),'original failed partial JSON must be retained'
    banks={n:np.load(P/(n+'-bank.npy'),allow_pickle=False) for n in NAMES}
    pred={n:pd.read_parquet(P/(n+'-components.parquet')).to_numpy(float) for n in NAMES}
    for n in NAMES:assert banks[n].shape==(428,10000) and np.isfinite(banks[n]).all() and np.isfinite(pred[n]).all()
    for mode in ['host','fresh']:
        r=json.loads((ROOT/('live-cli-'+mode+'-proof.json')).read_text())
        original=Path(r['run'])/'incumbent_player_scores.npy'
        assert np.array_equal(banks[mode+'_values_'+mode+'_order'],np.load(original,allow_pickle=False))
    contrasts={}
    pairs=[('fresh_values_host_order','host_values_host_order'),('fresh_values_fresh_order','host_values_fresh_order'),
           ('host_values_fresh_order','host_values_host_order'),('fresh_values_fresh_order','fresh_values_host_order')]
    for a,b in pairs:
        x,y=banks[a],banks[b]
        # Exact constant rows can have nonzero np.std(float32) from rounded mean
        # reduction. ptp identifies constant persisted rows; covariance is float64.
        mask=(np.ptp(x,axis=1)>0)&(np.ptp(y,axis=1)>0)
        cx,cy=np.corrcoef(x[mask].astype(float)),np.corrcoef(y[mask].astype(float))
        assert np.isfinite(cx).all() and np.isfinite(cy).all()
        tri=np.triu_indices(len(cx),1)
        contrasts[a+'-minus-'+b]=dict(changed_components=int(np.count_nonzero(pred[a]!=pred[b])),
          component_max_absolute_difference=float(abs(pred[a]-pred[b]).max()),
          different_bank_cells=int(np.count_nonzero(x!=y)),max_absolute_cell_difference=float(abs(x-y).max()),
          per_player_multisets_equal=np.array_equal(np.sort(x,axis=1),np.sort(y,axis=1)),
          common_nonconstant_players=int(mask.sum()),correlation_pairs=len(tri[0]),
          mean_absolute_correlation_difference=float(abs(cx-cy)[tri].mean()))
    result=dict(actual_cli_replays_exact=True,contrasts=contrasts,
      artifacts={n:{suffix:sha(P/(n+'-'+suffix)) for suffix in ['components.parquet','bank.npy']} for n in NAMES},
      reader_sha256=sha(Path(__file__)),producer_sha256=sha(Path(__file__).with_name('2026-09-19-cache-order-decomposition.py')),
      diagnostic_repair='All four frozen fits completed. Original reader selected some constant rows because float32 std reduction was nonzero, causing NaN correlation and failed JSON. Read-only repair uses exact range for constant detection and float64 covariance; no refit or changed contrast.',
      scope='Post-proof engineering factorial of cache values/order; no current NFL labels, candidate solves, performance scores or cache adoption')
    with (P/'result-repaired.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
