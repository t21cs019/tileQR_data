"""g〜j の共通層。4機種×2定義の点を作る。
  3機種: common10.load_s1（eta_eff.csv、G は各 nb の最高）。t_obs = W/G、t_model = W/(p·A·E_カーネル·E_並列理論値)（定義Mの基準）、
         t_ideal = W/(p·A·E_カーネル)（定義Kの基準）。E_カーネル = nb/(nb+β)。
  不老・弐: 2026-11-17_dag-parallelism/data/c_split.csv の kernel=ib=nb/8, policy=fifo。5回の平均（T_obs_mean）。
         t_model = T_model（= T_ideal + D_time。確認済み）、t_ideal = T_ideal。
  定義M: excess_M = t_obs − t_model ／ 定義K: excess_K = t_obs − t_ideal
  予測 nb: 3機種 = tau_predictions.csv の nb_theory、不老・弐 = c_table_points の tag=pred（32/40/72/128）。
  最適 nb（実測）: 3機種 = G 最大の nb、不老・弐 = T_obs_mean 最小の nb。
  タスク数 = N³/3 + N²/2（N = size/nb）。"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, AN, MACHINES, load_s1  # noqa: E402

FLOW2 = "不老・弐（p = 192）"
NAMES = {**MACHINES, "flow2": FLOW2}
SHORT = {"EPYC 7543（p = 32）": "EPYC 7543", "EPYC 7702（p = 64、1ソケット）": "EPYC 7702", "Xeon Silver 4214（p = 12、1ソケット）": "Xeon 4214", FLOW2: "不老・弐"}
ORDER = [MACHINES["EPYC7543"], MACHINES["EPYC7702 s1"], MACHINES["Xeon4214 s1"], FLOW2]


def points():
    e = load_s1()
    pr = pd.read_csv(AN / "2026-11-10_serial-task-cost/data/tau_predictions.csv")
    rows = []
    for lab, pn in MACHINES.items():
        g = e[e.label == lab].copy()
        g["t_ideal"] = g.W / (g.p * g.A_k * g.nb / (g.nb + g.beta_k)) / 1e9
        nbp = pr[pr.label == lab].set_index("size").nb_theory
        opt = g.loc[g.groupby("size").G.idxmax()].set_index("size").nb
        for _, r in g.iterrows():
            rows.append(dict(panel=pn, p=r.p, size=r["size"], nb=r.nb, tasks=r.tasks, t_obs=r.t_obs, t_model=r.t_model, t_ideal=r.t_ideal,
                             nb_pred=nbp[r["size"]], nb_opt=opt[r["size"]]))
    c = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/c_split.csv")
    c = c[(c.kernel == "ib=nb/8") & (c.policy == "fifo")]
    pt = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/c_table_points.csv")
    pred = pt[(pt.tag == "pred") & (pt.kernel == "ib=nb/8")].set_index("size").nb
    opt = c.loc[c.groupby("size").T_obs_mean.idxmin()].set_index("size").nb
    for _, r in c.iterrows():
        N = r["size"] / r.nb
        rows.append(dict(panel=FLOW2, p=192, size=r["size"], nb=r.nb, tasks=N**3 / 3 + N**2 / 2, t_obs=r.T_obs_mean, t_model=r.T_model, t_ideal=r.T_ideal,
                         nb_pred=pred[r["size"]], nb_opt=opt[r["size"]], starv_total=r.starv_total, rest_mean=r.rest_mean, explained_mean=r.explained_mean,
                         excess_K_csv=r.excess_mean, T_obs_fast=r.T_obs_fast, T_obs_slow=r.T_obs_slow))
    d = pd.DataFrame(rows)
    d["N"] = d["size"] / d.nb
    d["excess_M"] = d.t_obs - d.t_model
    d["excess_K"] = d.t_obs - d.t_ideal
    d["cls"] = np.where(d.nb < d.nb_pred, "lt_pred", "ge_pred")
    return d


def fit_loglog(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3: return dict(n=len(x), slope=np.nan, R2=np.nan, tau_us=np.nan)
    lx, ly = np.log10(x), np.log10(y)
    s, a = np.polyfit(lx, ly, 1)
    R2 = 1 - ((ly - a - s * lx) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    return dict(n=len(x), slope=s, R2=R2, tau_us=10 ** (ly - lx).mean() * 1e6)


def slope_table(d, col, by=("panel",)):
    rows = []
    for key, g in d.groupby(list(by), sort=False):
        for name, m in [("全点", g.nb > 0), ("nb < 予測 nb", g.cls == "lt_pred"), ("nb ≥ 予測 nb", g.cls == "ge_pred")]:
            h = g[m]; pos = h[h[col] > 0]
            rows.append(dict(**dict(zip(by, key if isinstance(key, tuple) else (key,))), subset=name, n_total=len(h), n_nonpositive=len(h) - len(pos), **fit_loglog(pos.tasks, pos[col])))
    return pd.DataFrame(rows)
