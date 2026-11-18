"""
d：模擬で説明できない残りを、τ の候補として式に当てはめる（候補の1つ。決めたモデルではない）。
  式1：T_obs = T_sim + c0 + τ·タスク数
  式2：T_obs = T_sim/r0 + c0 + τ·タスク数      （r0：全コアで動くときのカーネルの一様な遅れ。11-10 の serial_tau.py の r0 と同じ役）
相対誤差の二乗和を最小にする（重み 1/T_obs の線形最小二乗）。size ごとと、4 size まとめての2通り。
nb の範囲は、11-10 report.md C 節で速い水準が当てになるとされた範囲（1024・2048 は nb ≥ 96、4096 は ≥ 160、8192 は ≥ 192）。
A・β は ib=nb/8、模擬は fifo。
出力：data/d_rest_fit.csv、data/d_c0_vs_matrix_MB.csv（c0 と行列の大きさの直線）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

NB_MIN = {1024: 96, 2048: 96, 4096: 160, 8192: 192}
d = pd.read_csv(DATA / "c_split.csv")
d = d[(d.kernel == "ib=nb/8") & (d.policy == "fifo")]
d = d[d.nb >= d["size"].map(NB_MIN)]
rows = []
for a in AGGS:
    for scope, g in [(str(s), g) for s, g in d.groupby("size")] + [("all", d)]:
        y = g[f"T_obs_{a}"].to_numpy()
        wt = 1 / y
        for form in ["式1", "式2"]:
            if form == "式1":
                X = np.c_[np.ones(len(g)), g.tasks]
                yy = y - g.T_sim.to_numpy()
            else:
                X = np.c_[np.ones(len(g)), g.tasks, g.T_sim]
                yy = y
            coef, *_ = np.linalg.lstsq(X * wt[:, None], yy * wt, rcond=None)
            fit = X @ coef + (g.T_sim.to_numpy() if form == "式1" else 0)
            rel = (fit - y) / y
            rows.append(dict(agg=a, scope=scope, form=form, n=len(g),
                             c0_ms=coef[0] * 1e3, tau_us=coef[1] * 1e6,
                             r0=(1 / coef[2]) if form == "式2" else 1.0,
                             rel_rms=np.sqrt(np.mean(rel**2)), rel_max=np.abs(rel).max()))
R = pd.DataFrame(rows)
R.to_csv(DATA / "d_rest_fit.csv", index=False)
print(R.round(3).to_string(index=False))

# c0（式1、size ごと）の行列の大きさ（size²·8 B）への依存：c0 = a + b·MB の直線
mb = {1024: 8.0, 2048: 32.0, 4096: 128.0, 8192: 512.0}
rows = []
for a in AGGS:
    g = R[(R["agg"] == a) & (R.form == "式1") & (R.scope != "all")]
    x = g.scope.astype(int).map(mb).to_numpy(); y = g.c0_ms.to_numpy()
    b, a0 = np.polyfit(x, y, 1)
    rows.append(dict(agg=a, intercept_ms=a0, slope_ms_per_MB=b, resid_max_ms=np.abs(a0 + b * x - y).max()))
pd.DataFrame(rows).to_csv(DATA / "d_c0_vs_matrix_MB.csv", index=False)
print(pd.DataFrame(rows).round(3).to_string(index=False))
