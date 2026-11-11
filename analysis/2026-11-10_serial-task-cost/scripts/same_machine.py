"""
同じ機械で、コア数（ソケット数）やスレッド数（SMT）だけを変えたときの比較。機種による1コアの速さの違いが入らない。

  1ソケット → 2ソケット（コア数2倍）: AOBA-B（EPYC 7702、64 → 128）、calc（Xeon Silver 4214、12 → 24）
  SMT 無効 → 有効（コア数は同じでスレッド数2倍）: i3-7100、i3-10100、i7-7700、Ryzen 5 7400F

2ソケットは、メモリのチャネルもコア数と一緒に2倍になる。ただしソケットをまたぐ（NUMA の距離が遠い）ことの影響は分けられない。

出力: data/same_machine.csv（size・nb ごとの GFlops と、タスク1個あたりの時間）、fig_same_machine.png
"""

from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common10 import DATA, OUT, load_all

sys.path.insert(0, str(OUT.parent / "2026-10-27_gen4-kernel-term" / "scripts"))

PAIRS = {"aoba-b": "EPYC 7702（AOBA-B）", "calc": "Xeon Silver 4214（calc）"}
COL = {1: "#2a78d6", 2: "#eb6834"}   # dataviz の分類色 1・2（validate_palette.js で確認）
INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
SIZE = 8192


def main():
    from common27 import jp_font
    jp_font()
    a = load_all()
    keep = a[a.machine.isin(["aoba-b", "calc", "i3-7100", "i3-10100", "i7-7700", "ryzen5-7400f"])]
    cols = ["machine", "config", "p", "threads", "size", "nb", "G", "tasks", "us_per_task", "excess_us_per_task"]
    keep[cols].to_csv(DATA / "same_machine.csv", index=False, float_format="%.5g")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=200, layout="constrained")
    fig.patch.set_facecolor(BG)
    for ax, (m, title) in zip(axes, PAIRS.items()):
        ax.set_facecolor(BG)
        d = a[(a.machine == m) & (a["size"] == SIZE) & ~a.smt]
        curves = {s: g.sort_values("nb").set_index("nb").G for s, g in d.groupby("sockets")}
        for s, g in curves.items():
            p = d[d.sockets == s].p.iloc[0]
            ax.plot(g.index, g.values, color=COL[s], lw=2, label=f"{s}ソケット（{p}コア）")
            ax.annotate(f"{p}コア", (g.index[-1], g.values[-1]), xytext=(6, 6 if s == 2 else -10),
                        textcoords="offset points", fontsize=10, color=INK)
        ratio = (curves[2] / curves[1]).dropna()
        cross = ratio[ratio >= 1].index.min()
        ax.axvspan(32, cross, color=COL[2], alpha=0.07, lw=0)
        ax.text(0.30, 0.34, f"nb < {cross} では\nコアを2倍にすると遅くなる\n（nb 32 で {ratio[32]:.2f} 倍、nb 384 で {ratio[384]:.2f} 倍）",
                transform=ax.transAxes, va="top", fontsize=10.5, color=INK)
        ax.set_title(f"{title}　size {SIZE}", fontsize=12, color=INK)
        ax.set_xlabel("nb")
        ax.set_ylabel("タイル QR 分解の性能 [GFlops]")
        ax.set_xlim(32, 540)
        ax.set_ylim(0, None)
        ax.grid(color=GRID, lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color("#c3c2b7")
        ax.tick_params(colors="#52514e")
        ax.legend(loc="lower right", fontsize=10, frameon=False)
    fig.suptitle("同じ機械でコア数だけを2倍にする：小さい nb では遅くなる", fontsize=13, color=INK)
    fig.savefig(OUT / "fig_same_machine.png")

    t = keep[keep.nb.isin([32, 64, 128, 256, 384]) & keep["size"].isin([4096, 8192])]
    print(t.pivot_table(index=["size", "nb"], columns="config", values="G").round(0).to_string())
    u = keep[keep.nb.isin([32]) & keep.machine.isin(["aoba-b", "calc"])]
    print(u.pivot_table(index=["config", "nb"], columns="size", values="us_per_task").round(2).to_string())


if __name__ == "__main__":
    main()
