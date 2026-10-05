// Milly graph schema: one uniqueness constraint per label the loader MERGEs,
// on the property it MERGEs on (nfl_dfs.dashboard.milly_graph.MERGED_KEYS).
// scripts/load_milly_neo4j.py applies this file before its first batch.
// Player identity is the DraftKings player id, never the display name.
CREATE CONSTRAINT milly_week_key IF NOT EXISTS FOR (n:Week) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT milly_contest_id IF NOT EXISTS FOR (n:Contest) REQUIRE n.contest_id IS UNIQUE;
CREATE CONSTRAINT milly_game_id IF NOT EXISTS FOR (n:Game) REQUIRE n.game_id IS UNIQUE;
CREATE CONSTRAINT milly_team_code IF NOT EXISTS FOR (n:Team) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT milly_player_dk_id IF NOT EXISTS FOR (n:Player) REQUIRE n.dk_player_id IS UNIQUE;
CREATE CONSTRAINT milly_lineup_key IF NOT EXISTS FOR (n:Lineup) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT milly_user_name IF NOT EXISTS FOR (n:User) REQUIRE n.name IS UNIQUE;
