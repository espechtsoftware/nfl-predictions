"""Head promotion preserves membership, premium set, risk eligibility and ties."""
import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('head_policy',Path(__file__).with_name('2026-09-19-first-delivered-promotion.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_only_eligible_prefix_row_moves_and_all_other_order_survives():
    book=list(range(97));clean=[True]*97;a=np.zeros((97,20),np.float32)
    a[3]=10;a[5]=100;clean[5]=False;a[35]=1000
    result,r=m.promote(book,clean,a)
    assert r['promoted_from_rank']==4 and result==[3,0,1,2,*range(4,97)]
    assert result[30:]==book[30:] and set(result[:30])==set(book[:30])


def test_exact_tie_keeps_first_eligible_delivered_row():
    book=[2,1,0];a=np.ones((3,20),np.float32)
    result,r=m.promote(book,[True]*3,a)
    assert result==book and r['promoted_from_rank']==1


def test_no_clean_row_does_not_infer_one():
    book=list(range(97));a=np.ones((97,20),np.float32)
    result,r=m.promote(book,[False]*97,a)
    assert result==book and r['no_eligible_clean_row']
