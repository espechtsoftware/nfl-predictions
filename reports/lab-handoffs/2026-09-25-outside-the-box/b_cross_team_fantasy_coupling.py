import re, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
a=pd.read_parquet("ps_all.parquet"); a=a[(a.season_type=="REG")&(a.season>=2012)].rename(columns={"recent_team":"team","interceptions":"ints"})
b=pd.read_parquet("ps_2025.parquet"); b=b[b.season_type=="REG"].rename(columns={"passing_interceptions":"ints"})
cols=["player_display_name","position","team","season","week","passing_yards","passing_tds","ints","rushing_yards","rushing_tds","receptions","receiving_yards","receiving_tds","rushing_fumbles_lost","receiving_fumbles_lost","sack_fumbles_lost","targets","attempts","carries"]
st=pd.concat([a[cols],b[cols]]).fillna(0); st=st[st.position.isin(["QB","RB","WR","TE"])]
st["dk"]=(st.passing_yards*0.04+st.passing_tds*4-st.ints+3*(st.passing_yards>=300)+st.rushing_yards*0.1+st.rushing_tds*6+3*(st.rushing_yards>=100)
          +st.receptions+st.receiving_yards*0.1+st.receiving_tds*6+3*(st.receiving_yards>=100)-(st.rushing_fumbles_lost+st.receiving_fumbles_lost+st.sack_fumbles_lost))
tg=st.groupby(["season","week","team"]).agg(dk=("dk","sum"),vol=("targets","sum"),car=("carries","sum"),att=("attempts","sum")).reset_index()
tg["plays"]=tg.att+tg.car
g=pd.read_csv("games.csv"); g=g[(g.game_type=="REG")&g.total_line.notna()&g.home_score.notna()&(g.season>=2012)&(g.season<=2025)].copy()
fix={"OAK":"LV","SD":"LAC","STL":"LA","LAR":"LA"}
tg["team"]=tg.team.replace(fix); g["home_team"]=g.home_team.replace(fix); g["away_team"]=g.away_team.replace(fix)
g["home_impl"]=(g.total_line+g.spread_line)/2; g["away_impl"]=(g.total_line-g.spread_line)/2
h=g.merge(tg.add_prefix("h_"),left_on=["season","week","home_team"],right_on=["h_season","h_week","h_team"])
h=h.merge(tg.add_prefix("a_"),left_on=["season","week","away_team"],right_on=["a_season","a_week","a_team"])
print("games matched:",len(h))
# residualize team DK on own implied total and opponent implied total (linear), then correlate across the two teams
long=pd.concat([pd.DataFrame(dict(gid=h.game_id,dk=h.h_dk,plays=h.h_plays,impl=h.home_impl,oimpl=h.away_impl,side="h")),
                pd.DataFrame(dict(gid=h.game_id,dk=h.a_dk,plays=h.a_plays,impl=h.away_impl,oimpl=h.home_impl,side="a"))])
for y in ["dk","plays"]:
    X=np.column_stack([np.ones(len(long)),long.impl,long.oimpl]); bb,*_=np.linalg.lstsq(X,long[y].values,rcond=None); long[y+"_r"]=long[y]-X@bb
w=long.pivot(index="gid",columns="side",values=["dk_r","plays_r","dk"])
print("team skill-DK residual SD %.1f (mean team skill DK %.1f) -> CV %.2f" % (long.dk_r.std(), long.dk.mean(), long.dk_r.std()/long.dk.mean()))
print("corr across opponents | market: skill-DK residual %+.3f ; plays residual %+.3f" % (np.corrcoef(w["dk_r"]["h"],w["dk_r"]["a"])[0,1], np.corrcoef(w["plays_r"]["h"],w["plays_r"]["a"])[0,1]))
print("raw corr of team skill DK across opponents (unconditional): %+.3f" % np.corrcoef(w["dk"]["h"],w["dk"]["a"])[0,1])
