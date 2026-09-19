"""Install only hash-pinned wheels into an isolated Cloud Build directory, then exec."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path('/workspace')
context=json.loads((root/'context.json').read_text())
for name,digest in context['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
manifest=json.loads((root/'wheels.json').read_text())
paths=[]
for name,rec in manifest['files'].items():
    assert Path(name).name==name and name.endswith('.whl')
    p=root/'wheels'/name
    assert p.stat().st_size==rec['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256']
    paths.append(str(p))
target=root/'vendor';assert not target.exists()
subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',
    '--no-index','--no-deps','--target',str(target),*paths],check=True)
os.environ['PYTHONPATH']=str(target)+((':'+os.environ['PYTHONPATH']) if os.environ.get('PYTHONPATH') else '')
os.execv(sys.executable,[sys.executable,'-X','cpu_count=1',str(root/'runner.py'),sys.argv[1]])
