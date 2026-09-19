"""Stage only explicit authenticated study files for Cloud Build; no launch or outcome decoding."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

E=Path(__file__).resolve().parent
ROOT=E.parents[2]
IMAGE='us-central1-docker.pkg.dev/nfl-2-506823/lab/nfl2@sha256:39186bace6b243aa66a1ab9bcb83efd877f55caaa55a95992a8cf405ccea0076'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=Path(sys.argv[1]);assert not out.exists()
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    support=E/'2026-09-19-injury-type-support.json';s=json.loads(support.read_text())
    m=json.loads((E/'2026-09-19-zero-target-prior-current-support.json').read_text())
    paths={'study.py':E/'2026-09-19-injury-type-opportunity.py',
           'runner.py':E/'2026-09-19-injury-type-cloud.py','support.json':support,
           'bootstrap.py':E/'2026-09-19-injury-type-bootstrap.py',
           'wheels.json':E/'2026-09-19-injury-type-wheels.json',
           'safe.parquet':Path(s['safe_extract_path']),'labels.parquet':Path(m['path'])}
    wheels=json.loads(paths['wheels.json'].read_text())
    for name,rec in wheels['files'].items():
        p=Path('/home/erich/projects/review-evidence/overnight-20260918/injury-type-wheels')/name
        assert p.stat().st_size==rec['bytes'] and sha(p)==rec['sha256']
        paths['wheels/'+name]=p
    assert sha(paths['safe.parquet'])==s['safe_extract_sha256']
    assert sha(paths['labels.parquet'])==m['input']['sha256']
    out.mkdir(parents=True,exist_ok=False)
    for name,p in paths.items():
        (out/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out/name)
    context={'research_commit':commit,'files':{n:sha(out/n) for n in paths}}
    (out/'context.json').write_text(json.dumps(context,indent=2))
    for mode in ['smoke','forecast']:
        config={'steps':[{'name':IMAGE,'entrypoint':'python',
             'args':['-X','cpu_count=1','/workspace/bootstrap.py',mode],
             'env':['OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1',
                    'NUMEXPR_NUM_THREADS=1','BUILD_ID=$BUILD_ID']}],
             'timeout':'1800s','options':{'machineType':'E2_HIGHCPU_8'}}
        p=out.parent/f'{out.name}-{mode}-config.json';assert not p.exists()
        p.write_text(json.dumps(config,indent=2))
    print(json.dumps({'context':str(out),'context_sha256':sha(out/'context.json'),
        'research_commit':commit,'files':context['files'],'bytes':sum((out/n).stat().st_size for n in paths),
        'outcomes_decoded':False},indent=2))

if __name__=='__main__':main()
