"""
τ を機種ごとに当てはめず、全機種共通の定数1つで τ = a·p と置く（r0 は入れない）。

  時間 = W / (p·A_k·E_k(nb)·η理論(nb)) + タスク数 · a · p

a は、1機種を全サイズ丸ごと抜いた残りで当てはめる（LOAO、13フォールド。log 時間の二乗誤差を構成ごとに同じ重みで平均）。
比較のため τ = a·p^b（b も当てはめる）と τ = a·p² も出す。
当てはめに使っていない2ソケットの構成（AOBA-B s2 p = 128、calc s2 p = 24）も、全13機種の a で予測する。

出力: data/tau_universal.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from common10 import DATA, load_all, load_s1, perf_at_argmin, summ


def fit(d, b_fix):
    def loss(par):
        a, b = abs(par[0]), (par[1] if b_fix is None else b_fix)
        err = (np.log(d.t_model + a * d.p**b * d.tasks * 1e-6) - np.log(d.t_obs)) ** 2
        return err.groupby(d.config).mean().mean()

    best = min((minimize(loss, [a0, b0], method="Nelder-Mead") for a0 in (0.02, 0.07, 0.3) for b0 in (0.5, 1.0, 1.5)),
               key=lambda r: r.fun)
    return abs(best.x[0]), (best.x[1] if b_fix is None else b_fix)


def predict(g, a, b, **kw):
    tau = a * g.p.iloc[0] ** b
    th = {r["size"]: r for r in perf_at_argmin(g, g.t_model)}
    return [dict(label=g.label.iloc[0], p=g.p.iloc[0], a=a, b=b, tau_us=tau, nb_theory=th[r["size"]]["nb_pred"],
                 perf_theory=th[r["size"]]["perf"], **r, **kw) for r in perf_at_argmin(g, g.t_model + tau * g.tasks * 1e-6)]


def main():
    s1, al = load_s1(), load_all()
    s2 = al[al.config.isin(["aoba-b_s2_smt-off", "calc_s2_smt-off"])]
    rows = []
    for name, b_fix in {"τ = a·p": 1.0, "τ = a·p^b": None, "τ = a·p²": 2.0}.items():
        a_all, b_all = fit(s1, b_fix)
        for config, g in s1.groupby("config"):
            a, b = fit(s1[s1.config != config], b_fix)
            rows += predict(g, a, b, model=name, scope="LOAO")
        for config, g in s2.groupby("config"):
            g = g.assign(label=g.label + " s2")
            rows += predict(g, a_all, b_all, model=name, scope="2ソケット（当てはめに不使用）")
        r = pd.DataFrame([x for x in rows if x["model"] == name and x["scope"] == "LOAO"])
        print(f"{name}: 全点 a = {a_all:.4f}, b = {b_all:.3f}（フォールド a {r.a.min():.4f}〜{r.a.max():.4f}、b {r.b.min():.2f}〜{r.b.max():.2f}）")
        for sc, k in {"全57": r.p > 0, "p≥24": r.p >= 24, "p≤12": r.p <= 12}.items():
            print(f"   {sc}: {summ(r[k].perf)}（理論値のまま {summ(r[k].perf_theory)}）")
    res = pd.DataFrame(rows)
    res.to_csv(DATA / "tau_universal.csv", index=False, float_format="%.4g")
    cols = ["label", "p", "size", "tau_us", "nb_opt", "nb_theory", "perf_theory", "nb_pred", "perf"]
    print(res[(res.model == "τ = a·p") & ((res.p >= 24) | (res.scope != "LOAO"))][cols].to_string(index=False, float_format="%.3f"))


if __name__ == "__main__":
    main()
