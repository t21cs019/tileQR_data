"""
η_eff = QR GFlops / (p · A_k · E_k(nb))。A_k, β_k は単体 DTSMQR（threads=1, ib=nb/8 断面）の
フィット値を arch で平均したもの（2026-10-21 common.beta_from_ssrfb と同じ手続き）。
E が多コアでも単体と同じなら、η_eff は N = size/nb（と p）だけの関数になり、
同じ構成の各サイズの曲線が N 軸上で重なる。

出力: data/eta_eff.csv, data/eta_eff_collapse.csv, fig_eta_eff.png
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common27 import C_TH, DATA, K_TH, OUT, TAB, c21, jp_font, load57


def main():
    jp_font()
    df, obs = load57()
    arch, curves = c21.beta_from_ssrfb()
    Ak = curves[curves.used].groupby("arch").agg(A=("A", "mean"), beta=("beta", "mean"))
    arch_of = df.groupby("config")["arch"].first().to_dict()
    rows = []
    for t in TAB.itertuples():
        a = Ak.loc[arch_of[t.config]]
        o = obs[(t.config, t.size)]
        nb = o["nb"]
        Ek = nb / (nb + a.beta)
        N = t.size / nb
        rows.append(pd.DataFrame(dict(config=t.config, label=t.label, p=t.p, size=t.size, nb=nb, N=N,
                                      G=o["G"], A_k=a.A, beta_k=a.beta, eta_eff=o["G"] / (t.p * a.A * Ek),
                                      eta_th=1 / (1 + (C_TH * np.sqrt(t.p) / N) ** K_TH),
                                      eta_brent=1 / (1 + t.p * (30 * N - 34) / (4 * N**3)))))
    e = pd.concat(rows)
    e.to_csv(DATA / "eta_eff.csv", index=False, float_format="%.4g")

    # 重なり具合: 隣り合うサイズで N が重なる区間の log 比（大きいサイズ / 小さいサイズ）
    col = []
    for cfg, d in e.groupby("config"):
        sizes = sorted(d["size"].unique())
        for s1, s2 in zip(sizes[:-1], sizes[1:]):
            a, b = d[d["size"] == s1].sort_values("N"), d[d["size"] == s2].sort_values("N")
            lo, hi = max(a.N.min(), b.N.min()), min(a.N.max(), b.N.max())
            Ng = np.geomspace(lo, hi, 12)
            ra = np.interp(np.log(Ng), np.log(a.N), np.log(a.eta_eff))
            rb = np.interp(np.log(Ng), np.log(b.N), np.log(b.eta_eff))
            col.append(dict(label=d.label.iloc[0], p=d.p.iloc[0], s1=s1, s2=s2, N_lo=lo, N_hi=hi,
                            mean_log2_ratio=np.mean(rb - ra) / np.log(2)))
    col = pd.DataFrame(col).sort_values(["p", "label", "s1"], ascending=[False, True, True])
    col.to_csv(DATA / "eta_eff_collapse.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 200)
    print(col.to_string(index=False, float_format="%.3f"))
    # 大きい N（理論 η≥0.97）での η_eff の水準
    big = e[e.eta_th >= 0.97].groupby(["label", "p", "size"]).eta_eff.agg(["median", "min", "max", "size"])
    print(big.round(3).to_string())

    labs = ["EPYC7702 s1", "EPYC7543", "Xeon4214 s1", "i7-6900K", "i5-8500", "R5-7400F", "i3-10100", "i3-7100"]
    fig, axs = plt.subplots(2, 4, figsize=(17, 8), sharex=False)
    for ax, lab in zip(axs.flat, labs):
        d = e[e.label == lab]
        for s, g in d.groupby("size"):
            ax.plot(g.N, g.eta_eff, ".-", ms=3, lw=0.8, label=f"size {s}")
        Ng = np.geomspace(d.N.min(), d.N.max(), 200)
        p = d.p.iloc[0]
        ax.plot(Ng, 1 / (1 + (C_TH * np.sqrt(p) / Ng) ** K_TH), "k--", lw=1, label="理論 η (√7.5, k=2)")
        ax.set_xscale("log")
        ax.set_title(f"{lab} (p={p:g})")
        ax.set_xlabel("N = size/nb")
        ax.set_ylabel("η_eff = G / (p·A_k·E_k)")
        ax.grid(alpha=0.3)
    axs.flat[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "fig_eta_eff.png", dpi=110)


if __name__ == "__main__":
    main()
