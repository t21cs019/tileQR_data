"""analysis/2026-11-11_flow2-dtsmqr-1core/fig_qr_ratio.png と同じ中身を、η を使わない表記で描き直す（11-11 のスライド p.11 用）。

予測 = p·A·E_カーネル·E_並列、E_カーネル = nb/(nb+β)、E_並列 = 1/(1 + x^k)、x = c·√p·nb/size
p = 192、A = 99.7、β = 123.83、c = √7.5、k = 2（RESULT.md 4節と同じ。クロックの補正なし）
実測は curves.py の curves.csv（速い水準 base と5回の平均。ib について最大）
出力：../fig_flow2_qr_ratio.png、../data/qr_ratio.csv（RESULT.md 4節の表の値と見比べる用）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent / "2026-11-10_flow2-sweep-check/scripts"))
from common import setup_plot  # noqa: E402

P, A, BETA, C, K = 192, 99.7, 123.83, np.sqrt(7.5), 2.0
SIZES = [1024, 2048, 4096, 8192]
COLORS = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#1baf7a", 8192: "#eda100"}


def pred(nb, s):
    return P * A * nb / (nb + BETA) / (1 + (C * np.sqrt(P) * nb / s) ** K)


def main():
    cur = pd.read_csv(OUT / "data/curves.csv")
    cur = cur[cur.series.str.startswith("flow2")].copy()
    cur["pred"] = pred(cur.nb, cur["size"])
    cur["ratio"] = cur.GFlops / cur.pred
    tab = cur[cur.series == "flow2 p=192 base"].pivot(index="size", columns="nb", values="ratio")[[64, 128, 192, 256, 384, 512]]
    print(tab.round(2).to_string())
    cur.to_csv(OUT / "data/qr_ratio.csv", index=False, float_format="%.5g")

    plt = setup_plot()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6), facecolor="#fcfcfb")
    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        ax.grid(True, color="#e6e5e1", lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_xlim(32, 512)
        ax.set_xticks([32, 128, 256, 384, 512])
        ax.set_xlabel("nb")
    for s in SIZES:
        b = cur[(cur.series == "flow2 p=192 base") & (cur["size"] == s)]
        m = cur[(cur.series == "flow2 p=192 mean") & (cur["size"] == s)]
        a1.plot(b.nb, b.ratio, color=COLORS[s], lw=2, label=f"size {s}")
        a1.plot(m.nb, m.ratio, color=COLORS[s], lw=1, ls=":")
        mx = b.GFlops.max()
        a2.plot(b.nb, b.GFlops / mx, color=COLORS[s], lw=2, label=f"size {s} 実測")
        a2.plot(b.nb, b.pred / mx, color=COLORS[s], lw=1.4, ls="--")
    a1.axhline(1, color="#52514e", lw=0.8)
    a1.set_ylim(0, 1.05)
    a1.set_ylabel("実測 ÷ 予測")
    a1.set_title("実測 ÷ 予測（実線：速い水準、点線：5回の平均）", loc="left", fontsize=11)
    a1.legend(frameon=False, fontsize=9, loc="upper left")
    a2.set_yscale("log")
    a2.set_ylabel("実測の最高で割った値（対数）")
    a2.set_title("実測（実線）と予測（破線）", loc="left", fontsize=11)
    fig.suptitle("不老・弐の QR（p = 192）と当てはめなしのモデル（A = 99.7、β = 124、c = √7.5、k = 2）",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT / "fig_flow2_qr_ratio.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
