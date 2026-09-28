import sys, re, pandas as pd
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
src = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "milly_shape_lift.py")).read()   # the laptop's script, one level up in reports/lab-handoffs/
ns = {}; exec(src.split("\ndef lift")[0], ns)          # defines SQL and PROJ using the production settings
from nfl_dfs.bq import query_df
x = query_df(ns["SQL"]); x.to_parquet("field_shapes_w123.parquet"); print("shapes", x.shape)
p = query_df(ns["PROJ"]); p.to_parquet("field_proj_w123.parquet"); print("proj", p.shape)
