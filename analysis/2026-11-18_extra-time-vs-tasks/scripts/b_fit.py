"""機種ごとの当てはめ。excess_s > 0 の点だけ（log を取るため。除いた数も出す）。
  log-log 自由当てはめ: log10(余分な時間) = a + 傾き·log10(タスク数) → 傾き、R²（log-log）
  τ: 傾き1に固定した log-log 当てはめ（log τ = log(余分な時間/タスク数) の平均、つまり幾何平均）。R²_固定 は同じ log 空間での決定係数。
  部分集合 all / lt_pred / ge_pred でも出す。不老・弐は agg=fast を主、slow・mean も参考に。
  d_rest_fit.csv 式1 の c0・τ（size ごと、速い水準）も写す（当てはめ直さない）。
  スライド p.15 の確認: nb ごと（size 1024〜16384）の 1タスクあたり余分な時間 [µs]。
出力: data/b_fit.csv, data/b_slide_check.csv, data/b_flow2_c0tau.csv"""
import numpy as np, pandas as pd
from common import *

def fit(x, y):
    lx, ly = np.log10(x), np.log10(y)
    if len(x) < 3: return dict(n=len(x), slope=np.nan, R2=np.nan, tau_us=np.nan, R2_fixed=np.nan)
    s, a = np.polyfit(lx, ly, 1)
    R2 = 1 - ((ly - (a + s * lx)) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    b = (ly - lx).mean()
    R2f = 1 - ((ly - (b + lx)) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    return dict(n=len(x), slope=s, R2=R2, tau_us=10**b * 1e6, R2_fixed=R2f)

d = pd.read_csv(OUT / "data/a_points.csv")
rows = []
for (pn, agg), g in d.groupby(["panel", "agg"], sort=False):
    for sub, gg in [("all", g), ("lt_pred", g[g.rel_pred == "lt_pred"]), ("ge_pred", g[g.rel_pred == "ge_pred"])]:
        n_all = len(gg); gp = gg[gg.positive]
        rows.append(dict(panel=pn, agg=agg, subset=sub, n_total=n_all, n_excluded_nonpositive=n_all - len(gp), **fit(gp.tasks.values, gp.excess_s.values)))
f = pd.DataFrame(rows); f.to_csv(OUT / "data/b_fit.csv", index=False, float_format="%.4g")
print(f.to_string())

s = d[d["agg"] == "best-of-ib"]
s = s.assign(us_per_task=s.excess_s / s.tasks * 1e6)
chk = []
for pn, nbs in [(MACHINES["EPYC7702 s1"], [32]), (MACHINES["EPYC7543"], [32, 64])]:
    for nb in nbs:
        g = s[(s.panel == pn) & (s.nb == nb)].sort_values("size")
        gp = g[g.positive]
        r = fit(gp.tasks.values, gp.excess_s.values)
        chk.append(dict(panel=pn, nb=nb, sizes=" ".join(map(str, g["size"].astype(int))), us_per_task_by_size=" ".join(f"{v:.2f}" for v in g.us_per_task),
                        min=g.us_per_task.min(), max=g.us_per_task.max(), tau_geomean=r["tau_us"],
                        tau_lsq_origin=(g.excess_s * g.tasks).sum() / (g.tasks ** 2).sum() * 1e6))
pd.DataFrame(chk).to_csv(OUT / "data/b_slide_check.csv", index=False, float_format="%.4g")
print(pd.DataFrame(chk).to_string())
r = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/d_rest_fit.csv")
r = r[(r.form == "式1") & (r.scope != "all")]
r.to_csv(OUT / "data/b_flow2_c0tau.csv", index=False)
