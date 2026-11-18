"""b. 図B：11-11 の p.9 右の図（analysis/2026-11-11_flow2-curves/scripts/ratio.py の fig_flow2_ratio.png）を、
集計3通り（速い水準・遅い水準だけ・5回の平均）それぞれで描く。色・軸・棒の上の数値の書き方は ratio.py と同じ。

性能比 = 実測(予測の最適 nb) ÷ 実測の最大。実測は 2026-11-17_flow2-perf-ratio-3agg の data/a_curves.csv の各列。
モデル（ratio.py と同じ式）：E_カーネル(nb)·E_並列(nb)、E_カーネル = nb/(nb+β)、E_並列 = 1/(1 + (c·√p·nb/size)^k)、
β = 123.83（ib = nb/8）、p = 192。c, k は 理論値（√7.5、2）と 57条件の値（2.590、1.473）。予測 nb は実測の格子の上で最大。

確かめること（assert）：
 1. 理論値の棒が、3agg の RESULT.md「1. 結論」の A = 99.7・β = 124 の表（3桁）と一致し、b_summary.csv の perf とも 5桁（%.5g の保存の精度）で一致
 2. 速い水準・5回の平均の棒（理論値・57条件とも）が、11-11 の data/ratio.csv（base・mean）と 4桁で一致
 3. 速い水準の棒の上の数値（%、整数）が p.9 の 理論値 3・2・3・24、当てはめ 3・3・6・36
出力：fig_b_ratio_{fast,slow,mean}.png（1枚ずつ）、fig_b_ratio_3agg.png（3枚を横に並べたもの）、data/b_ratio.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import AGGS, BG, DATA, OUT, P, ROOT, SIZE_COLORS, SIZES, SRC, curves, setup_plot, summary  # noqa: E402

BETA = 123.83                       # ratio.py と同じ（b_fits.csv の flow2・mean5・ib=nb/8）
MODELS = [("理論値\nc = √7.5、k = 2", np.sqrt(7.5), 2.0),
          ("57条件で当てはめた値\nc = 2.590、k = 1.473", 2.59002, 1.47251)]
P9 = {"理論値": [3, 2, 3, 24], "57条件": [3, 3, 6, 36]}


def ratios() -> pd.DataFrame:
    cur = curves()
    rows = []
    for agg in AGGS:
        for name, c, k in MODELS:
            for s in SIZES:
                g = cur[cur["size"] == s].sort_values("nb")
                nb, obs = g.nb.to_numpy(float), g[agg].to_numpy()
                f = nb / (nb + BETA) / (1 + (c * np.sqrt(P) * nb / s) ** k)
                i = int(np.argmax(f))
                rows.append(dict(agg=agg, model=name.split("\n")[0], size=s, nb_pred=int(nb[i]),
                                 nb_opt=int(nb[np.nanargmax(obs)]), ratio=obs[i] / np.nanmax(obs)))
    return pd.DataFrame(rows)


def result_table() -> pd.DataFrame:
    """3agg の RESULT.md の A = 99.7・β = 124 の表を読む。"""
    txt = (SRC / "RESULT.md").read_text()
    blk = txt.split("**A = 99.7、β = 124")[1].split("**A = 95.0")[0]
    rows = []
    for line in blk.splitlines():
        m = re.match(r"\|\s*(\d{4})\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", line)
        if m:
            s, nbp, f, sl, mn = m.groups()
            rows += [dict(size=int(s), nb_pred=int(nbp), agg=a, ratio_md=v, nd=len(v.split(".")[1]))
                     for a, v in zip(AGGS, (f, sl, mn))]
    T = pd.DataFrame(rows)
    assert len(T) == 12, T
    return T


def check(r: pd.DataFrame):
    th = r[r.model == "理論値"]
    # 1. RESULT.md の表と b_summary.csv
    T = result_table().merge(th, on=["size", "agg"], suffixes=("_md", ""))
    assert (T.nb_pred_md == T.nb_pred).all()
    for _, t in T.iterrows():
        assert f"{t.ratio:.{t.nd}f}" == t.ratio_md, (t["agg"], t["size"], t.ratio, t.ratio_md)
    S = summary().rename(columns={"perf": "ratio_sum"}).merge(th, on=["agg", "size"])
    assert (S.nb_pred_x == S.nb_pred_y).all() and np.allclose(S.ratio_sum, S.ratio, atol=0, rtol=1e-4)   # b_summary.csv は 5桁（%.5g）で保存
    print(f"1. RESULT.md の表 12 値・b_summary.csv の 12 行と一致（b_summary との最大差 {np.abs(S.ratio_sum - S.ratio).max():.1e}）")
    # 2. 11-11 の ratio.csv
    old = pd.read_csv(ROOT / "analysis/2026-11-11_flow2-curves/data/ratio.csv")
    old["agg"] = old.series.map({"flow2 p=192 base": "fast", "flow2 p=192 mean": "mean"})
    old["model"] = old.model.str.split(" ").str[0]
    m = old.merge(r, on=["agg", "model", "size"], suffixes=("_1111", ""))
    assert len(m) == 16, len(m)
    assert (m.nb_pred_1111 == m.nb_pred).all() and (m.nb_opt_1111 == m.nb_opt).all()
    # 4桁の丸め（±5e-5）＋ 3agg と 11-11 の曲線の差（RESULT.md 2節：最大 1e-5）
    assert (np.abs(m.ratio - m.ratio_1111) <= 6e-5).all(), m[["agg", "model", "size", "ratio_1111", "ratio"]]
    print(f"2. 11-11 の ratio.csv（速い水準・5回の平均 × 2モデル × 4 size = 16 行）と 4桁（丸めの幅で）・予測 nb・最適 nb が一致。最大差 {np.abs(m.ratio - m.ratio_1111).max():.1e}")
    # 3. p.9 の数値
    f = r[r["agg"] == "fast"]
    for key, want in P9.items():
        got = [int(f"{100 * v:.0f}") for v in f[f.model.str.startswith(key)].sort_values("size").ratio]
        assert got == want, (key, got, want)
    print("3. 速い水準の棒の数値が p.9 と一致：理論値 3・2・3・24、当てはめ 3・3・6・36")


def draw(ax, b, agg):
    ax.set_facecolor(BG)
    w = 0.19
    for j, (name, _, _) in enumerate(MODELS):
        for i, s in enumerate(SIZES):
            v = 100 * b[(b.model == name.split("\n")[0]) & (b["size"] == s)].ratio.iloc[0]
            x = j + (i - 1.5) * (w + 0.02)
            ax.bar(x, v, w, color=SIZE_COLORS[s], label=f"size {s}" if j == 0 else None)
            ax.annotate(f"{v:.0f}", (x, v), xytext=(0, 2), textcoords="offset points", ha="center", fontsize=8, color="#52514e")
    ax.set_xticks([0, 1], [m[0] for m in MODELS], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_ylabel("性能比 [%]（予測 nb の性能 ÷ 実測の最高）", fontsize=9)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left")


def main():
    r = ratios()
    r.to_csv(DATA / "b_ratio.csv", index=False, float_format="%.5g")
    print(r.assign(pct=(100 * r.ratio).round(1)).to_string(index=False))
    check(r)

    plt = setup_plot()
    for agg, lab in AGGS.items():
        fig, ax = plt.subplots(figsize=(6.4, 4.6), facecolor=BG)
        draw(ax, r[r["agg"] == agg], agg)
        ax.set_title(f"不老・弐（EPYC 9965、p = 192）：実測は{lab}", fontsize=11, loc="left")
        fig.tight_layout()
        fig.savefig(OUT / f"fig_b_ratio_{agg}.png", dpi=150, facecolor=fig.get_facecolor())
        plt.close(fig)

    fig, axs = plt.subplots(1, 3, figsize=(14.4, 4.8), facecolor=BG, sharey=True)
    for ax, (agg, lab) in zip(axs, AGGS.items()):
        draw(ax, r[r["agg"] == agg], agg)
        ax.set_title(f"実測は{lab}", fontsize=11, loc="left")
        if ax is not axs[0]:
            ax.set_ylabel("")
            ax.get_legend().remove()
    fig.suptitle("不老・弐（EPYC 9965、p = 192）：予測 nb の性能比を集計3通りで（β = 124）", fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_b_ratio_3agg.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
