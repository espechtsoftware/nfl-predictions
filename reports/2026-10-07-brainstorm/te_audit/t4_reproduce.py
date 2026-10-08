"""Task 4: reproduce the reviewer's history tables with the auditor's own panel and code.
'as reviewer' = schedule codes left raw (OAK/SD/STL), hindsight best-scorer definitions, season-to-date DK allowed (3+ games),
EPA per dropback allowed over the previous 6 games within season (3+ games). Then the same with team codes normalized."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from hist_lib import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
OUTR = ["TE1", "te_share", "te_boom", "WR1", "RB1", "QB", "te_beats_wr", "rbte_beats_wrwr", "qbte45", "qbwr45", "qbrbte60", "qbwrwr60"]
for panel in ("panel_rawcodes", "panel"):
    P = add_outcomes(prep(f"{panel}.parquet"), "max")
    base = P[(P.n_al >= 3) & P.qb_max.notna() & P.te1_max.notna() & P.wr1_max.notna() & P.rb1_max.notna()].copy()
    for variant in ("DK allowed to WRs (te_defense_study)", "EPA per dropback l6 (te_defense_epa)"):
        D = base.copy()
        if variant.startswith("EPA"):
            D = D[D.n_in6 >= 3].copy(); D["third"] = thirds(D, "epa_in6")
        else:
            D["third"] = thirds(D, "wr_al")
        H = D[D.season <= 2025].copy()
        print(f"\n######## {panel} | {variant} | history 2014-2025 team-games: {len(H):,}")
        raw, wit = third_tables(H, "third", OUTR)
        print("raw means by opponent third:"); print(raw.round(3).to_string())
        print("within offense-season:"); print(wit.round(3).to_string())
        if variant.startswith("EPA"):
            H2 = H.copy(); H2["wr_al"] = H2.epa_in6   # the reviewer put the EPA measure in column 1
        else:
            H2 = H
        reg, n = cont_reg(H2, ["wr_al", "te_al", "rb_al"], ["TE1", "te_share", "te_boom", "WR1", "RB1", "QB"], cluster="ds")
        print(f"regression (n={n}); column 1 = {'EPA l6' if variant.startswith('EPA') else 'DK allowed to WR'}:"); print(reg.to_string(index=False))
