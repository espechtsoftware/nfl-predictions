import json, re, glob, pandas as pd, numpy as np
pmap={int(k):tuple(v) for k,v in json.load(open("linestar/pmap.json")).items()}
rows=[]; meta=[]
for pid,(season,week) in sorted(pmap.items()):
    d=json.load(open(f"linestar/p{pid}.json"))
    own=d.get("Ownership") or {}
    sc=json.loads(d["SalaryContainerJson"])
    mains=[s for s in own.get("Slates",[]) if s.get("SlateName")=="Main" and s.get("Mode")==0]
    if not mains: meta.append((season,week,"no main")); continue
    main=mains[0]; sid=main["Id"]
    proj={o["SalaryId"]:o["Owned"] for o in (own.get("Projected") or {}).get(str(sid),[])}
    crs=[cr for cr in own.get("ContestResults",[]) if cr["Contest"]["SlateId"]==sid]
    if not crs: meta.append((season,week,"no contest")); continue
    big=max(crs,key=lambda cr: cr["Contest"]["EntryCount"])
    act={o["SalaryId"]:o["Owned"] for o in big["OwnershipData"]}
    meta.append((season,week,big["Contest"]["ContestName"][:60],big["Contest"]["EntryCount"],len(proj),len(act)))
    for r in sc["Salaries"]:
        if r["Id"] not in proj: continue   # main-slate players = those with a projected ownership on the main slate
        m=re.search(r"/Date\((\d+)",str(r.get("GT")))
        gt=pd.to_datetime(int(m.group(1)),unit="ms",utc=True) if m else pd.NaT
        rows.append(dict(season=season,week=week,pid=r["PID"],sid=r["Id"],name=r["Name"],pos=str(r["POS"]).upper(),
            team=r.get("PTEAM"),opp=r.get("OTEAM"),sal=r.get("SAL"),pp=r.get("PP"),ceil=r.get("Ceil"),floor=r.get("Floor"),
            ps=r.get("PS"),ppg=r.get("PPG"),conf=r.get("Conf"),is_=r.get("IS"),stat=r.get("STAT"),gi=r.get("GI"),gt=gt,
            own_proj=proj.get(r["Id"]),own_act=act.get(r["Id"],0.0),contest_n=big["Contest"]["EntryCount"]))
df=pd.DataFrame(rows); df.to_parquet("ls_main.parquet")
print(pd.DataFrame(meta).to_string()[:3000]); print(df.shape)
print(df[["pp","ps","own_proj","own_act","ceil","floor","sal"]].describe().round(2))
print("IS values",df.is_.value_counts().head(10).to_dict()," STAT",df.stat.value_counts().head(10).to_dict())
