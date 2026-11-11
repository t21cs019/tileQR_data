"""Brent の定理の上限・下限で作る nb の探索範囲 B を、研究室の EPYC 7543（p = 32）の性能曲線に重ねる。

11-11 のゼミのスライド（構成案 p.15）用。新しい計算の方法は入れていない：
analysis/2026-11-10_brent-search-range/scripts/range_two_ways.py の prep・run(B) と同じ式を、同じデータ
（serial-task-cost/scripts/common10.load_s1 = 2026-10-27_gen4-kernel-term/data/eta_eff.csv）に当てて描くだけ。
  y = p·D/W（W = 4N³、D = 30N − 28、N = size/nb）、E_カーネル = nb/(nb+β_k)
  時間の上限での予測（いまのモデル）  p·A_k·E_カーネル·1/(1 + y)
  時間の下限での予測                  p·A_k·E_カーネル·min(1, 1/y)
  範囲 B：下限での予測 ≥ 上限での予測の最大、となる nb
出力：../fig_range_epyc7543.png、../fig_range_epyc7543_time.png（縦軸を時間にした版。どちらをスライドに使うかは未定）、../data/range_epyc7543.csv（size ごとの範囲。search_ranges.csv の B と一致を確かめる）
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
A = OUT.parent
sys.path.insert(0, str(A / "2026-11-10_serial-task-cost/scripts"))
from common10 import load_s1  # noqa: E402

CFG = "epyc_s1_smt-off"
SIZES = [1024, 2048, 4096, 8192]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
C_MEAS, C_LO, C_HI, C_RANGE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"


def main():
    d = load_s1()
    d = d[(d.config == CFG) & d["size"].isin(SIZES)].copy()
    d["y"] = d.p * d.D / (4 * d.N**3)
    d["E"] = d.nb / (d.nb + d.beta_k)
    d["G_lo"] = d.p * d.A_k * d.E / (1 + d.y)
    d["G_hi"] = d.p * d.A_k * d.E * np.minimum(1, 1 / d.y)

    ref = pd.read_csv(A / "2026-11-10_brent-search-range/data/search_ranges.csv")
    ref = ref[(ref.config == CFG) & (ref.range == "B")].drop_duplicates("size").set_index("size")
    rows = []
    for s, g in d.groupby("size"):
        keep = g.G_hi >= g.G_lo.max()
        lo, hi = int(g.nb[keep].min()), int(g.nb[keep].max())
        i = g.G.idxmax()
        rows.append(dict(size=s, lo=lo, hi=hi, nb_opt=int(g.nb[i]), frac=keep.mean(),
                         best_in=g.G[keep].max() / g.G.max(), ref_lo=int(ref.loc[s, "lo"]), ref_hi=int(ref.loc[s, "hi"])))
    r = pd.DataFrame(rows)
    print(r.to_string(index=False))
    assert (r.lo == r.ref_lo).all() and (r.hi == r.ref_hi).all(), "search_ranges.csv の範囲 B と一致しない"
    r.to_csv(OUT / "data/range_epyc7543.csv", index=False, float_format="%.4f")

    import matplotlib
    import matplotlib.ticker
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), facecolor="#fcfcfb")
    for ax, s in zip(axes, SIZES):
        g = d[d["size"] == s].sort_values("nb")
        rr = r[r["size"] == s].iloc[0]
        ax.set_facecolor("#fcfcfb")
        ax.axvspan(rr.lo, rr.hi, color=C_RANGE, alpha=0.18, lw=0)
        ax.plot(g.nb, g.G_hi, color=C_HI, lw=2, ls="--", label="時間の下限での予測")
        ax.plot(g.nb, g.G_lo, color=C_LO, lw=2, ls="--", label="時間の上限での予測（いまのモデル）")
        ax.axhline(g.G_lo.max(), color=C_LO, lw=0.8, ls=":")
        ax.plot(g.nb, g.G, color=C_MEAS, lw=2.2, label="タイル QR の性能（実測）")
        top = g.loc[g.G.idxmax()]
        ax.plot(top.nb, top.G, "o", ms=7, color=C_MEAS, mec="#fcfcfb", mew=2, zorder=5)
        ax.set_title(f"size {s}：範囲 B は nb {int(rr.lo)}〜{int(rr.hi)}（最適 {int(rr.nb_opt)}）", fontsize=11, color=INK, loc="left")
        ax.set_xlim(32, 512)
        ax.set_xticks([32, 128, 256, 384, 512])
        ax.set_ylim(0, None)
        ax.set_xlabel("nb", color=INK)
        ax.grid(True, color=GRID, lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=INK2)
    axes[0].set_ylabel("GFlops", color=INK)
    h, l = axes[0].get_legend_handles_labels()
    h.append(plt.Rectangle((0, 0), 1, 1, color=C_RANGE, alpha=0.3)); l.append("範囲 B（残す nb）")
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=11)
    fig.suptitle("研究室の EPYC 7543（p = 32）：下限での予測が、上限での予測の最大（点線）に届かない nb を捨てる",
                 fontsize=12, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(OUT / "fig_range_epyc7543.png", dpi=150, facecolor=fig.get_facecolor())

    # 縦軸を時間にした版：時間 = QR の演算量 ÷ 性能（演算量は size だけで決まるので、性能の図を上下に裏返したものと同じ）
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), facecolor="#fcfcfb")
    for ax, s in zip(axes, SIZES):
        g = d[d["size"] == s].sort_values("nb")
        rr = r[r["size"] == s].iloc[0]
        fl = 4 / 3 * s**3                       # QR の演算量（m = n）の主要項
        ms = lambda G: fl / (G * 1e9) * 1e3
        ax.set_facecolor("#fcfcfb")
        ax.axvspan(rr.lo, rr.hi, color=C_RANGE, alpha=0.18, lw=0)
        ax.plot(g.nb, ms(g.G_lo), color=C_LO, lw=2, ls="--", label="時間の上限（いまのモデル）")
        ax.plot(g.nb, ms(g.G_hi), color=C_HI, lw=2, ls="--", label="時間の下限")
        ax.axhline(ms(g.G_lo.max()), color=C_LO, lw=0.8, ls=":")
        ax.plot(g.nb, ms(g.G), color=C_MEAS, lw=2.2, label="タイル QR の計算時間（実測）")
        top = g.loc[g.G.idxmax()]
        ax.plot(top.nb, ms(top.G), "o", ms=7, color=C_MEAS, mec="#fcfcfb", mew=2, zorder=5)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}" if str(f"{v:g}")[0] in "25" else ""))
        ax.set_title(f"size {s}：範囲 B は nb {int(rr.lo)}〜{int(rr.hi)}（最適 {int(rr.nb_opt)}）", fontsize=11, color=INK, loc="left")
        ax.set_xlim(32, 512)
        ax.set_xticks([32, 128, 256, 384, 512])
        ax.set_xlabel("nb", color=INK)
        ax.grid(True, color=GRID, lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("計算時間 [ms]（対数）", color=INK)
    h, l = axes[0].get_legend_handles_labels()
    h.append(plt.Rectangle((0, 0), 1, 1, color=C_RANGE, alpha=0.3)); l.append("範囲 B（残す nb）")
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=11)
    fig.suptitle("研究室の EPYC 7543（p = 32）：時間の下限が、時間の上限の最小（点線）より大きい nb を捨てる",
                 fontsize=12, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(OUT / "fig_range_epyc7543_time.png", dpi=150, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
