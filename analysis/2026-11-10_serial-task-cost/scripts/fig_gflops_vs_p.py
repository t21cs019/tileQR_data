"""
同じ nb で、コア数 p と性能（GFlops）の関係を見る。size ごとに1枚、nb ごとに1本。

  p ≤ 64 の13構成: 各 nb で ib を振った中の最高（../2026-10-27_gen4-kernel-term/data/eta_eff.csv の G）
  p = 192（不老・弐）: スレッド固定の A/B テストの「固定あり」5回の中央値。ib = 32 だけ（data/bind_ab_time.csv）
同じ p に複数の機種があるとき（p = 4 と 6）、線は中央値を通し、点は機種ごとに打つ。

出力: fig_gflops_vs_p.png、data/gflops_vs_p.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
DATA = OUT / "data"
sys.path.insert(0, str(OUT.parent / "2026-10-27_gen4-kernel-term" / "scripts"))

SIZES = [2048, 4096, 8192]
NBS = [64, 128, 192, 256, 384]
# nb は順序のある量なので、1つの色相の明→暗（dataviz の青の 250・350・450・550・700）
COLORS = dict(zip(NBS, ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]))
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"


def load():
    e = pd.read_csv(OUT.parent / "2026-10-27_gen4-kernel-term" / "data" / "eta_eff.csv")
    a = e[e["size"].isin(SIZES) & e.nb.isin(NBS)][["label", "p", "size", "nb", "G"]].assign(source="sweep（ib は最高）")
    b = pd.read_csv(DATA / "bind_ab_time.csv")
    b = b[b.machine == "flow"].rename(columns={"G_close": "G"})[["p", "size", "nb", "G"]]
    b = b.assign(label="EPYC9965（不老・弐）", source="A/B 固定あり（ib = 32）")
    d = pd.concat([a, b], ignore_index=True)
    d["G_per_core"] = d.G / d.p
    return d.sort_values(["size", "nb", "p", "label"])


def main():
    from common27 import jp_font
    jp_font()
    d = load()
    d.to_csv(DATA / "gflops_vs_p.csv", index=False, float_format="%.5g")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), dpi=200, layout="constrained", sharey=True)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, size in zip(axes, SIZES):
        ax.set_facecolor("#fcfcfb")
        s = d[d["size"] == size]
        ends = {}
        for nb in NBS:
            t = s[s.nb == nb]
            med = t.groupby("p").G.median()
            ax.plot(med.index, med.values, color=COLORS[nb], lw=2, zorder=3, label=f"nb = {nb}")
            ax.scatter(t.p, t.G, s=34, color=COLORS[nb], edgecolor="#fcfcfb", linewidth=1.2, zorder=4)
            ends[nb] = med.values[-1]
        # 右端のラベル。重ならないように、下から順に log 軸で 13% 以上あける
        y_prev = 0
        for nb, y in sorted(ends.items(), key=lambda kv: kv[1]):
            y_lab = max(y, y_prev * 1.13)
            ax.annotate(f"{nb}", (192, y), xytext=(225, y_lab), textcoords="data", va="center", fontsize=9, color=INK)
            y_prev = y_lab
        # 目安：コア数に比例して速くなる線（p = 4 の nb = 384 を通る）
        ref = s[(s.nb == 384) & (s.p == 4)].G.median()
        ax.plot([2, 64], [ref * 2 / 4, ref * 64 / 4], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
        ax.annotate("コア数に比例", (20, ref * 20 / 4), xytext=(-4, 8), textcoords="offset points", ha="right",
                    fontsize=9, color=MUTED, rotation=38)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([2, 4, 6, 8, 12, 32, 64, 192])
        ax.set_xticklabels(["2", "4", "6", "8", "12", "32", "64", "192"])
        ax.minorticks_off()
        ax.set_xlim(1.7, 300)
        ax.set_ylim(10, 3000)
        ax.set_title(f"size {size}", fontsize=12, color=INK)
        ax.set_xlabel("物理コア数 p（32 = EPYC 7543、64 = EPYC 7702、192 = EPYC 9965）", fontsize=9.5)
        ax.grid(color=GRID, lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color("#c3c2b7")
        ax.tick_params(colors="#52514e")
    axes[0].set_ylabel("タイル QR 分解の性能 [GFlops]")
    axes[0].set_yticks([10, 20, 50, 100, 200, 500, 1000, 2000])
    axes[0].set_yticklabels(["10", "20", "50", "100", "200", "500", "1000", "2000"])
    axes[0].legend(loc="upper left", fontsize=9.5, frameon=False, title="タイルサイズ")
    fig.suptitle("同じ nb でコア数を増やしたときの性能：小さい nb は、コアが多いほど遅くなる", fontsize=13, color=INK)
    fig.savefig(OUT / "fig_gflops_vs_p.png")

    pv = d.groupby(["size", "nb", "p"]).G.median().unstack("p")
    print(pv.round(0).to_string())


if __name__ == "__main__":
    main()
