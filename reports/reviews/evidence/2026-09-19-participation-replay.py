"""Portable exact numeric replay of the frozen transfer, without warehouse access.

Usage: this_file.py EXTRACTED_BUNDLE LAB_CHECKOUT PRODUCTION_CHECKOUT OUTPUT_DIR
Only artifact path representation changes. Every bundled byte is authenticated.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    root,lab,prod,out=map(lambda x:Path(x).resolve(),sys.argv[1:])
    manifest=json.loads((root/'manifest.json').read_text())
    for row in manifest['files']:
        p=root/row['relative_path'];assert p.stat().st_size==row['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],p
    source=root/manifest['source_relative_path']
    spec=importlib.util.spec_from_file_location('frozen_participation_transfer',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    def mapped(value):
        p=Path(value)
        if p.is_absolute() and not p.is_relative_to(root):
            alt=root/'files'/str(p).lstrip('/')
            if alt.exists():return alt
        return p
    # Content identity is unchanged; absolute laptop file paths are transport metadata.
    m.Path=mapped;m.BASE=mapped(m.BASE);m.INPUT=mapped(m.INPUT);m.SUPPORT=mapped(m.SUPPORT)
    m.LAB=lab;m.OUT=out
    sys.path[:0]=[str(prod/'src'),str(lab/'src')]
    state=m.inputs();m.main(state)
    original=json.loads((root/manifest['result_relative_path']).read_text())
    actual=json.loads((out/'result.json').read_text())
    compared=['candidate_count','excluded_players','map_records','selection_seed','audit_seed',
        'masks','books','shared_members','exposures','expected_inactive_contamination','first_rosters','metrics','contrasts']
    assert all(actual[k]==original[k] for k in compared)
    for arm in original['vetting']:
        for k in ('indices','first_source_rank','hard','material','order_source_ranks'):
            assert actual['vetting'][arm][k]==original['vetting'][arm][k]
    print('EXACT_FROZEN_NUMERIC_AND_DELIVERY_REPLAY_PASS',compared,flush=True)


if __name__=='__main__':main()
