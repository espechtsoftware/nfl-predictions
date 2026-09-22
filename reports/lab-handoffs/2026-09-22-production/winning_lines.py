"""What did it actually take to win/cash in Weeks 1-2, vs what our pool could make?"""
import pandas as pd, sys
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
q = f"""
SELECT week, contest_id, ANY_VALUE(contest_name) contest_name, COUNT(*) entries,
       MAX(points) win_line,
       APPROX_QUANTILES(points, 100)[OFFSET(99)] p99,
       APPROX_QUANTILES(points, 100)[OFFSET(90)] p90,
       APPROX_QUANTILES(points, 100)[OFFSET(50)] median
FROM `{settings.raw}.contest_entries`
WHERE season=2026 AND week IN (1,2)
GROUP BY week, contest_id
ORDER BY week, entries DESC
"""
df = query_df(q)
pd.set_option("display.width", 200)
print(df.to_string(index=False))
POOL = {1: 236.28, 2: 197.26}
BOOK = {1: 218.40, 2: 157.96}
print("\n=== our pool oracle / entered best vs the line that WON each contest ===")
for _, r in df.iterrows():
    w = int(r.week)
    print(f"  wk{w} {str(r.contest_name)[:38]:<38} entries {int(r.entries):>7}  "
          f"win {r.win_line:7.2f}   pool_oracle {POOL[w]-r.win_line:+7.2f}   "
          f"book_best {BOOK[w]-r.win_line:+7.2f}")
