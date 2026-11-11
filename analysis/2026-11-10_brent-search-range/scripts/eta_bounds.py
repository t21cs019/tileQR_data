"""
Brent の上限・下限と実測の関係（57条件）。標準出力は data/eta_bounds.log に残した。

  A. 実測 η_eff（= G ÷ (p·A_k·E_k)）が、上限の時間の線（η_lo = 1/(1+y)）と下限の時間の線（η_hi = min(1, 1/y)）のどこにあるか
     → data/eta_position.csv（全 nb 点）
  B. η の形を (1 + y^q)^(1/q) で上限（q = 1）から下限（q = ∞）まで変えたときの予測 nb での性能比。τ = a·p あり（LOAO）・なし
     → data/eta_forms_predictions.csv（条件ごと）、data/eta_forms_summary.csv
  C. 探索範囲（下限の時間 ≤ 上限の時間の最小）。τ なし、τ を両方に足す、上限だけに足す
  D. 比較：しきい値つきの範囲 {nb : 予測性能 ≥ θ·max}
     → data/range_variants.csv（C と D の要約）
実行: .venv/bin/python analysis/2026-11-10_brent-search-range/scripts/eta_bounds.py
"""
import sys
from pathlib import Path
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent / "2026-11-10_serial-task-cost" / "scripts"))
import numpy as np, pandas as pd
from scipy.optimize import minimize_scalar
from common10 import load_s1, perf_at_argmin, summ

d = load_s1()
d["Wu"] = 4 * d.N**3
d["y"] = d.p * d.D / d.Wu                 # = p / P(N)
d["t1"] = d.W / (d.p * d.A_k * d.nb / (d.nb + d.beta_k)) / 1e9   # W/p（カーネル効率込み）
d["eta_lo"] = 1 / (1 + d.y)               # 時間の上限 → 効率の下限
d["eta_hi"] = np.minimum(1, 1 / d.y)      # 時間の下限 → 効率の上限
d["grp"] = np.where(d.p >= 24, "p>=24", "p<=12")

print("=== A. 実測 η_eff は挟み込みのどこにあるか（全 nb 点） ===")
d["pos"] = np.select([d.eta_eff < d.eta_lo, d.eta_eff > d.eta_hi], ["下限より下", "上限より上"], "間")
d["ybin"] = pd.cut(d.y, [0, 0.1, 0.3, 1, 3, 1e9], labels=["y<0.1", "0.1-0.3", "0.3-1", "1-3", ">3"])
print(pd.crosstab([d.grp, d.ybin], d.pos, normalize="index").round(2).to_string())
print(pd.crosstab([d.grp, d.ybin], d.pos).to_string())
# 挟み込みの中での位置 s = (η_eff-η_lo)/(η_hi-η_lo)
d["s"] = (d.eta_eff - d.eta_lo) / (d.eta_hi - d.eta_lo)
print(d.groupby(["grp", "ybin"], observed=True).agg(med_s=("s", "median"), med_ratio_lo=("eta_eff", lambda x: np.median(x / d.loc[x.index, "eta_lo"])), n=("s", "size")).round(2).to_string())

print("\n=== 実測最適 nb での y = p/P ===")
opt = d.loc[d.groupby(["config", "size"]).G.idxmax()]
print(opt.groupby("grp").y.describe().round(3).to_string())
print(opt[["label", "p", "size", "nb", "N", "y", "eta_eff", "eta_lo", "eta_hi"]].round(3).to_string(index=False))

print("\n=== B. η の形を変えた予測（57条件、予測 nb での性能比） ===")
PRED, RNG = [], []
def tq(q):
    if np.isinf(q): return d.t1 * np.maximum(1, d.y)
    return d.t1 * (1 + d.y**q) ** (1 / q)
def ev(t, name):
    r = pd.DataFrame([dict(config=c, p=g.p.iloc[0], **x) for c, g in d.assign(t=t).groupby("config") for x in perf_at_argmin(g, g.t)])
    bias = np.median(np.log2(r.nb_pred / r.nb_opt))
    print(f"{name:42s} 全57 {summ(r.perf)} | p>=24 {summ(r[r.p>=24].perf)} | p<=12 {summ(r[r.p<=12].perf)} | bias {bias:+.2f}")
    PRED.append(r.assign(form=name)); return r
def fit_a(mask, t0):
    f = lambda a: ((np.log(t0[mask] + a * d.p[mask] * d.tasks[mask] * 1e-6) - np.log(d.t_obs[mask])) ** 2).groupby(d.config[mask]).mean().mean()
    return minimize_scalar(f, bounds=(0, 2), method="bounded").x
def ev_tau(t0, name):
    rows = []
    for c, g in d.groupby("config"):
        a = fit_a(d.config != c, t0)
        rows += [dict(config=c, p=g.p.iloc[0], a=a, **x) for x in perf_at_argmin(g, t0[g.index] + a * g.p * g.tasks * 1e-6)]
    r = pd.DataFrame(rows)
    bias = np.median(np.log2(r.nb_pred / r.nb_opt))
    print(f"{name:42s} 全57 {summ(r.perf)} | p>=24 {summ(r[r.p>=24].perf)} | p<=12 {summ(r[r.p<=12].perf)} | bias {bias:+.2f} a={r.a.min():.3f}-{r.a.max():.3f}")
    PRED.append(r.assign(form=name)); return r
for q in (1, 1.5, 2, 4, np.inf):
    ev(tq(q), f"q={q} (τなし)")
for q in (1, 1.5, 2, 4, np.inf):
    ev_tau(tq(q), f"q={q} + τ=a·p (LOAO)")

print("\n=== C. 最適 nb が必ず入る区間（下限の時間 ≤ 上限の時間の最小） ===")
def interval(t_lo, t_hi, name, tol=1.0):
    rows = []
    for (c, s), g in d.assign(t_lo=t_lo, t_hi=t_hi).groupby(["config", "size"]):
        keep = g.t_lo <= g.t_hi.min() * tol
        nbopt = g.nb[g.G.idxmax()]
        band = g.G >= 0.95 * g.G.max()
        rows.append(dict(config=c, p=g.p.iloc[0], size=s, lo=g.nb[keep].min(), hi=g.nb[keep].max(), nb_opt=nbopt,
                         hit=bool(keep[g.G.idxmax()]), frac=keep.mean(), best_in=g.G[keep].max() / g.G.max(),
                         band_cover=(keep & band).sum() / band.sum()))
    r = pd.DataFrame(rows)
    print(f"{name:34s} 最適を含む {r.hit.sum()}/{len(r)}  区間内の最高/全体最高: 平均 {100*r.best_in.mean():.1f} 最低 {100*r.best_in.min():.1f}  残す nb の割合 平均 {100*r.frac.mean():.0f}%  (p>=24: 含む {r[r.p>=24].hit.sum()}/10, 割合 {100*r[r.p>=24].frac.mean():.0f}%)")
    RNG.append(dict(kind="挟み込み", name=name, theta=np.nan, opt_in_range=int(r.hit.sum()), n=len(r), best_in_range_mean=r.best_in.mean(), best_in_range_min=r.best_in.min(), frac_nb_kept=r.frac.mean(), frac_nb_kept_p24=r[r.p>=24].frac.mean()))
    return r
tl, th = tq(np.inf), tq(1)
r0 = interval(tl, th, "τなし")
a = 0.092
tt = a * d.p * d.tasks * 1e-6
r1 = interval(tl + tt, th + tt, "τ=0.092·p を両方に足す")
r2 = interval(tl, th + tt, "下限はτなし、上限だけτ（安全側）")
print(r2[~r2.hit][["config", "size", "lo", "hi", "nb_opt", "best_in"]].to_string(index=False))
print(r1[~r1.hit][["config", "size", "lo", "hi", "nb_opt", "best_in"]].to_string(index=False))
print(r1[["config","p","size","lo","hi","nb_opt","frac","best_in"]].round(2).to_string(index=False))

print("\n=== D. 比較：しきい値つきの範囲 {nb : 予測性能 ≥ θ·max} を同じデータで ===")
def thr(t, name, th):
    rows = []
    for (c, s), g in d.assign(t=t).groupby(["config", "size"]):
        keep = g.t.min() / g.t >= th
        rows.append(dict(p=g.p.iloc[0], hit=bool(keep[g.G.idxmax()]), frac=keep.mean(), best_in=g.G[keep].max() / g.G.max()))
    r = pd.DataFrame(rows)
    print(f"{name:30s} θ={th}: 最適を含む {r.hit.sum()}/57  区間内最高/全体最高 最低 {100*r.best_in.min():.1f}  残す割合 {100*r.frac.mean():.0f}% (p>=24 {100*r[r.p>=24].frac.mean():.0f}%)")
    RNG.append(dict(kind="しきい値", name=name, theta=th, opt_in_range=int(r.hit.sum()), n=len(r), best_in_range_mean=r.best_in.mean(), best_in_range_min=r.best_in.min(), frac_nb_kept=r.frac.mean(), frac_nb_kept_p24=r[r.p>=24].frac.mean()))
for th_ in (0.92, 0.85, 0.80):
    thr(tq(1), "上限のみ(τなし)", th_)
    thr(tq(1) + tt, "上限+τ", th_)
print("\n区間の端の内訳（τ を両方に足した場合）: 上端が格子の上限 512 に当たる条件数", (r1.hi == 512).sum(), "/57")
print("p別 残す割合:", r1.groupby("p").frac.mean().round(2).to_dict())
print("size別 残す割合:", r1.groupby("size").frac.mean().round(2).to_dict())

DATA = OUT / "data"
d[["config", "label", "p", "size", "nb", "N", "y", "G", "eta_eff", "eta_lo", "eta_hi", "pos", "s"]].to_csv(DATA / "eta_position.csv", index=False, float_format="%.4g")
P = pd.concat(PRED); P.to_csv(DATA / "eta_forms_predictions.csv", index=False, float_format="%.4g")
P.groupby("form", sort=False).apply(lambda r: pd.Series(dict(mean=r.perf.mean(), min=r.perf.min(), n_ge95=(r.perf >= 0.95).sum(),
    mean_p24=r[r.p >= 24].perf.mean(), min_p24=r[r.p >= 24].perf.min(), mean_p12=r[r.p <= 12].perf.mean(),
    bias_log2=np.median(np.log2(r.nb_pred / r.nb_opt))))).reset_index().to_csv(DATA / "eta_forms_summary.csv", index=False, float_format="%.4g")
pd.DataFrame(RNG).to_csv(DATA / "range_variants.csv", index=False, float_format="%.4g")
