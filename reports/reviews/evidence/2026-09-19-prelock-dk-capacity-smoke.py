"""Synthetic capacity only: two complete full-dose ordinary selector passes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import time
import numpy as np

HERE=Path(__file__).parent
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/prelock-dk-capacity-smoke')
SOURCE=HERE/'2026-09-19-prelock-dk-reselect.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert sha(SOURCE)=='a2a240aa4a44d15bc8f973246722dc986978ceda9a8af69dccd3420d7f6c82cf'
    ROOT.mkdir(exist_ok=False);start=time.monotonic()
    spec=importlib.util.spec_from_file_location('capacity_selector',SOURCE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # This deliberately exceeds the current 12,560 attempt cap. Values and
    # rows are synthetic: no roster, performance or full-run identity claim.
    a=np.random.default_rng(20260919057).random((12800,20000),dtype=np.float32)
    created=time.monotonic();first=m.base.greedy(a,97);middle=time.monotonic()
    second=m.base.greedy(a,97);finished=time.monotonic()
    assert first==second and len(first)==len(set(first))==97
    result=dict(synthetic_only=True,shape=list(a.shape),entries=97,
        setup_seconds=created-start,first_pass_seconds=middle-created,second_pass_seconds=finished-middle,
        total_seconds=finished-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        exact_repeat=True,selector_sha256=sha(SOURCE),helper_sha256=sha(m.HELPER),producer_sha256=sha(__file__),
        scope='Two 12,800-candidate by 20,000-world selector passes; excludes provider/network delays, complete file ingestion and delivery. Not an actual full-corpus run or scoring test.')
    with (ROOT/'result.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
