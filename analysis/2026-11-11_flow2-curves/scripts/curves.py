"""不老・弐・EPYC 7543・EPYC 7702 の nb–GFlops 曲線（ib について最大）を描く。

- 不老・弐（p = 192）：report.md の推奨の集計（速い水準 base、common.add_baseline）。比較用に 5 回の平均も細い点線で
- EPYC 7543（p = 32）・EPYC 7702（AOBA-B 1ソケット、p = 64）：derived/qr_sweep.parquet の 5 回（5 本）の GFlops の平均
出力：../fig_three_epyc.png、../fig_flow2_sizes.png、../data/curves.csv、../data/peaks.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / "analysis/2026-11-10_flow2-sweep-check/scripts"))
from common import add_baseline, flops_dgeqrf, load_all, setup_plot  # noqa: E402

SIZES = [1024, 2048, 4096, 8192]
COLORS = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#1baf7a", 8192: "#eda100"}  # dataviz の既定の順（検証済み）
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def curve_mean(config):
    d = pd.read_parquet(ROOT / "derived/qr_sweep.parquet", columns=["config", "size", "nb", "ib", "GFlops", "source_file"])
    d = d[(d.config == config) & d["size"].isin(SIZES)]
    runs = d.groupby("size").source_file.nunique().to_dict()
    g = d.groupby(["size", "nb", "ib"]).GFlops.mean().groupby(["size", "nb"]).max().reset_index()
    return g, runs


def curve_flow():
    d = add_baseline(load_all())
    p = d.drop_duplicates(["size", "nb", "ib"]).copy()
    p["base_gf"] = flops_dgeqrf(p["size"]) / (p.base * 1e6)
    b = p.groupby(["size", "nb"]).base_gf.max().rename("GFlops").reset_index()
    m = d.groupby(["size", "nb", "ib"]).GFlops.mean().groupby(["size", "nb"]).max().rename("GFlops").reset_index()
    return b, m


def peaks(g):
    rows = []
    for s, x in g.groupby("size"):
        top = x.loc[x.GFlops.idxmax()]
        w = x[x.GFlops >= 0.95 * top.GFlops]
        rows.append(dict(size=s, nb_opt=int(top.nb), GFlops_max=round(top.GFlops, 1), nb95_lo=int(w.nb.min()), nb95_hi=int(w.nb.max())))
    return pd.DataFrame(rows)


def style(ax):
    ax.set_facecolor("#fcfcfb")
    ax.grid(True, color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2)
    ax.set_xlim(32, 512)
    ax.set_xticks([32, 128, 256, 384, 512])
    ax.set_xlabel("nb", color=INK)


def draw(ax, g, label_right=True, lw=2.0):
    for s in SIZES:
        x = g[g["size"] == s]
        if x.empty:
            continue
        ax.plot(x.nb, x.GFlops, color=COLORS[s], lw=lw, label=f"size {s}")
        top = x.loc[x.GFlops.idxmax()]
        ax.plot(top.nb, top.GFlops, "o", ms=7, color=COLORS[s], mec="#fcfcfb", mew=2, zorder=5)
        if label_right:
            last = x.iloc[-1]
            ax.annotate(f"{s}", (last.nb, last.GFlops), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=9, color=INK2)


def main():
    plt = setup_plot()
    e7543, r7543 = curve_mean("epyc_s1_smt-off")
    e7702, r7702 = curve_mean("aoba-b_s1_smt-off")
    fb, fm = curve_flow()

    tabs = []
    for name, g in [("EPYC 7543 p=32 mean", e7543), ("EPYC 7702 p=64 mean", e7702), ("flow2 p=192 base", fb), ("flow2 p=192 mean", fm)]:
        tabs.append(g.assign(series=name))
        print(name); print(peaks(g).to_string(index=False))
    pd.concat(tabs).to_csv(OUT / "data/curves.csv", index=False)
    pd.concat([peaks(g).assign(series=n) for n, g in [("EPYC 7543 p=32 mean", e7543), ("EPYC 7702 p=64 mean", e7702),
               ("flow2 p=192 base", fb), ("flow2 p=192 mean", fm)]]).to_csv(OUT / "data/peaks.csv", index=False)
    print("runs per size:", "7543", r7543, "7702", r7702)

    # 図1：3機種を横に並べる（縦軸は機種ごと、対数）
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), facecolor="#fcfcfb")
    panels = [(axes[0], e7543, "EPYC 7543（研究室）p = 32\n5回の平均"),
              (axes[1], e7702, "EPYC 7702（AOBA-B 1ソケット）p = 64\n5回の平均"),
              (axes[2], fb, "EPYC 9965（不老・弐）p = 192\n速い水準（実線）、5回の平均（点線）")]
    for ax, g, t in panels:
        style(ax)
        draw(ax, g)
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(FixedLocator([1, 3, 10, 30, 100, 300, 1000, 3000]))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_title(t, color=INK, fontsize=11, loc="left")
    for s in SIZES:
        x = fm[fm["size"] == s]
        axes[2].plot(x.nb, x.GFlops, color=COLORS[s], lw=1.0, ls=":")
    axes[0].set_ylabel("GFlops（ib について最大、対数）", color=INK)
    axes[0].legend(loc="lower right", frameon=False, fontsize=9)
    fig.text(0.01, 0.005, "● は各曲線の最高の点。縦軸の範囲は機種ごとに違う。集計の方法が機種で違う（不老・弐は 13〜15 ms の遅れが混ざるため速い水準）",
             fontsize=9, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig_three_epyc.png", dpi=150, facecolor=fig.get_facecolor())

    # 図2：不老・弐だけ、4 size を1枚に（線形）
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor="#fcfcfb")
    style(ax)
    pk = peaks(fb)
    for s in SIZES:
        x = fb[fb["size"] == s]
        r = pk[pk["size"] == s].iloc[0]
        w = x[(x.nb >= r.nb95_lo) & (x.nb <= r.nb95_hi)]
        ax.plot(x.nb, x.GFlops, color=COLORS[s], lw=2.0, label=f"size {s}")
        ax.plot(w.nb, w.GFlops, color=COLORS[s], lw=5.0, alpha=0.35, solid_capstyle="round")
        ax.plot(int(r.nb_opt), r.GFlops_max, "o", ms=8, color=COLORS[s], mec="#fcfcfb", mew=2, zorder=5)
        ax.annotate(f"size {s}：約 {r.GFlops_max:.0f}（nb {int(r.nb95_lo)}〜{int(r.nb95_hi)}）", (int(r.nb_opt), r.GFlops_max),
                    xytext=(-260 if s == 8192 else 8, 10), textcoords="offset points", fontsize=10, color=INK)
    ax.set_ylim(0, 2300)
    ax.set_ylabel("GFlops（速い水準、ib について最大）", color=INK)
    ax.set_title("不老・弐（EPYC 9965、p = 192、固定あり）の性能曲線", color=INK, loc="left")
    ax.legend(loc="upper left", frameon=False)
    fig.text(0.01, 0.01, "太い帯は最高から 5% 以内の nb。● は最高の点", fontsize=9, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig_flow2_sizes.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
