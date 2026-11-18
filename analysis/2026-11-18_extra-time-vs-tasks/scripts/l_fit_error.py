"""l：i 節の c0 + τ·タスク数 の当てはめ線が、nb の範囲ごとにどれだけ当たるか（定義M、機種×size。不老・弐は 5回の平均・c_split の全格子）。
当てはめ: i_c0_tau.py と同じ。y = 余分な時間(M) = t_obs − t_model を、c0 + τ·タスク数 に、重み 1/t_obs の線形最小二乗（Σ((c0 + τ·タスク数 − y)/t_obs)² を最小）で当てはめる。
          余分な時間 ≤ 0 の点も当てはめに含める（除かない）。3通り: all（全点、i 節）／ lt（nb < 予測 nb の点だけ。3 点未満は当てはめ不能）／ ge（nb ≥ 予測 nb の点だけ）。
誤差（点ごと）: (i) 余分な時間の相対誤差 = (当てはめ − 実測の余分)/実測の余分（余分 ≤ 0 の点は除く） 
                (ii) 全体の時間の相対誤差 = (t_model + 当てはめ − t_obs)/t_obs = (当てはめ − 余分)/t_obs（上の最小二乗が最小にしている量そのもの）
範囲: a = nb < 予測 nb、b = nb ≥ 予測 nb、c = 全点、d1 = nb < 外れ始める nb、d2 = nb ≥ 外れ始める nb（h の規則B・±30%・定義M、h_departure.csv。外れなければ d2 は空）
セルごとに n（点数）、RMS、絶対値の中央値、平均（偏り）。
出力: data/l_error_by_range.csv（機種×size×当てはめ×範囲×誤差）, data/l_error_machine.csv（size をまとめた機種ごと）, data/l_c0_tau_3fits.csv, data/l_fit_check.csv"""
import numpy as np, pandas as pd
from gcommon import *

d = pd.read_csv(OUT / "data/g_points.csv")
H = pd.read_csv(OUT / "data/h_departure.csv"); H = H[(H.rule == "B") & (H.tol == 0.3) & (H.definition == "M")]
Ri = pd.read_csv(OUT / "data/i_c0_tau.csv"); Ri = Ri[(Ri.definition == "M") & (Ri.range == "全点")]

def wfit(g):
    w = 1 / g.t_obs.to_numpy(); X = np.c_[np.ones(len(g)), g.tasks]
    coef, *_ = np.linalg.lstsq(X * w[:, None], g.excess_M.to_numpy() * w, rcond=None)
    return coef

def stats(e):
    e = np.asarray(e)
    if len(e) == 0: return dict(n=0, rms=np.nan, median_abs=np.nan, mean=np.nan)
    return dict(n=len(e), rms=float(np.sqrt((e ** 2).mean())), median_abs=float(np.median(np.abs(e))), mean=float(e.mean()))

rows, pts, cf, chk = [], [], [], []
for pn in ORDER:
    for size, g in d[d.panel == pn].groupby("size"):
        g = g.sort_values("nb").reset_index(drop=True)
        dep = H[(H.panel == pn) & (H["size"] == int(size))].nb_dep.iloc[0]
        ranges = {"a: nb < 予測 nb": g.cls == "lt_pred", "b: nb ≥ 予測 nb": g.cls == "ge_pred", "c: 全点": g.nb > 0,
                  "d1: nb < 外れ始める nb": (g.nb < dep) if not np.isnan(dep) else g.nb < 0, "d2: nb ≥ 外れ始める nb": (g.nb >= dep) if not np.isnan(dep) else g.nb < 0}
        sets = {"all": g, "lt": g[g.cls == "lt_pred"], "ge": g[g.cls == "ge_pred"]}
        # i 節との照合
        r = Ri[(Ri.panel == pn) & (Ri["size"] == int(size))].iloc[0]; c_all = wfit(g)
        assert abs(c_all[0] * 1e3 - r.c0_ms) < 1e-4 * max(1, abs(r.c0_ms)) and abs(c_all[1] * 1e6 - r.tau_us) < 1e-4 * abs(r.tau_us)
        chk.append(dict(panel=SHORT[pn], size=int(size), n_fit_all=len(g), n_nonpositive_in_fit=int((g.excess_M <= 0).sum()), c0_ms_i=r.c0_ms, c0_ms_here=c_all[0] * 1e3, tau_us_i=r.tau_us, tau_us_here=c_all[1] * 1e6))
        for fname, fs in sets.items():
            if len(fs) < 3:
                cf.append(dict(machine=SHORT[pn], size=int(size), fit=fname, n_fit=len(fs), c0_ms=np.nan, tau_us=np.nan, note="当てはめ不能（3 点未満）")); continue
            coef = wfit(fs); fit = coef[0] + coef[1] * g.tasks
            cf.append(dict(machine=SHORT[pn], size=int(size), fit=fname, n_fit=len(fs), c0_ms=coef[0] * 1e3, tau_us=coef[1] * 1e6, note=""))
            e_i = (fit - g.excess_M) / g.excess_M; e_ii = (fit - g.excess_M) / g.t_obs
            for rn, m in ranges.items():
                mm = m.to_numpy(); pos = mm & (g.excess_M > 0).to_numpy()
                for kind, e, sel in (("i 余分な時間", e_i, pos), ("ii 全体の時間", e_ii, mm)):
                    s = stats(e[sel]); rows.append(dict(machine=SHORT[pn], size=int(size), fit=fname, range=rn, error=kind, n_in_range=int(mm.sum()), n_nonpositive_excluded=int(mm.sum() - pos.sum()) if kind.startswith("i ") else 0, **s))
                    pts.append(pd.DataFrame(dict(machine=SHORT[pn], fit=fname, range=rn, error=kind, e=np.asarray(e[sel]))))
T = pd.DataFrame(rows); T.to_csv(OUT / "data/l_error_by_range.csv", index=False, float_format="%.4g")
pd.DataFrame(cf).to_csv(OUT / "data/l_c0_tau_3fits.csv", index=False, float_format="%.5g")
pd.DataFrame(chk).to_csv(OUT / "data/l_fit_check.csv", index=False, float_format="%.5g")
P = pd.concat(pts); M = []
for k, g in P.groupby(["machine", "fit", "range", "error"], sort=False):
    M.append(dict(machine=k[0], fit=k[1], range=k[2], error=k[3], **stats(g.e.values)))
M = pd.DataFrame(M); M.to_csv(OUT / "data/l_error_machine.csv", index=False, float_format="%.4g")
pd.set_option("display.width", 250)
print(pd.DataFrame(chk).to_string())
print(M[(M.fit == "all")].pivot_table(index=["machine", "error"], columns="range", values="rms").round(3).to_string())
print(M[(M.fit == "all")].pivot_table(index=["machine", "error"], columns="range", values="mean").round(3).to_string())
print(pd.DataFrame(cf).to_string())
