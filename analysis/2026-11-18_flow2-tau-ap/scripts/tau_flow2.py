"""不老・弐（p = 192）で、時間 = W/(p·A·E·η理論) + タスク数·τ の最小になる nb を予測し、実測の性能比を出す。
入力：analysis/2026-11-17_flow2-perf-ratio-3agg/data/a_curves.csv、出力：data/summary.csv
使い方：python -I scripts/tau_flow2.py <a_curves.csv> data/summary.csv"""
import numpy as np, pandas as pd, sys
c = pd.read_csv(sys.argv[1])
P, A, B = 192, 99.689, 123.83
C = np.sqrt(7.5)
c["N"] = c["size"]/c.nb
c["tasks"] = c.N**3/3 + c.N**2/2
W = 4/3*c["size"]**3
eta = 1/(1+(C*np.sqrt(P)*c.nb/c["size"])**2)
c["t_model"] = W/(P*A*c.nb/(c.nb+B)*eta)/1e9
rows=[]
for tau in [0, 15.4, 17.3, 18.0, 30, 47, 90.6]:
    for agg in ["fast","mean"]:
        for s,g in c.groupby("size"):
            g=g.sort_values("nb")
            t_obs = W[g.index]/g[agg]/1e9
            tp = g.t_model + g.tasks*tau*1e-6
            i = int(np.argmin(tp.values)); io=int(np.argmax(g[agg].values))
            rows.append(dict(tau=tau,agg=agg,size=s,nb_pred=int(g.nb.iloc[i]),nb_obs=int(g.nb.iloc[io]),
              perf=g[agg].iloc[i]/g[agg].max(), t_err_at_obsopt=(tp.iloc[io]/t_obs.iloc[io]-1)))
r=pd.DataFrame(rows)
print(r[r["agg"]=="fast"].round(3).to_string(index=False))
print(r[r["agg"]=="mean"].groupby("tau").perf.agg(["min","mean"]).round(3))
r.to_csv(sys.argv[2], index=False, float_format="%.4g")
