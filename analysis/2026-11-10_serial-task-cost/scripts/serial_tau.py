"""
当てはめなしのモデル（1コアの E × 理論 η）に、タスク数に比例する直列の時間を足す。

  時間 = W / (r0 · p·A_k·E_k(nb)·η理論(nb)) + タスク数 · τ
  W = 4/3·size³、タスク数 = N³/3 + N²/2（N = size/nb）

τ（タスク1個あたりの直列の時間）と r0（一様な係数）を、構成ごとに全サイズ・全 nb の実測時間に
当てはめる（log の二乗誤差、インサンプル）。性能に直すと 1/G = 1/(r0·G_model) + τ/(4·nb³) で、
nb だけで決まる上限 4·nb³/τ が入る。

入力: ../2026-10-27_gen4-kernel-term/data/eta_eff.csv（G は各 nb の最高、A_k・β_k は1コアの DTSMQR）
出力: data/per_task_time.csv   各点の、タスク1個あたりの実測時間と、モデルより余分な時間
      data/tau_fit.csv         構成ごとの τ、r0、当てはめの誤差
      data/tau_predictions.csv 予測 nb と性能比（理論値のまま / τ を足したとき）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

OUT = Path(__file__).resolve().parents[1]
DATA = OUT / "data"
SRC = OUT.parent / "2026-10-27_gen4-kernel-term" / "data" / "eta_eff.csv"


def load():
    e = pd.read_csv(SRC)
    e["W"] = 4 / 3 * e["size"] ** 3
    e["tasks"] = e.N**3 / 3 + e.N**2 / 2
    e["G_model"] = e.p * e.A_k * e.nb / (e.nb + e.beta_k) * e.eta_th
    e["t_obs"] = e.W / e.G / 1e9
    e["t_model"] = e.W / e.G_model / 1e9
    e["us_per_task"] = e.t_obs / e.tasks * 1e6
    e["excess_us_per_task"] = (e.t_obs - e.t_model) / e.tasks * 1e6
    return e


def fit(g):
    def loss(par):
        tau, r0 = par
        if tau < 0 or r0 <= 0:
            return 1e9
        t = g.t_model / r0 + g.tasks * tau * 1e-6
        return float(np.mean((np.log(t) - np.log(g.t_obs)) ** 2))

    best = min((minimize(loss, [t0, r], method="Nelder-Mead") for t0 in (0.1, 1, 5) for r in (0.7, 1.0)),
               key=lambda r: r.fun)
    base = minimize(lambda r: loss([0, r[0]]), [0.8], method="Nelder-Mead")
    return best.x[0], best.x[1], base.fun**0.5, best.fun**0.5


def main():
    e = load()
    cols = ["config", "label", "p", "size", "nb", "N", "G", "G_model", "tasks", "us_per_task", "excess_us_per_task"]
    e[cols].to_csv(DATA / "per_task_time.csv", index=False, float_format="%.5g")

    fits, preds = [], []
    for (config, label), g in e.groupby(["config", "label"]):
        tau, r0, rms0, rms1 = fit(g)
        fits.append(dict(config=config, label=label, p=g.p.iloc[0], tau_us=tau, r0=r0, tau_over_p=tau / g.p.iloc[0],
                         rms_log_r0_only=rms0, rms_log_with_tau=rms1))
        for size, gs in g.groupby("size"):
            gs = gs.set_index("nb")
            nb_th = gs.G_model.idxmax()
            nb_tau = (gs.t_model / r0 + gs.tasks * tau * 1e-6).idxmin()
            preds.append(dict(label=label, p=gs.p.iloc[0], size=size, nb_opt=gs.G.idxmax(), nb_theory=nb_th,
                              perf_theory=gs.G[nb_th] / gs.G.max(), nb_tau=nb_tau, perf_tau=gs.G[nb_tau] / gs.G.max()))
    fits = pd.DataFrame(fits).sort_values("p")
    preds = pd.DataFrame(preds).sort_values(["p", "label", "size"])
    fits.to_csv(DATA / "tau_fit.csv", index=False, float_format="%.4g")
    preds.to_csv(DATA / "tau_predictions.csv", index=False, float_format="%.4g")

    print(fits.to_string(index=False, float_format="%.3f"))
    for sc, k in {"全57": preds.p > 0, "p≥24": preds.p >= 24, "p≤12": preds.p <= 12}.items():
        d = preds[k]
        print(f"{sc}: 理論値 平均 {100 * d.perf_theory.mean():.1f} 最低 {100 * d.perf_theory.min():.1f} "
              f"95%以上 {(d.perf_theory >= 0.95).sum()} ／ τ あり 平均 {100 * d.perf_tau.mean():.1f} "
              f"最低 {100 * d.perf_tau.min():.1f} 95%以上 {(d.perf_tau >= 0.95).sum()}（n = {len(d)}）")
    print(preds[preds.p >= 24].to_string(index=False, float_format="%.3f"))
    ex = e[e.label.isin(["EPYC7702 s1", "EPYC7543"]) & e.nb.isin([32, 64, 128])]
    print(ex.pivot_table(index=["label", "nb"], columns="size", values="excess_us_per_task").round(2).to_string())


if __name__ == "__main__":
    main()
