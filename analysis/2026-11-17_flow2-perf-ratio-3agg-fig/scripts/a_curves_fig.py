"""a. 図A：不老・弐の GFlops–nb 曲線を size ごとに 2×2 で描き、3水準（速い水準・遅い水準だけ・5回の平均）の線と、
予測の最適 nb（理論値の c = √7.5、k = 2、β = 124、ib = nb/8）の縦の破線を入れる。

値は 2026-11-17_flow2-perf-ratio-3agg の data/a_curves.csv、予測の nb は同 data/b_summary.csv の nb_pred をそのまま使う。
出力：fig_a_curves.png（16:9）、data/a_pred_nb.csv（パネルに書いた予測 nb と実測の最適 nb）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from common import AGG_COLORS, AGGS, BG, DATA, OUT, SIZES, curves, setup_plot, summary  # noqa: E402


def main():
    c, S = curves(), summary()
    nbp = S[S["agg"] == "fast"].set_index("size").nb_pred
    assert (S.groupby("size").nb_pred.nunique() == 1).all()        # 予測 nb は集計によらない
    rows = []
    plt = setup_plot()
    fig, axs = plt.subplots(2, 2, figsize=(12.8, 7.2), facecolor=BG)
    for ax, s in zip(axs.flat, SIZES):
        ax.set_facecolor(BG)
        g = c[c["size"] == s].sort_values("nb")
        for agg, lab in AGGS.items():
            ax.plot(g.nb, g[agg], color=AGG_COLORS[agg], lw=1.3, label=lab)
        Ss = S[S["size"] == s].set_index("agg")
        ax.axvline(nbp[s], color="#52514e", ls="--", lw=1.1, label="予測の最適 nb（理論値の c, k、β = 124）")
        ymax = g[list(AGGS)].max().max()
        ax.annotate(f"予測 nb = {nbp[s]}", (nbp[s], ymax * 0.96), xytext=(4, 0), textcoords="offset points",
                    fontsize=9, color="#52514e", va="top")
        ax.set_title(f"size {s}（実測の最適 nb：速い {Ss.nb_obs['fast']}／遅い {Ss.nb_obs['slow']}／平均 {Ss.nb_obs['mean']}）",
                     fontsize=10.5, loc="left")
        ax.set_xlim(0, 520)
        ax.set_ylim(0, ymax * 1.08)
        ax.set_xlabel("nb", fontsize=9)
        ax.set_ylabel("GFlops（ib について最大）", fontsize=9)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        ax.grid(color="#e6e5e1", lw=0.8)
        ax.set_axisbelow(True)
        rows.append(dict(size=s, nb_pred=int(nbp[s]), **{f"nb_obs_{a}": int(Ss.nb_obs[a]) for a in AGGS}))
        if s == 8192:
            ax.text(0.98, 0.04, "size 8192 では速い水準と遅い水準が分かれていない\n"
                    "（2026-11-10 report.md C 節）。「遅い水準だけ」は\n実行を ex > 6 ms で機械的に分けた値",
                    transform=ax.transAxes, ha="right", va="bottom", multialignment="left", fontsize=8.5, color="#b0302a",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#e6c3c0"))
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=9.5, loc="upper right", ncol=4, bbox_to_anchor=(0.995, 0.995))
    fig.suptitle("不老・弐（EPYC 9965、p = 192）の QR：集計3通りの曲線と予測 nb",
                 fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT / "fig_a_curves.png", dpi=150, facecolor=fig.get_facecolor())
    R = pd.DataFrame(rows)
    R.to_csv(DATA / "a_pred_nb.csv", index=False)
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
