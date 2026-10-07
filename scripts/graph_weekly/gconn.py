from pathlib import Path
from neo4j import GraphDatabase
def driver():
    kv = dict(l.split("=", 1) for l in Path.home().joinpath(".config/neo4j-local-milly.txt").read_text().splitlines() if "=" in l)
    return GraphDatabase.driver(kv["NEO4J_URI"].strip(), auth=(kv["NEO4J_USER"].strip(), kv["NEO4J_PASSWORD"].strip()))
