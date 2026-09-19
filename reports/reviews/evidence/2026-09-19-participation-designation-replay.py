"""Exact external replay; only paths are translated, all artifact bytes checked.

Usage: this.py BUNDLE_ROOT CLEAN_LAB_CHECKOUT PRODUCTION_CHECKOUT NEW_OUTPUT
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    root,lab,prod,out=[Path(x).resolve() for x in sys.argv[1:]]
    manifest=json.loads((root/'manifest.json').read_text())
    assert not out.exists()
    for row in manifest['files']:
        p=root/row['relative_path'];assert p.is_relative_to(root)
        assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    source=root/manifest['source_relative_path']
    spec=importlib.util.spec_from_file_location('designation_frozen_reader',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    def mapped(value):
        p=Path(value)
        if p.is_absolute() and not p.is_relative_to(root):
            alt=root/'files'/str(p).lstrip('/')
            if alt.exists():return alt
        return p
    m.base.Path=mapped
    for key in ('BASE','INPUT','SUPPORT','OUT'):setattr(m.base,key,mapped(getattr(m.base,key)))
    m.base.LAB=lab;m.OUT=out
    sys.path[:0]=[str(prod/'src'),str(lab/'src')]
    from google.cloud import bigquery
    def forbidden(*args,**kwargs):raise RuntimeError('provider query forbidden during replay')
    bigquery.Client.query=forbidden
    m.main()
    original=json.loads((root/manifest['result_relative_path']).read_text())
    actual=json.loads((out/'result.json').read_text())
    fields=['candidate_count','entries','books','map_records','selection_masks','audit_masks',
        'metrics','contrasts','exposures','source_control_and_full_exact','all_books_legal']
    assert all(original[k]==actual[k] for k in fields)
    for arm in original['delivery']:
        for k in ('indices','first_source_rank','hard','material','order_source_ranks'):
            assert original['delivery'][arm][k]==actual['delivery'][arm][k]
    print('EXACT_DESIGNATION_NUMERICS_AND_DELIVERY_REPLAY_PASS',fields,flush=True)


if __name__=='__main__':main()
