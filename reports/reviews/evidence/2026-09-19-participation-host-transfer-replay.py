"""Replay authenticated host-transfer bytes with path translation only.

Usage: script.py BUNDLE_ROOT CLEAN_LAB_CHECKOUT PRODUCTION_CHECKOUT NEW_OUTPUT
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def main():
    root,lab,prod,out=[Path(x).resolve() for x in sys.argv[1:]]
    manifest=json.loads((root/'manifest.json').read_text());assert not out.exists()
    for r in manifest['files']:
        p=root/r['path'];assert p.is_relative_to(root) and p.stat().st_size==r['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    assert subprocess.check_output(['git','-C',str(lab),'rev-parse','HEAD'],text=True).strip()==manifest['lab_sha']
    assert not subprocess.check_output(['git','-C',str(lab),'status','--porcelain','--untracked-files=all'],text=True).strip()
    def mapped(value):
        p=Path(value)
        if p.is_absolute() and not p.is_relative_to(root):
            q=root/'files'/str(p).lstrip('/')
            if q.exists():return q
        return p
    source=root/manifest['source'];spec=importlib.util.spec_from_file_location('host_transfer_frozen',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    oldlab=m.LAB
    for key in ('ROOT','RELEASE','MANIFEST','LAB'):setattr(m,key,mapped(getattr(m,key)))
    m.OUT=out;m.Path=mapped
    original_load=m.load
    def load(name):
        module=original_load(name)
        if name=='2026-09-19-participation-transfer.py':
            module.Path=mapped
            for key in ('BASE','INPUT','SUPPORT','OUT'):setattr(module,key,mapped(getattr(module,key)))
            module.LAB=lab
        return module
    m.load=load
    sys.path[:0]=[str(prod/'src'),str(lab/'src')]
    import nfl2
    assert Path(nfl2.__file__).resolve().is_relative_to(lab/'src')
    original_check=subprocess.check_output
    def check(args,*a,**kw):
        args=list(args)
        if args[:2]==['git','-C'] and args[2] in (str(oldlab),str(m.LAB)):args[2]=str(lab)
        return original_check(args,*a,**kw)
    subprocess.check_output=check
    try:m.main('run')
    finally:subprocess.check_output=original_check
    original=json.loads((root/manifest['result']).read_text());actual=json.loads((out/'result.json').read_text())
    fields=['actual_host_selection_banks_exact','actual_host_d160_control_exact','all1600_candidates_legal',
        'source_projection','books','metrics','contrasts','map_records','selection_masks','audit_masks',
        'shared_members','first_same','exposures']
    assert all(original[k]==actual[k] for k in fields)
    for arm in original['delivery']:
        for k in ('indices','first_source_rank','hard','material','order_source_ranks'):
            assert original['delivery'][arm][k]==actual['delivery'][arm][k]
    for k in original['audit_identity']:
        assert original['audit_identity'][k]['sha256']==actual['audit_identity'][k]['sha256']
    print('EXACT_ACTUAL_HOST_BANKS_SELECTION_DELIVERY_AND_AUDIT_REPLAY_PASS',flush=True)


if __name__=='__main__':main()
