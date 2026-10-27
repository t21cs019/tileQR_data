"""EPYC 7543 のタイル QR 性能（各 nb で最良の ib、5周の平均）。7月の計測（隔離済み）と 10/27 の再計測を重ねる。"""
from pathlib import Path
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D = ROOT / "raw/qr_sweep/epyc_s1_smt-off"          # 4096 以上（既存）
OLD = ROOT / "archive/quarantine/epyc_size1024-2048_slow_2026-07"
NEW = {1024: ROOT / "raw_data/epyc_s1_smt-off/epyc_size1024_nb32-512_t5_20261027_080944.csv",
       2048: ROOT / "raw_data/epyc_s1_smt-off/epyc_size2048_nb32-512_t5_20261027_095708.csv"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COL = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#1baf7a", 8192: "#eda100", 16384: "#e87ba4"}

def curve(files):
    df = pd.concat([pd.read_csv(f) for f in files])
    a = df.groupby(["nb", "ib"], as_index=False).GFlops.mean()
    return a.loc[a.groupby("nb").GFlops.idxmax()].sort_values("nb").reset_index(drop=True)

series = []  # (label, size, curve, is_old_anomalous)
for s in [1024, 2048, 4096, 8192, 16384]:
    anomalous = s in NEW
    c = curve(sorted((OLD if anomalous else D).glob(f"epyc_size{s}_*.csv")))
    series.append((f"{s}（{'7月・旧' if anomalous else '既存'}）", s, c, anomalous))
for s, f in NEW.items():
    series.append((f"{s}（10/27 再計測）", s, curve([f]), False))

fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), layout="constrained")
for ax, logy in zip(axes, [False, True]):
    for label, s, c, old in series:
        ax.plot(c.nb, c.GFlops, color=COL[s], lw=1.6 if old else 2, ls=(0, (4, 3)) if old else "-",
                label=label, zorder=2 if old else 3)
        i = c.GFlops.idxmax()
        ax.plot(c.nb[i], c.GFlops[i], "o", ms=7, color=COL[s], mec=SURF, mew=2, zorder=4)
        if logy:  # 右端に直接ラベル
            ax.annotate(label, (c.nb.iloc[-1], c.GFlops.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8.5, color=INK)
    ax.set_xlim(20, 640 if logy else 524); ax.set_xticks([32, 128, 256, 384, 512])
    if logy:
        ax.set_yscale("log"); ax.set_ylim(0.7, 1500)
        ax.set_title("対数目盛り（小さいサイズの差を見る）", loc="left", fontsize=11, color=INK)
    else:
        ax.set_ylim(0, None)
        ax.set_title("通常の目盛り", loc="left", fontsize=11, color=INK)
    ax.set_xlabel("nb", color=INK2); ax.set_ylabel("タイルQR分解 GFlops", color=INK2)
    ax.grid(axis="y", which="major", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ["top", "right"]: ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]: ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
fig.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=9.5, labelcolor=INK, loc="outside lower center", ncol=7)
fig.suptitle("EPYC 7543（1ソケット, 32コア, SMT off）: 各 nb で最良の ib（5回の平均）。破線 = 7月の計測、● = 最高性能",
             fontsize=12, color=INK, x=0.01, ha="left")
fig.savefig(HERE / "fig_epyc_old_vs_new.png", dpi=150, facecolor=SURF)

# 異常の大きさ
for s in NEW:
    o = next(c for l, ss, c, old in series if ss == s and old)
    n = next(c for l, ss, c, old in series if ss == s and not old)
    m = o.merge(n, on="nb", suffixes=("_old", "_new")); r = m.GFlops_new / m.GFlops_old
    print(f"size {s}: 旧 peak {o.GFlops.max():.1f} (nb {o.nb[o.GFlops.idxmax()]})  新 peak {n.GFlops.max():.1f} (nb {n.nb[n.GFlops.idxmax()]})"
          f"  peak比 {n.GFlops.max()/o.GFlops.max():.1f}x  nbごとの比 中央値 {r.median():.1f}x 範囲 {r.min():.1f}-{r.max():.1f}x")
    print("   ", m[m.nb.isin([32, 64, 96, 128, 192, 256, 384, 512])].assign(ratio=r.round(1))[["nb", "GFlops_old", "GFlops_new", "ratio"]].round(1).to_string(index=False).replace("\n", "\n    "))
for l, s, c, old in series:
    if s == 4096 and not old: print("4096 peak", c.GFlops.max().round(1))
