"""Builds panel.parquet (team codes normalized) and panel_rawcodes.parquet (schedule codes left as OAK/SD/STL, which is
what the reviewer's scripts effectively did) from build_panel.sql."""
import sys; sys.path.insert(0, ".")
from pathlib import Path
from bqh import q
sql = Path("build_panel.sql").read_text()
raw = (sql.replace("CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE home_team END home", "home_team home")
          .replace("CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE away_team END away", "away_team away"))
assert raw != sql and "home_team home" in raw and "away_team away" in raw
for name, s in (("panel", sql), ("panel_rawcodes", raw)):
    D = q(s); D.to_parquet(f"{name}.parquet")
    print(name, D.shape)
    print(D.groupby("season").agg(n=("team", "size"), off_missing=("te1_max", lambda s: s.isna().sum()), epa_in6=("epa_in6", "count"),
          epa_x6=("epa_x6", "count"), stale=("epa_stale", "count"), te1_sal=("te1_sal", "count"), itt=("itt", "count"), n_al=("n_al", "count")).to_string())
