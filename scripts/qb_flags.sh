#!/usr/bin/env bash
# Write the backup-QB flag table for the Sunday late-swap page (read-only BigQuery).
#   qb_flags.sh OUT_CSV [SEASON WEEK]
# Columns: qb_name, team, salary, proj, depth_rank, injury_status, practice_level,
#          starter_name, starter_proj, starter_injury_status, starter_practice_level, verdict
# A row is written for every QB whose feature depth_rank >= 2 and served proj >= 4.
# verdict: BEHIND-HEALTHY-STARTER (the lineup's QB is not expected to start),
#          STARTER-OUT (depth-1 is Out/IR: this backup may be the real starter -- confirm who),
#          STARTER-DOUBTFUL (may start -- confirm), STARTER-QUESTIONABLE, NO-DEPTH-1 (no depth-1 row).
# The page marks kept lineups whose QB appears here; the decision is the operator's.
set -euo pipefail
OUT=${1:?OUT_CSV}; SEASON=${2:-2026}; WEEK=${3:-2}
P=nfl-predictions-503414
bq query --project_id=$P --use_legacy_sql=false --format=csv --max_rows=500 --maximum_bytes_billed=2000000000 "
WITH proj AS (
  SELECT display_name, gsis_id, team, salary, proj_points
  FROM \`$P.nfl_predictions.player_projections\`
  WHERE season=$SEASON AND week=$WEEK AND position='QB'
    AND generated_at = (SELECT MAX(generated_at) FROM \`$P.nfl_predictions.player_projections\` WHERE season=$SEASON AND week=$WEEK)
),
inf AS (
  SELECT gsis_id, depth_rank, injury_status, practice_level
  FROM \`$P.nfl_features.player_week_inference\` WHERE season=$SEASON AND week=$WEEK AND position='QB'
),
q AS (SELECT p.*, i.depth_rank, i.injury_status, i.practice_level FROM proj p LEFT JOIN inf i USING (gsis_id)),
starter AS (
  SELECT team, display_name AS starter_name, proj_points AS starter_proj, injury_status AS starter_injury_status, practice_level AS starter_practice_level
  FROM q WHERE depth_rank = 1
  QUALIFY ROW_NUMBER() OVER (PARTITION BY team ORDER BY proj_points DESC) = 1
)
SELECT q.display_name AS qb_name, q.team, q.salary, ROUND(q.proj_points,2) AS proj, q.depth_rank,
       IFNULL(q.injury_status,'') AS injury_status, q.practice_level,
       IFNULL(s.starter_name,'') AS starter_name, ROUND(s.starter_proj,2) AS starter_proj,
       IFNULL(s.starter_injury_status,'') AS starter_injury_status, s.starter_practice_level,
       CASE WHEN s.starter_name IS NULL THEN 'NO-DEPTH-1'
            WHEN UPPER(IFNULL(s.starter_injury_status,'')) IN ('OUT','IR') THEN 'STARTER-OUT'
            WHEN UPPER(IFNULL(s.starter_injury_status,'')) = 'DOUBTFUL' THEN 'STARTER-DOUBTFUL'
            WHEN UPPER(IFNULL(s.starter_injury_status,'')) = 'QUESTIONABLE' THEN 'STARTER-QUESTIONABLE'
            ELSE 'BEHIND-HEALTHY-STARTER' END AS verdict
FROM q LEFT JOIN starter s USING (team)
WHERE q.depth_rank >= 2 AND q.proj_points >= 4
ORDER BY q.proj_points DESC" > "$OUT"
echo "$(($(wc -l < "$OUT") - 1)) backup QBs with proj >= 4 -> $OUT"
