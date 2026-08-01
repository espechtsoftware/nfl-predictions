-- Offensive-line injuries (2026-08-01): the public prices skill-player
-- injuries; pass-protection losses (LT/C/RT out) change sack rate, time
-- to throw, and depth of target for EVERY skill player on the team.
-- Same point-in-time discipline as 018: the week-W injury report is
-- pre-game knowledge.
CREATE OR REPLACE TABLE `${features}.team_week_ol_out` AS
SELECT
  team, season, week,
  COUNTIF(position IN ('T', 'G', 'C')) AS team_ol_out
FROM `${raw}.injuries`
WHERE report_status = 'Out'
GROUP BY team, season, week;
