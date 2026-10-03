// Milly graph (scripts/load_milly_neo4j.py): saved queries for the Aura console.
// Generated from nfl_dfs.dashboard.milly_graph; keep the two in step.

CREATE CONSTRAINT milly_week IF NOT EXISTS FOR (n:Week) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT milly_contest IF NOT EXISTS FOR (n:Contest) REQUIRE n.contest_id IS UNIQUE;
CREATE CONSTRAINT milly_game IF NOT EXISTS FOR (n:Game) REQUIRE n.game_id IS UNIQUE;
CREATE CONSTRAINT milly_team IF NOT EXISTS FOR (n:Team) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT milly_player IF NOT EXISTS FOR (n:Player) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT milly_lineup IF NOT EXISTS FOR (n:Lineup) REQUIRE n.key IS UNIQUE;

// Panel: stack_pairs
MATCH (a:Player)-[r:STACKED_WITH]->(b:Player)
WHERE r.kind = 'teammate'
RETURN a.name AS player_a, b.name AS player_b,
       sum(r.top_1pct_count) AS top_1pct_lineups, sum(r.count) AS lineups,
       count(DISTINCT r.week_key) AS weeks
ORDER BY top_1pct_lineups DESC, lineups DESC LIMIT 20;

// Panel: bring_backs
MATCH (a:Player)-[r:STACKED_WITH]->(b:Player)
WHERE r.kind = 'opponent'
RETURN a.name AS player_a, b.name AS player_b,
       sum(r.top_1pct_count) AS top_1pct_lineups, count(DISTINCT r.week_key) AS weeks
ORDER BY top_1pct_lineups DESC LIMIT 15;

// Panel: players_over_time
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)
WHERE l.top_1pct
WITH p, l.week_key AS wk, count(l) AS n
ORDER BY wk
RETURN p.name AS player, p.position AS position, collect(wk + ':' + toString(n)) AS weeks,
       count(wk) AS n_weeks, sum(n) AS top_1pct_lineups
ORDER BY n_weeks DESC, top_1pct_lineups DESC LIMIT 25;

// Panel: winning_shapes
MATCH (l:Lineup)-[:ENTERED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
WHERE l.rank = 1
RETURN w.key AS week, l.points AS points, l.stack_label AS stack, l.salary AS salary,
       l.own_sum AS own_sum, l.dupes AS dupes
ORDER BY week;

// Insights: winners_vs_projected
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)-[r:FP_PROJECTED]->(w:Week {key: l.week_key})
WITH l, sum(r.fp_own) AS own_sum, sum(r.fp_proj) AS proj_sum
RETURN l.week_key AS week,
       CASE WHEN l.rank = 1 THEN 'winner' WHEN l.top_1pct THEN 'top 1%' ELSE 'loaded' END AS grp,
       count(l) AS lineups, avg(own_sum) AS fp_own_sum, avg(proj_sum) AS fp_proj_sum
ORDER BY week, grp;

// Insights: leverage_paid
MATCH (p:Player)-[o:OWNED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
MATCH (p)-[r:FP_PROJECTED]->(w)
OPTIONAL MATCH (l:Lineup {top_1pct: true})-[:CONTAINS]->(p) WHERE l.week_key = w.key
WITH w, p, o, r, count(l) AS top1_lineups
WHERE (o.own <= 0.6 * r.fp_own AND r.fp_own - o.own >= 3 AND top1_lineups > 0)
   OR (r.fp_own >= 15 AND top1_lineups = 0)
RETURN w.key AS week, p.name AS player, r.fp_own AS fp_own, o.own AS realized,
       top1_lineups, o.fpts AS fpts,
       CASE WHEN r.fp_own >= 15 AND top1_lineups = 0 THEN 'chalk that busted'
            ELSE 'leverage that paid' END AS category
ORDER BY week, category, abs(r.fp_own - o.own) DESC;

// Insights: stack_outcomes
MATCH (a:Player)-[s:STACKED_WITH {kind: 'teammate'}]->(b:Player)
WHERE s.top_1pct_count > 0 AND (a.position = 'QB' OR b.position = 'QB')
OPTIONAL MATCH (a)-[ra:FP_PROJECTED]->(w:Week {key: s.week_key})
OPTIONAL MATCH (b)-[rb:FP_PROJECTED]->(w)
RETURN s.week_key AS week, a.name AS player_a, b.name AS player_b,
       s.top_1pct_count AS top_1pct_lineups,
       coalesce(ra.fp_own, 0) + coalesce(rb.fp_own, 0) AS pair_fp_own
ORDER BY week, top_1pct_lineups DESC LIMIT 60;
