"""不老・弐（p = 192）の QR の性能曲線に、当てはめなしのモデルの予測を重ねる（11-11 のスライドの付録用）。

予測 = p·A·E_カーネル·E_並列、E_カーネル = nb/(nb+β)、E_並列 = 1/(1 + x^k)、x = c·√p·nb/size
A = 99.7、β = 123.83（DTSMQR 1コア）。c, k は ratio.py と同じ2通り（理論値 √7.5・2、57条件の 2.59002・1.47251）
実測は curves.py の速い水準（base、ib について最大）
出力：../fig_flow2_model_curves.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent / "2026-11-10_flow2-sweep-check/scripts"))
from common import setup_plot  # noqa: E402

P, A, BETA = 192, 99.7, 123.83
MODELS = [("予測：理論値（c = √7.5、k = 2）", np.sqrt(7.5), 2.0, "#eb6834", "--"),
          ("予測：57条件の値（c = 2.590、k = 1.473）", 2.59002, 1.47251, "#1baf7a", "--")]
SIZES = [1024, 2048, 4096, 8192]
C_MEAS = "#2a78d6"


def main():
    cur = pd.read_csv(OUT / "data/curves.csv")
    cur = cur[cur.series == "flow2 p=192 base"]
    plt = setup_plot()
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), facecolor="#fcfcfb")
    for ax, s in zip(axes, SIZES):
        g = cur[cur["size"] == s].sort_values("nb")
        nb = g.nb.to_numpy(float)
        ax.set_facecolor("#fcfcfb")
        ax.grid(True, color="#e6e5e1", lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for name, c, k, col, ls in MODELS:
            pr = P * A * nb / (nb + BETA) / (1 + (c * np.sqrt(P) * nb / s) ** k)
            ax.plot(nb, pr, color=col, lw=1.8, ls=ls, label=name)
            i = int(np.argmax(pr))
            ax.plot(nb[i], pr[i], "o", ms=6, color=col, mec="#fcfcfb", mew=1.5, zorder=5)
        ax.plot(nb, g.GFlops, color=C_MEAS, lw=2.2, label="タイル QR の性能（実測、速い水準）")
        j = int(g.GFlops.to_numpy().argmax())
        ax.plot(nb[j], g.GFlops.iloc[j], "o", ms=7, color=C_MEAS, mec="#fcfcfb", mew=2, zorder=6)
        ax.set_yscale("log")
        ax.set_xlim(32, 512)
        ax.set_xticks([32, 128, 256, 384, 512])
        ax.set_xlabel("nb")
        ax.set_title(f"size {s}（実測の最適 nb {int(nb[j])}）", loc="left", fontsize=11)
    axes[0].set_ylabel("GFlops（対数）")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=11)
    fig.suptitle("不老・弐（EPYC 9965、p = 192）の性能曲線と、当てはめなしのモデルの予測（A = 99.7、β = 124）。● は各曲線の最高",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 0.94))
    fig.savefig(OUT / "fig_flow2_model_curves.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
