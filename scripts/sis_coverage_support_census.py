"""Outcome-free feasibility census for SIS defender coverage cells."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
Q=f'''
WITH x AS (
 SELECT season,week,defense,alignment,defender_player_id,coverage_snaps,targets,
   SAFE_DIVIDE(targets,SUM(targets) OVER(PARTITION BY season,week,defense,alignment)) AS target_share,
   SAFE_DIVIDE(coverage_snaps,SUM(coverage_snaps) OVER(PARTITION BY season,week,defense,alignment)) AS snap_share
 FROM `{settings.raw}.sis_receiver_copula_player_game`
), g AS (
 SELECT season,week,defense,alignment,COUNT(*) defenders,SUM(coverage_snaps) snaps,SUM(targets) targets,
   MAX(target_share) top_target_share,MAX(snap_share) top_snap_share,
   SUM(target_share*target_share) target_hhi,
   COUNTIF(coverage_snaps>=20) defenders_20_snaps,COUNTIF(targets>=3) defenders_3_targets
 FROM x GROUP BY season,week,defense,alignment
)
SELECT alignment,COUNT(*) cells,AVG(defenders) avg_defenders,
 APPROX_QUANTILES(defenders,100)[OFFSET(10)] p10_defenders,
 APPROX_QUANTILES(defenders,100)[OFFSET(50)] p50_defenders,
 APPROX_QUANTILES(defenders,100)[OFFSET(90)] p90_defenders,
 AVG(snaps) avg_snaps,AVG(targets) avg_targets,
 AVG(top_target_share) avg_top_target_share,AVG(target_hhi) avg_target_hhi,
 AVG(defenders_20_snaps) avg_defenders_20_snaps,AVG(defenders_3_targets) avg_defenders_3_targets,
 COUNTIF(defenders<3) cells_lt3,COUNTIF(targets<10) cells_lt10
FROM g GROUP BY alignment ORDER BY alignment'''
rows=query_df(Q).to_dict('records')
# Serialize numpy scalars through pandas-friendly conversion.
for row in rows:
 for k,v in list(row.items()):
  if hasattr(v,'item'): row[k]=v.item()
out=Path(__file__).resolve().parents[1]/'reports/reviews/evidence/2026-09-20-sis-coverage-support-census.json'
out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'source_table':'sis_receiver_copula_player_game','outcome_free':True,'rows':rows},indent=2,sort_keys=True)+'\n')
print(json.dumps(rows,indent=2))
