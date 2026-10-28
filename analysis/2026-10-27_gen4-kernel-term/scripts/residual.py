"""
R = η_eff / η_理論 を nb の関数として見る。η_理論 は c=√7.5, k=2。
R が size に依らず nb だけの関数なら、欠けているのは nb の項（E 側か、新しい項）。

1構成ずつ R(nb) = r0 / (1 + (ν/nb)^q) をフィットし、q を見る。
  q ≈ 1 … E と同じ形（転送量 / 演算量。β が大きくなったのと同じ）
  q ≈ 3 … タスク1個あたりの固定オーバーヘッド（タスクの演算量 ∝ nb³）
フィットは nb ≥ 64（単体 E のフィット範囲）かつ size ≥ 2048、η_理論 ≥ 0.3 の点。
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from common27 import DATA, OUT, jp_font


def fit_R(nb, R, q=None):
    def f(z):
        r0, lnu = z[0], z[1]
        qq = q if q is not None else z[2]
        return np.log(r0 / (1 + (np.exp(lnu) / nb) ** qq)) - np.log(R)
    z0 = [np.median(R[-10:]) if len(R) > 10 else R.max(), np.log(30.0)] + ([2.0] if q is None else [])
    lo = [1e-3, np.log(1.0)] + ([0.3] if q is None else [])
    hi = [5.0, np.log(5000.0)] + ([8.0] if q is None else [])
    r = least_squares(f, z0, bounds=(lo, hi))
    return r.x, float(np.sqrt(np.mean(r.fun**2)))


def main():
    jp_font()
    e = pd.read_csv(DATA / "eta_eff.csv")
    e["R"] = e.eta_eff / e.eta_th
    rows = []
    for cfg, d in e.groupby("config"):
        m = (d.nb >= 64) & (d["size"] >= 2048) & (d.eta_th >= 0.3)
        d = d[m].sort_values("nb")
        nb, R = d.nb.to_numpy(float), d.R.to_numpy(float)
        zq, rq = fit_R(nb, R)
        z1, r1 = fit_R(nb, R, q=1.0)
        z3, r3 = fit_R(nb, R, q=3.0)
        rows.append(dict(label=d.label.iloc[0], p=d.p.iloc[0], n=len(d), q=zq[2], nu_q=np.exp(zq[1]), rms_q=rq,
                         nu_q1=np.exp(z1[1]), rms_q1=r1, nu_q3=np.exp(z3[1]), rms_q3=r3))
    r = pd.DataFrame(rows).sort_values("p", ascending=False)
    r.to_csv(DATA / "residual_fit.csv", index=False, float_format="%.4g")
    pd.set_option("display.width", 200)
    print(r.to_string(index=False, float_format="%.3g"))

    labs = ["EPYC7702 s1", "EPYC7543", "Xeon4214 s1", "i7-6900K", "i5-8500", "R5-7400F", "i3-10100", "i3-7100"]
    fig, axs = plt.subplots(2, 4, figsize=(17, 8))
    for ax, lab in zip(axs.flat, labs):
        d = e[e.label == lab]
        for s, g in d.groupby("size"):
            g = g[g.eta_th >= 0.3]
            ax.plot(g.nb, g.R, ".-", ms=3, lw=0.8, label=f"size {s}")
        ax.set_xscale("log", base=2)
        ax.set_title(f"{lab} (p={d.p.iloc[0]:g})")
        ax.set_xlabel("nb")
        ax.set_ylabel("R = η_eff / η_理論")
        ax.grid(alpha=0.3)
    axs.flat[0].legend(fontsize=8)
    fig.suptitle("η_理論 で割った残り（η_理論 ≥ 0.3 の点）。size に依らず nb で重なれば nb の項が欠けている")
    fig.tight_layout()
    fig.savefig(OUT / "fig_residual_vs_nb.png", dpi=110)


if __name__ == "__main__":
    main()
