"""
実測のタイル QR の性能曲線に、当てはめなしのモデル p·A_k·E_k(nb)·η理論(nb) を重ねる（2026-10-28 ゼミのスライド用）。
A_k, β_k は単体 DTSMQR から、η は c = √7.5, k = 2。どこがモデルで説明できていないかを見る。

入力: data/eta_eff.csv（eta_eff.py の出力）
出力: fig_model_gap.png
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common27 import DATA, OUT, jp_font

PANELS = [("i5-8500", 4096, "p ≤ 12 の例"), ("EPYC7543", 2048, "多コア"), ("EPYC7702 s1", 2048, "多コア")]


def main():
    jp_font()
    e = pd.read_csv(DATA / "eta_eff.csv")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), dpi=200, layout="constrained")
    for ax, (label, size, note) in zip(axes, PANELS):
        d = e[(e.label == label) & (e["size"] == size)].sort_values("nb")
        model = d.p * d.A_k * d.nb / (d.nb + d.beta_k) * d.eta_th
        ax.plot(d.nb, d.G, color="#2a6fdb", lw=2, label="実測")
        ax.plot(d.nb, model, color="#e0601b", lw=2, ls="--", label="モデル（当てはめなし）")
        i_m, i_p = d.G.idxmax(), model.idxmax()
        ax.plot(d.nb[i_m], d.G[i_m], "o", color="#2a6fdb", ms=8)
        ax.plot(d.nb[i_p], model[i_p], "^", color="#e0601b", ms=9)
        ax.annotate(f"実測の最適 nb = {d.nb[i_m]:.0f}", (d.nb[i_m], d.G[i_m]), xytext=(6, -22),
                    textcoords="offset points", color="#2a6fdb", fontsize=10,
                    bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
        ax.annotate(f"予測 nb = {d.nb[i_p]:.0f}", (d.nb[i_p], model[i_p]), xytext=(8, 6),
                    textcoords="offset points", color="#e0601b", fontsize=10,
                    bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
        if d.p.iloc[0] >= 24:
            small = d[d.nb <= d.nb[i_m]]
            ax.fill_between(small.nb, small.G, model[small.index], color="#e0601b", alpha=0.12, lw=0)
            ax.text(0.97, 0.95, "小さい nb ほど\n実測がモデルより低い", transform=ax.transAxes, ha="right",
                    va="top", color="#b04a10", fontsize=12)
        ax.set_title(f"{label.replace(' s1', '')}（p = {d.p.iloc[0]}）size {size}　{note}", fontsize=12)
        ax.set_xlabel("nb")
        ax.set_ylabel("タイル QR 分解の性能 [GFlops]")
        ax.set_xlim(32, 512)
        ax.set_ylim(0, model.max() * 1.12)
        ax.grid(alpha=0.3)
    axes[0].legend(loc="lower right", fontsize=10)
    fig.savefig(OUT / "fig_model_gap.png")


if __name__ == "__main__":
    main()
