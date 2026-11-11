"""不老・弐（p = 192）で、当てはめなしのモデルが予測する nb の性能比を出し、棒グラフにする。

モデル：性能 ∝ E_カーネル(nb) · E_並列(nb)、E_カーネル = nb/(nb+β)、E_並列 = 1/(1 + x^k)、x = c·√p·nb/size
  （analysis/2026-10-27_epyc-remeasure/scripts/common.py の predict_nb・eta_x と同じ式。nb は実測の格子の上で最大を取る）
c, k は2通り：
  理論値      c = √7.5、k = 2
  57条件の値  c = 2.59002、k = 1.47251（analysis/2026-10-27_epyc-remeasure/data/fold_constants57.csv の ALL 行。
             不老・弐を含まない、HT 無効・1ソケットの13機種57条件で当てはめた値。11-04 の p.2 の図と同じ当てはめ）
β = 123.83（不老・弐の DTSMQR 1コア、ib = nb/8。analysis/2026-11-11_flow2-dtsmqr-1core/RESULT.md）
性能比 = 実測(予測 nb) ÷ 実測の最大。実測は curves.py と同じ（速い水準 base、ib について最大）。5回の平均でも出す。
出力：../data/ratio.csv、../fig_flow2_ratio.png
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
P, BETA = 192, 123.83
MODELS = [("理論値\nc = √7.5、k = 2", np.sqrt(7.5), 2.0),
          ("57条件で当てはめた値\nc = 2.590、k = 1.473", 2.59002, 1.47251)]
SIZES = [1024, 2048, 4096, 8192]
COLORS = {1024: "#2a78d6", 2048: "#1baf7a", 4096: "#eda100", 8192: "#e87ba4"}   # 11-04 p.2 の図の色の並び


def main():
    import sys
    sys.path.insert(0, str(OUT.parents[0] / "2026-11-10_flow2-sweep-check/scripts"))
    from common import setup_plot
    cur = pd.read_csv(OUT / "data/curves.csv")
    rows = []
    for series in ("flow2 p=192 base", "flow2 p=192 mean"):
        for name, c, k in MODELS:
            for s in SIZES:
                g = cur[(cur.series == series) & (cur["size"] == s)].sort_values("nb")
                nb = g.nb.to_numpy(float)
                f = nb / (nb + BETA) / (1 + (c * np.sqrt(P) * nb / s) ** k)
                i = int(np.argmax(f))
                rows.append(dict(series=series, model=name.replace("\n", " "), size=s, nb_pred=int(nb[i]),
                                 nb_opt=int(nb[g.GFlops.to_numpy().argmax()]),
                                 ratio=g.GFlops.iloc[i] / g.GFlops.max()))
    r = pd.DataFrame(rows)
    r.to_csv(OUT / "data/ratio.csv", index=False, float_format="%.4f")
    print(r.to_string(index=False))

    plt = setup_plot()
    b = r[r.series == "flow2 p=192 base"]
    fig, ax = plt.subplots(figsize=(5.2, 4.6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    w = 0.19
    for j, (name, _, _) in enumerate(MODELS):
        for i, s in enumerate(SIZES):
            v = 100 * b[(b.model == name.replace("\n", " ")) & (b["size"] == s)].ratio.iloc[0]
            x = j + (i - 1.5) * (w + 0.02)
            ax.bar(x, v, w, color=COLORS[s], label=f"size {s}" if j == 0 else None)
            ax.annotate(f"{v:.0f}", (x, v), xytext=(0, 2), textcoords="offset points", ha="center", fontsize=8, color="#52514e")
    ax.set_xticks([0, 1], [m[0] for m in MODELS], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_ylabel("性能比 [%]（予測 nb の性能 ÷ 実測の最高）", fontsize=9)
    ax.set_title("不老・弐（EPYC 9965、p = 192）", fontsize=11, loc="left")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_flow2_ratio.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
