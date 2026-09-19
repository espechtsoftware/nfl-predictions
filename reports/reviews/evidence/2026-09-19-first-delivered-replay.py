"""Replay the head diagnostic from the verified host bundle plus small add-on.

Usage: script.py HOST_BUNDLE HEAD_ADDON CLEAN_LAB PROD_CHECKOUT NEW_OUTPUT
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root,addon,lab,prod,out=[Path(x).resolve() for x in sys.argv[1:]]
    base=json.loads((root/'manifest.json').read_text());extra=json.loads((addon/'manifest.json').read_text())
    for directory,manifest in [(root,base),(addon,extra)]:
        for r in manifest['files']:
            p=directory/r['path'];assert p.is_relative_to(directory) and p.stat().st_size==r['bytes']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    stage=out.with_name(out.name+'-inputs');assert not out.exists() and not stage.exists()
    shutil.copytree(root,stage)
    for r in extra['files']:
        p=stage/r['path'];assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(addon/r['path'],p)
    source=stage/extra['source'];spec=importlib.util.spec_from_file_location('head_reader_frozen',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    def mapped(value):
        p=Path(value)
        if p.is_absolute() and not p.is_relative_to(stage):
            q=stage/'files'/str(p).lstrip('/')
            if q.exists():return q
        return p
    oldlab=m.LAB
    for module in (m,m.h):
        module.Path=mapped
        for key in ('ROOT','RELEASE','MANIFEST','LAB','OUT'):
            if hasattr(module,key):setattr(module,key,mapped(getattr(module,key)))
    m.OUT=out
    load=m.h.load
    def adapted(name):
        module=load(name)
        if name=='2026-09-19-participation-transfer.py':
            module.Path=mapped
            for key in ('BASE','INPUT','SUPPORT','OUT'):setattr(module,key,mapped(getattr(module,key)))
            module.LAB=lab
        return module
    m.h.load=adapted
    sys.path[:0]=[str(prod/'src'),str(lab/'src')]
    import nfl2
    assert Path(nfl2.__file__).resolve().is_relative_to(lab/'src')
    assert subprocess.check_output(['git','-C',str(lab),'rev-parse','HEAD'],text=True).strip()==base['lab_sha']
    check=subprocess.check_output
    def translated(args,*a,**kw):
        args=list(args)
        if args[:2]==['git','-C'] and args[2] in (str(oldlab),str(m.LAB)):args[2]=str(lab)
        return check(args,*a,**kw)
    subprocess.check_output=translated
    try:m.main()
    finally:subprocess.check_output=check
    expected=json.loads((addon/extra['result']).read_text());actual=json.loads((out/'result.json').read_text())
    fields=['books','decisions','metrics','contrasts','audit_masks','membership_unchanged',
        'prefix30_and_all_later_regions_exact','original_selection_banks_exact']
    assert all(expected[k]==actual[k] for k in fields)
    for k in expected['audit_identity']:assert expected['audit_identity'][k]['sha256']==actual['audit_identity'][k]['sha256']
    print('EXACT_HEAD_POLICY_SELECTION_AND_FRESH_AUDIT_REPLAY_PASS',flush=True)


if __name__=='__main__':main()
