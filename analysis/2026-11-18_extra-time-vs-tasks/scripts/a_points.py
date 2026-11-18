"""各点の元データを作る。
  3機種（EPYC7543, EPYC7702 s1, Xeon4214 s1）: eta_eff.csv（common10.load_s1）。余分な時間 = t_obs − t_model（r0=1、E_並列 理論値、機種ごとの A,β）
  不老・弐: 2026-11-17_dag-parallelism/data/c_table_points.csv の kernel=ib=nb/8（A=99.7, β=124）の excess_fast/slow/mean
            （実測 − W/(p·A·E_カーネル)。E_並列 を引かない定義）。タスク数は N³/3+N²/2（N=size/nb）で数え直す。
  予測 nb: 3機種は tau_predictions.csv の nb_theory（理論値のままのモデルの最適 nb、size ごと）。不老・弐は c_table_points の tag=pred。
  nb >= 予測 nb を "ge_pred"、小さい方を "lt_pred"。
出力: data/a_points.csv（size, nb, tasks, excess_s, agg, 余分な時間の定義, 予測 nb との関係, 正の値か）"""
import numpy as np, pandas as pd
from common import *

def main():
    e = load_s1()
    pr = pd.read_csv(AN / "2026-11-10_serial-task-cost/data/tau_predictions.csv")
    rows = []
    for lab in MACHINES:
        g = e[e.label == lab].copy()
        nbp = pr[pr.label == lab].set_index("size").nb_theory
        g["nb_pred"] = g["size"].map(nbp)
        g["excess_s"] = g.t_obs - g.t_model
        for _, r in g.iterrows():
            rows.append(dict(panel=MACHINES[lab], p=r.p, size=r["size"], nb=r.nb, tasks=r.tasks, excess_s=r.excess_s, agg="best-of-ib",
                             definition="実測−モデル(E_カーネル×E_並列理論値)", nb_pred=r.nb_pred))
    c = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/c_table_points.csv")
    c = c[c.kernel == "ib=nb/8"]
    pred = c[c.tag == "pred"].set_index("size").nb
    for _, r in c.iterrows():
        N = r["size"] / r.nb
        for a in ("fast", "slow", "mean"):
            rows.append(dict(panel=FLOW2, p=192, size=r["size"], nb=r.nb, tasks=N**3 / 3 + N**2 / 2, excess_s=r[f"excess_{a}"], agg=a,
                             definition="実測−完全に並列な時間 W/(p·A·E_カーネル)", nb_pred=pred[r["size"]]))
    d = pd.DataFrame(rows)
    d["rel_pred"] = np.where(d.nb >= d.nb_pred, "ge_pred", "lt_pred")
    d["positive"] = d.excess_s > 0
    d.to_csv(OUT / "data/a_points.csv", index=False, float_format="%.6g")
    print(d.groupby(["panel", "agg"]).agg(n=("nb", "size"), neg=("positive", lambda x: (~x).sum())))
    print(d[~d.positive].groupby(["panel", "rel_pred"]).size())

main()
