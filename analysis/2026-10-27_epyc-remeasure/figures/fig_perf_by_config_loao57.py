"""
各構成で予測 nb が達成した性能比（2026-10-21 スライド p23 と同じ形式の棒グラフ）を、57条件の LOAO で描く。

p23 は中間40条件（10機種 × size 1024〜8192）の LOAO。ここでは13機種 × size 1024〜16384 の57条件で、
どの条件もその機種（全サイズ）を抜いて当てはめた c, k（../data/fold_constants57.csv）で予測する。
入力は ../s1_smt-off/data/perf_vs_parallelism_loao57.csv（fig_perf_vs_parallelism_slide.py の出力）。
出力は fig_perf_by_config_loao57.png。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm

HERE = Path(__file__).resolve().parent
fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"

# p23 の画像から取った色。16384 は p23 に無いので足した
SIZE_COLOR = {1024: "#2a78d6", 2048: "#1baf7a", 4096: "#eda100", 8192: "#e87ba4", 16384: "#8a6a4f"}
PURPLE, INK, AXIS, GRID = "#aa4eff", "#262626", "#595959", "#ececec"
# p23 の並び（物理コア数の多い順）に、追加の3機種を同じコア数の後ろへ入れる
ORDER = [("EPYC7702 s1", "EPYC\n7702"), ("EPYC7543", "EPYC\n7543"), ("Xeon4214 s1", "Xeon Silver\n4214"),
         ("i7-6900K", "Core\ni7-6900K"), ("i5-8500", "Core\ni5-8500"), ("R5-7400F", "Ryzen 5\n7400F"),
         ("i5-9600", "Core\ni5-9600"), ("i3-10100", "Core\ni3-10100"), ("i5-7400", "Core\ni5-7400"),
         ("i7-7700", "Core\ni7-7700"), ("i3-8100", "Core\ni3-8100"), ("E3-1220v3", "Xeon\nE3-1220v3"),
         ("i3-7100", "Core\ni3-7100")]
ADDED = {"i5-9600", "i3-8100", "E3-1220v3"}


def main():
    d = pd.read_csv(HERE.parent / "s1_smt-off/data/perf_vs_parallelism_loao57.csv")
    if len(d) != 57:
        raise SystemExit(f"条件数が57でない: {len(d)}")
    fig, ax = plt.subplots(figsize=(9.9, 4.87), dpi=220, layout="constrained")
    w = 0.16
    sizes = list(SIZE_COLOR)
    for gi, (lab, _) in enumerate(ORDER):
        s = d[d.label == lab].set_index("size")
        for j, size in enumerate(sizes):
            if size in s.index:
                ax.bar(gi + (j - 2) * w, s.perf[size], w * 0.94, color=SIZE_COLOR[size], zorder=2,
                       label=f"size {size}" if gi == 0 else None)
    mean = d.perf.mean()
    ax.axhline(mean, color=PURPLE, ls="--", lw=1.6, zorder=3)
    ax.text(len(ORDER) - 0.45, mean + 0.35, f"全体平均 {mean:.1f}%", color=PURPLE, fontsize=11,
            ha="right", va="bottom", zorder=4,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5, alpha=0.9))
    p = d.groupby("label").p.first()
    ax.set_xticks(range(len(ORDER)), [f"{t}\np = {p[lab]}" for lab, t in ORDER], fontsize=9.5)
    for t, (lab, _) in zip(ax.get_xticklabels(), ORDER):
        if lab in ADDED:
            t.set_fontweight("bold")
    ax.set_xlim(-0.55, len(ORDER) - 0.45)
    ax.set_ylim(75, 100.6)
    ax.set_yticks([75, 80, 85, 90, 95, 100], ["75", "80", "85", "90", "95", "100%"])
    ax.set_xlabel("構成（物理コア数 p の多い順、太字は中間発表後に追加した機種）", color=INK, fontsize=12)
    ax.set_ylabel("性能比（予測 nb の性能 / 実測ピーク性能）", color=INK, fontsize=11)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#c8c8c8")
    ax.tick_params(colors=AXIS, labelsize=11, labelcolor=INK, length=0)
    ax.tick_params(axis="x", labelsize=9.5)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=5, frameon=False, fontsize=12,
              labelcolor=INK, handlelength=1.6, columnspacing=1.6)
    fig.savefig(HERE / "fig_perf_by_config_loao57.png", facecolor="white")
    plt.close(fig)

    relerr = (np.abs(d.nb_pred - d.nb_opt) / d.nb_opt).mean() * 100
    print(f"57条件 LOAO: 平均 {mean:.1f}%  最低 {d.perf.min():.1f}%  予測 nb の平均相対誤差 {relerr:.1f}%")


if __name__ == "__main__":
    main()
