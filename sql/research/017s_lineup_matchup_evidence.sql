-- Lineup-level matchup evidence over the realized research corpus (v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py AFTER 017r. Joins every
-- research-eligible replay candidate (the 107-slate realized corpus with
-- actual scores) to the all-week player matchup table and aggregates to
-- one row per candidate: the modeling/selection feed that finally lets
-- winner-style characteristics and corpus tail labels meet game-context
-- features.
--
-- Outcome discipline: `actual_score` and its threshold indicators are
-- TRAINING/EVALUATION labels for walk-forward research on these
-- already-viewed slates (exploratory tier). They are never live features;
-- any nominated strategy still passes the preregistered held-out and
-- prospective gates before production.

CREATE OR REPLACE TABLE `${features}.lineup_matchup_evidence` AS
WITH candidates AS (
  SELECT
    panel_run_id,
    season,
    week,
    cand_ix,
    tag,
    all_tags,
    selected,
    selected_rank,
    salary,
    p_line,
    sim_mean,
    sim_q90,
    sim_q99,
    tail_line,
    actual_score,
    players
  FROM `${predictions}.replay_candidates`
  WHERE research_eligible
),
exploded AS (
  SELECT
    c.panel_run_id,
    c.season,
    c.week,
    c.cand_ix,
    player_id
  FROM candidates c,
  UNNEST(SPLIT(c.players, ',')) AS player_id
  WHERE player_id NOT LIKE 'DST_%'
),
joined AS (
  SELECT
    e.panel_run_id,
    e.season,
    e.week,
    e.cand_ix,
    e.player_id,
    m.family,
    m.role_label,
    m.matchup_edge_score,
    m.easy_matchup,
    m.component_count,
    m.qb_depth1
  FROM exploded e
  LEFT JOIN `${features}.player_matchup_week_pit` m
    ON m.season = e.season AND m.week = e.week AND m.gsis_id = e.player_id
),
aggregated AS (
  SELECT
    panel_run_id,
    season,
    week,
    cand_ix,
    COUNT(*) AS skill_player_count,
    COUNTIF(family IS NOT NULL) AS matchup_matched_count,
    COUNTIF(matchup_edge_score IS NOT NULL) AS matchup_supported_count,
    COUNTIF(family = 'receiver') AS receiver_count,
    COUNTIF(family = 'receiver' AND matchup_edge_score IS NOT NULL)
      AS receiver_supported_count,
    AVG(IF(family = 'receiver', matchup_edge_score, NULL))
      AS receiver_edge_mean,
    MAX(IF(family = 'receiver', matchup_edge_score, NULL))
      AS receiver_edge_max,
    COUNTIF(family = 'receiver' AND easy_matchup)
      AS receiver_easy_count,
    COUNTIF(
      family = 'receiver' AND easy_matchup AND role_label = 'WR1'
    ) AS wr1_easy_count,
    AVG(IF(family = 'rb', matchup_edge_score, NULL)) AS rb_edge_mean,
    MAX(IF(family = 'rb', matchup_edge_score, NULL)) AS rb_edge_max,
    COUNTIF(family = 'rb' AND easy_matchup) AS rb_easy_count,
    COUNTIF(
      family = 'rb' AND easy_matchup AND role_label = 'RB1'
    ) AS rb1_easy_count,
    -- One QB per legal lineup; starter-gate with the depth flag where it
    -- exists (through 2024), otherwise carry the ungated edge.
    MAX(IF(
      family = 'qb' AND COALESCE(qb_depth1, TRUE),
      matchup_edge_score, NULL
    )) AS qb_edge,
    LOGICAL_OR(
      family = 'qb' AND COALESCE(qb_depth1, TRUE)
      AND easy_matchup
    ) AS qb_easy,
    AVG(matchup_edge_score) AS lineup_edge_mean,
    MAX(matchup_edge_score) AS lineup_edge_max
  FROM joined
  GROUP BY panel_run_id, season, week, cand_ix
)
SELECT
  c.panel_run_id,
  c.season,
  c.week,
  c.cand_ix,
  c.tag,
  c.all_tags,
  c.selected,
  c.selected_rank,
  c.salary,
  c.p_line,
  c.sim_mean,
  c.sim_q90,
  c.sim_q99,
  c.tail_line,
  ('boom' IN UNNEST(SPLIT(c.all_tags, ','))) AS boom_tagged,
  a.skill_player_count,
  a.matchup_matched_count,
  a.matchup_supported_count,
  a.receiver_count,
  a.receiver_supported_count,
  a.receiver_edge_mean,
  a.receiver_edge_max,
  a.receiver_easy_count,
  a.wr1_easy_count,
  a.rb_edge_mean,
  a.rb_edge_max,
  a.rb_easy_count,
  a.rb1_easy_count,
  a.qb_edge,
  a.qb_easy,
  a.lineup_edge_mean,
  a.lineup_edge_max,
  IF(a.receiver_edge_mean IS NOT NULL AND c.sim_q99 IS NOT NULL,
     a.receiver_edge_mean * c.sim_q99, NULL) AS boom_edge_interaction,
  c.actual_score,
  (c.actual_score >= 194) AS actual_ge_194,
  (c.actual_score > 200) AS actual_gt_200,
  (c.actual_score > 210) AS actual_gt_210,
  (c.actual_score > 220) AS actual_gt_220
FROM candidates c
JOIN aggregated a
  ON a.panel_run_id = c.panel_run_id
 AND a.season = c.season AND a.week = c.week AND a.cand_ix = c.cand_ix
