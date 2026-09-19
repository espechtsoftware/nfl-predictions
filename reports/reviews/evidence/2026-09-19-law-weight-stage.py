"""Stage exact committed forecast source and authenticated benchmark bytes for Cloud Build."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
E=Path(__file__).resolve().parent
PROD=E.parents[2]
IMAGE='us-central1-docker.pkg.dev/nfl-2-506823/lab/nfl2@sha256:39186bace6b243aa66a1ab9bcb83efd877f55caaa55a95992a8cf405ccea0076'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    dest=Path(sys.argv[1]);dest.mkdir(parents=True,exist_ok=False)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=PROD,text=True).strip()
    research=subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROD,text=True).strip()
    labcommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=LAB,text=True).strip()
    assert labcommit=='2dc116ce95647a776ba9c36cf194f44d022d03a4'
    files={}
    for name in subprocess.check_output(['git','ls-files','src'],cwd=LAB,text=True).splitlines():
        if not name.endswith('.py'): continue
        body=subprocess.check_output(['git','show',labcommit+':'+name],cwd=LAB)
        p=dest/'lab'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
        files[name]=sha(p)
    (dest/'source-contract.json').write_text(json.dumps({'commit':labcommit,'files':files},indent=2))
    for old,new in [('2026-09-19-law-weight-forecast.py','forecast.py'),('2026-09-19-law-weight-cloud.py','cloud.py')]:
        shutil.copyfile(E/old,dest/new)
    support=json.loads((E/'2026-09-19-law-weight-support.json').read_text())
    for rec in support['files']:
        source=Path(rec['path']);assert sha(source)==rec['sha256']
        rel=rec['uri'].split('/benchmark/',1)[1]
        p=dest/'cache'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)
        rec['path']=str(Path('/workspace/cache')/rel)
    (dest/'support-cloud.json').write_text(json.dumps(support,indent=2))
    context={'lab_commit':labcommit,'research_commit':research,'base_image':IMAGE,
             'files':{str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}}
    (dest/'context.json').write_text(json.dumps(context,indent=2))
    for mode,seconds in [('smoke',600),('forecast',3600)]:
        config={'steps':[{'name':IMAGE,'entrypoint':'python','args':['-X','cpu_count=1','/workspace/cloud.py',mode],
                         'env':['OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','BUILD_ID=$BUILD_ID']}],
                'timeout':f'{seconds}s','options':{'machineType':'E2_HIGHCPU_8'}}
        (dest/(mode+'.json')).write_text(json.dumps(config,indent=2))
    print(json.dumps({'path':str(dest),'context_sha256':sha(dest/'context.json'),'research_commit':research,
                       'lab_source_files':len(files),'total_bytes':sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())},indent=2))

if __name__=='__main__': main()
