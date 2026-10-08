"""Task 4b: the reviewer's continuous stack-sum regressions (QB+TE, QB+WR, QB+RB+TE, QB+WR+WR), raw codes (as reviewer) and normalized."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from hist_lib import *
pd.set_option("display.width", 250)
for panel in ("panel_rawcodes", "panel"):
    P = add_outcomes(prep(f"{panel}.parquet"), "max")
    P["qb_te"] = P.QB + P.TE1; P["qb_wr"] = P.QB + P.WR1; P["qb_rb_te"] = P.QB + P.RB1 + P.TE1; P["qb_wr_wr"] = P.QB + P.WR1 + P.WR2
    base = P[(P.n_al >= 3) & P.qb_max.notna() & P.te1_max.notna() & P.wr1_max.notna() & P.rb1_max.notna() & (P.season <= 2025)].copy()
    for lab, D in (("DK allowed (col 1 = WR allowed)", base), ("EPA (col 1 = EPA l6)", base[base.n_in6 >= 3].assign(wr_al=lambda x: x.epa_in6))):
        reg, n = cont_reg(D, ["wr_al", "te_al", "rb_al"], ["qb_te", "qb_wr", "qb_rb_te", "qb_wr_wr"])
        print(f"--- {panel} | {lab} | n={n}"); print(reg.to_string(index=False))
