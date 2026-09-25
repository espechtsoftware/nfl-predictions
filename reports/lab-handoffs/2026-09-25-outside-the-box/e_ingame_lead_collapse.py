import re, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
def norm(s):
    s=str(s).lower(); s=re.sub(r"[\.\'’]","",s); s=re.sub(r"-"," ",s)
    s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",s); return re.sub(r"\s+"," ",s).strip()
sn=pd.concat([pd.read_parquet(f"snaps_{y}.parquet") for y in range(2018,2026)])
sn=sn[(sn.game_type=="REG")&(sn.position.isin(["RB","WR","TE","QB"]))].copy(); sn["nm"]=sn.player.map(norm)
# DK points from nflverse stats
a=pd.read_parquet("ps_all.parquet"); a=a[(a.season_type=="REG")&(a.season>=2018)]
a=a.rename(columns={"recent_team":"team","interceptions":"ints"})
b=pd.read_parquet("ps_2025.parquet"); b=b[b.season_type=="REG"].rename(columns={"passing_interceptions":"ints"})
cols=["player_display_name","team","season","week","passing_yards","passing_tds","ints","rushing_yards","rushing_tds","receptions","receiving_yards","receiving_tds","rushing_fumbles_lost","receiving_fumbles_lost","sack_fumbles_lost","passing_2pt_conversions","rushing_2pt_conversions","receiving_2pt_conversions"]
st=pd.concat([a[cols],b[cols]]).fillna(0)
st["dk"]=(st.passing_yards*0.04+st.passing_tds*4-st.ints+3*(st.passing_yards>=300)+st.rushing_yards*0.1+st.rushing_tds*6+3*(st.rushing_yards>=100)
          +st.receptions+st.receiving_yards*0.1+st.receiving_tds*6+3*(st.receiving_yards>=100)
          -(st.rushing_fumbles_lost+st.receiving_fumbles_lost+st.sack_fumbles_lost)+2*(st.passing_2pt_conversions+st.rushing_2pt_conversions+st.receiving_2pt_conversions))
st["nm"]=st.player_display_name.map(norm)
sn=sn.merge(st[["season","week","nm","dk"]].drop_duplicates(["season","week","nm"]),on=["season","week","nm"],how="left"); sn["dk"]=sn.dk.fillna(0)
sn=sn.sort_values(["season","team","nm","week"])
# pre-game role: mean offense_pct over the player's previous 3 appearances in the same season
sn["prior_pct"]=sn.groupby(["season","team","nm"]).offense_pct.transform(lambda s: s.shift(1).rolling(3,min_periods=2).mean())
out=[]
for pos, lead_min in [("RB",0.55),("WR",0.75),("TE",0.70),("QB",0.90)]:
    x=sn[sn.position==pos]
    for (s,w,t),g in x.groupby(["season","week","team"]):
        g=g.dropna(subset=["prior_pct"]).sort_values("prior_pct",ascending=False)
        if len(g)<2 or g.prior_pct.iloc[0]<lead_min: continue
        lead=g.iloc[0]; backups=g.iloc[1:]
        exit_=(lead.offense_pct<0.5*lead.prior_pct) and (lead.offense_pct<0.40)
        bk=backups.iloc[0]
        out.append(dict(pos=pos,season=s,week=w,team=t,lead_prior=lead.prior_pct,lead_pct=lead.offense_pct,exit=exit_,
                        lead_dk=lead.dk,bk_prior=bk.prior_pct,bk_pct=bk.offense_pct,bk_dk=bk.dk))
o=pd.DataFrame(out)
for pos,g in o.groupby("pos"):
    e=g[g.exit]; n=g[~g.exit]
    print(f"{pos}: lead-player games {len(g)}, in-game collapse (active, <50% of usual & <40% snaps) rate {g.exit.mean():.3%}")
    print(f"   lead DK: normal {n.lead_dk.mean():.1f} vs collapse {e.lead_dk.mean():.1f}")
    print(f"   top backup DK: normal {n.bk_dk.mean():.1f} (P>=20 {np.mean(n.bk_dk>=20):.1%}) vs lead-collapse {e.bk_dk.mean():.1f} (P>=20 {np.mean(e.bk_dk>=20):.1%}); backup snap% {n.bk_pct.mean():.0%} -> {e.bk_pct.mean():.0%}")
    tot20=(g.bk_dk>=20).sum(); via=(e.bk_dk>=20).sum()
    print(f"   share of the top backup's 20+ games that came in lead-collapse games: {via}/{tot20} = {via/max(tot20,1):.0%}")
