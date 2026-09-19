"""Prepare a Cloud Build recipe using the already authenticated forecast source archive."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

E=Path(__file__).resolve().parent
IMAGE='us-central1-docker.pkg.dev/nfl-2-506823/lab/nfl2@sha256:39186bace6b243aa66a1ab9bcb83efd877f55caaa55a95992a8cf405ccea0076'
def main():
    target=Path(sys.argv[1]);assert not target.exists()
    payload={}
    for name,dest in [('2026-09-19-law-weight-read.py','reader.py'),('2026-09-19-law-weight-cloud-read.py','cloud-read.py')]:
        raw=(E/name).read_bytes()
        expected=subprocess.check_output(['git','show','d66a0273:reports/reviews/evidence/'+name],cwd=E.parents[2])
        assert raw==expected
        payload[dest]={'base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
    program=('import base64,hashlib,json,runpy\nfrom pathlib import Path\n'
             'payload=json.loads('+repr(json.dumps(payload))+')\n'
             'for name,rec in payload.items():\n'
             '    raw=base64.b64decode(rec["base64"]); assert hashlib.sha256(raw).hexdigest()==rec["sha256"]\n'
             '    p=Path("/workspace")/name; assert not p.exists(); p.write_bytes(raw)\n'
             'runpy.run_path("/workspace/cloud-read.py",run_name="__main__")\n')
    compile(program,'cloud-read-bootstrap','exec')
    config={'steps':[{'name':IMAGE,'entrypoint':'python','args':['-X','cpu_count=1','-c',program],
        'env':['OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','BUILD_ID=$BUILD_ID']}],
        'timeout':'1800s','options':{'machineType':'E2_HIGHCPU_8'}}
    target.write_text(json.dumps(config,indent=2))
    print(json.dumps({'config':str(target),'config_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'payloads':{k:v['sha256'] for k,v in payload.items()},'scope':'recipe only; no outcome read or launch'},indent=2))

if __name__=='__main__': main()
