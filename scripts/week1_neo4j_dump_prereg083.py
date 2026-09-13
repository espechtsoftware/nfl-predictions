"""Dump the PREREG-083 candidate corpus (Neo4j) to parquet: one row per candidate occurrence with roster players."""
import pandas as pd
from neo4j import GraphDatabase
d = GraphDatabase.driver("bolt://127.0.0.1:7687")
Q = """MATCH (c:CandidateOccurrence)-[:INSTANCE_OF]->(r:Roster)-[:CONTAINS_PLAYER]->(p:Player)
       WITH c, r, collect(p.player_id) AS players
       RETURN c.season AS season, c.week AS week, c.arm AS arm, toInteger(c.candidate_rank) AS candidate_rank, c.selected AS selected,
              c.selected_rank AS selected_rank, toFloat(c.realized_score) AS actual, toFloat(c.sim_mean) AS sim_mean, toFloat(c.sim_q90) AS sim_q90,
              toFloat(c.sim_q99) AS sim_q99, toInteger(c.sim_q99_rank) AS sim_q99_rank, toFloat(c.p187) AS p187, toFloat(c.p194) AS p194, toFloat(c.p200) AS p200,
              toFloat(c.p210) AS p210, toFloat(c.p220) AS p220, toFloat(c.served_projection) AS served_projection, toInteger(r.salary) AS salary, players"""
with d.session() as s:
    rows = [dict(r) for r in s.run(Q)]
df = pd.DataFrame(rows); df["season"] = df.season.astype(int); df["week"] = df.week.astype(int); df["selected"] = df.selected.astype(str) == "True"
df["selected_rank"] = pd.to_numeric(df.selected_rank, errors="coerce"); df["players"] = df.players.apply(lambda l: ",".join(sorted(l)))
df.to_parquet("/home/erich/week1-sunday/pool-level/prereg083_candidates.parquet"); print(df.shape, df.groupby(["season","arm"]).size().to_dict(), "selected", int(df.selected.sum()))
