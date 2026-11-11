"""
「モデルより余分な時間」が何に比例するかを、原因の候補ごとの式で比べる。

  時間 = t_model / r0 + 係数 × 項        （r0 は nb によらない一様な係数。どの式にも入れる）

  項                 意味する原因
  tasks（∝ N³）      タスク1個ごとの時間（タスクの生成、キューのロックなど）
  tasks·nb²          タスクが動かすメモリの量に比例する時間（メモリ帯域、キャッシュへの読み込み。β が大きいのと同じ形）
  D = 30N − 28       クリティカルパスの上の遅れ（依存が解けてから次のタスクが始まるまでの待ち）
  N²                 タイル1枚ごと、またはパネルのタスク1個ごとの時間
  size²              行列全体に1回かかる時間（タイル配置へのコピー、メモリの確保）。nb によらない

係数と r0 を構成ごとに、全サイズ・全 nb の実測時間に当てはめる（log の二乗誤差、インサンプル）。
比べるのは、当てはめの誤差（rms）と、予測時間が最小の nb での性能比。

出力: data/hypotheses_fit.csv（構成 × 式）、data/hypotheses_perf.csv（条件 × 式）
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from common10 import DATA, load_s1, perf_at_argmin, summ

TERMS = {
    "tasks": lambda g: g.tasks * 1e-6,                # 係数の単位: µs／タスク
    "tasks·nb²": lambda g: g.tasks * g.nb**2 * 8e-9,  # 秒／GB（タスク1個がタイル1枚分を動かすとして）
    "D": lambda g: g.D * 1e-6,                        # µs／クリティカルパスの重み1
    "N²": lambda g: g.N**2 * 1e-6,                    # µs／タイル
    "size²": lambda g: g["size"] ** 2 * 8e-9,         # 秒／GB（行列1枚分）
}
MODELS = [[], ["tasks"], ["tasks·nb²"], ["D"], ["N²"], ["size²"], ["tasks", "tasks·nb²"], ["tasks", "D"]]


def fit(g, terms):
    cols = [TERMS[t](g).to_numpy() for t in terms]
    tm, lo = g.t_model.to_numpy(), np.log(g.t_obs.to_numpy())

    def pred(par):
        t = tm / abs(par[0])
        for a, c in zip(par[1:], cols):
            t = t + abs(a) * c
        return t

    def loss(par):
        return 1e9 if abs(par[0]) < 0.05 else float(np.mean((np.log(pred(par)) - lo) ** 2))

    best = min((minimize(loss, [r] + [s] * len(cols), method="Nelder-Mead",
                         options=dict(maxiter=6000, xatol=1e-6, fatol=1e-10))
                for r in (0.6, 0.8, 1.0, 1.2) for s in (0.01, 0.3, 3, 30)), key=lambda r: r.fun)
    return np.abs(best.x), best.fun**0.5, pred(best.x)


def main():
    e = load_s1()
    fits, perfs = [], []
    for (config, label), g in e.groupby(["config", "label"]):
        for terms in MODELS:
            name = " + ".join(terms) or "r0 だけ"
            par, rms, t_pred = fit(g, terms)
            row = dict(label=label, p=g.p.iloc[0], model=name, rms_log=rms, r0=par[0])
            row.update({f"coef_{t}": v for t, v in zip(terms, par[1:])})
            fits.append(row)
            perfs += [dict(label=label, p=g.p.iloc[0], model=name, **r) for r in perf_at_argmin(g, t_pred)]
    fits, perfs = pd.DataFrame(fits), pd.DataFrame(perfs)
    fits.to_csv(DATA / "hypotheses_fit.csv", index=False, float_format="%.4g")
    perfs.to_csv(DATA / "hypotheses_perf.csv", index=False, float_format="%.4g")

    for name in fits.model.unique():
        f, q = fits[fits.model == name], perfs[perfs.model == name]
        print(f"{name:20s} p≥24: rms {f[f.p >= 24].rms_log.mean():.3f}  {summ(q[q.p >= 24].perf)}"
              f" ｜ p≤12: rms {f[f.p <= 12].rms_log.mean():.3f}  {summ(q[q.p <= 12].perf)}")
    print(fits[fits.p >= 12].drop(columns="p").to_string(index=False, float_format="%.3g"))


if __name__ == "__main__":
    main()
