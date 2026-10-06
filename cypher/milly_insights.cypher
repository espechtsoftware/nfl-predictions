// Milly graph (scripts/load_milly_neo4j.py; a local instance): saved queries for the Neo4j Browser.
// Week keys look like '2026-04' (milly_graph.week_key). Browser queries at the end take parameters:
// :param user => '<DraftKings name>'    :param week_key => '2026-04'    :param player => '<player name>'
// Generated from nfl_dfs.dashboard.milly_graph; keep the two in step.
// The uniqueness constraints are in cypher/milly_schema.cypher.

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

// Panel: repeat_finishers (DraftKings user names; the graph is local only)
MATCH (u:User)-[:ENTERED]->(l:Lineup)
WHERE coalesce(l.source, 'top') = 'top'
WITH u, count(l) AS loaded, sum(CASE WHEN l.top_1pct THEN 1 ELSE 0 END) AS top_1pct_lineups,
     count(DISTINCT CASE WHEN l.top_1pct THEN l.week_key END) AS top_1pct_weeks, min(l.rank) AS best_rank
WHERE top_1pct_lineups > 0
RETURN u.name AS user, top_1pct_weeks, top_1pct_lineups, best_rank, loaded
ORDER BY top_1pct_weeks DESC, top_1pct_lineups DESC, best_rank LIMIT 25;

// Panel: winning_shapes
MATCH (l:Lineup)-[:ENTERED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
WHERE l.rank = 1
RETURN w.key AS week, l.points AS points, l.stack_label AS stack, l.salary AS salary,
       l.own_sum AS own_sum, l.dupes AS dupes
ORDER BY week;

// Insights: winners_vs_projected
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)-[r:FP_PROJECTED]->(w:Week {key: l.week_key})
WHERE coalesce(l.source, 'top') = 'top'
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

// ---- Browser queries with parameters (portfolios loaded with --users-file; operator 2026-10-06) ----
// :param user => '<DraftKings name>'    :param week_key => '2026-04'    :param player => '<player name>'

// Browser: user_core
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})
WITH count(l) AS n, collect(l) AS ls
UNWIND ls AS l
MATCH (l)-[:CONTAINS]->(p:Player)
WITH n, p, count(l) AS k
RETURN p.name AS player, p.position AS position, p.team AS team, k AS lineups, round(100.0 * k / n, 1) AS pct
ORDER BY lineups DESC LIMIT 40;

// Browser: what_replaced_player
MATCH (x:Player {name: $player})
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})
WHERE NOT (l)-[:CONTAINS]->(x)
MATCH (l)-[:CONTAINS]->(p:Player {position: x.position})
RETURN p.name AS instead, p.team AS team, p.team = x.team AS same_team, count(l) AS lineups
ORDER BY lineups DESC LIMIT 15;

// Browser: user_qb_receivers
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})-[:CONTAINS]->(q:Player {position: 'QB'})
OPTIONAL MATCH (l)-[:CONTAINS]->(r:Player) WHERE r.position IN ['WR', 'TE'] AND r.team = q.team
RETURN q.name AS qb, coalesce(r.name, '(no teammate receiver)') AS receiver, r.position AS position,
       count(l) AS lineups
ORDER BY qb, lineups DESC;

// Browser: user_stack_graph
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})-[:CONTAINS]->(q:Player {position: 'QB'})
MATCH (l)-[:CONTAINS]->(r:Player) WHERE r.position IN ['WR', 'TE', 'RB'] AND r.team = q.team
RETURN q, r, count(l) AS lineups;
