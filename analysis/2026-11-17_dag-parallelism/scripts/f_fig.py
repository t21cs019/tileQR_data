"""
f：図。size ごとに nb と時間（ms、対数）。完全に並列な時間、DAG の模擬（p=192、fifo）、モデル（W/p + D）、
実測（3集計）。縦線は予測 nb（灰）と実測の最適 nb（速い水準）。A・β は ib=nb/8。
出力：fig_f_time_vs_nb.png
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = pd.read_csv(DATA / "c_split.csv")
d = d[(d.kernel == "ib=nb/8") & (d.policy == "fifo")]
B = pd.read_csv(AGG3 / "data/b_summary.csv")
B = B[(B.kernel == "ib=nb/8") & (B["agg"] == "fast")].set_index("size")
SER = [("T_ideal", "ideal W/(pAE)", "#52514e", (0, (3, 2))),
       ("T_model", "model W/p + D", "#eb6834", (0, (5, 2))),
       ("T_sim", "DAG list-schedule p=192", "#2a78d6", "-"),
       ("T_obs_fast", "observed: fast level", "#1baf7a", "-"),
       ("T_obs_slow", "observed: slow only", "#eda100", "-"),
       ("T_obs_mean", "observed: mean of 5", "#e87ba4", "-")]
fig, axs = plt.subplots(1, 4, figsize=(16, 4.4), sharey=True, facecolor="#fcfcfb")
for ax, size in zip(axs, SIZES):
    g = d[d["size"] == size].sort_values("nb")
    ax.set_facecolor("#fcfcfb")
    for col, lab, c, ls in SER:
        ax.plot(g.nb, g[col] * 1e3, color=c, lw=2, ls=ls, label=lab)
    ax.axvline(B.loc[size, "nb_pred"], color="#a8a7a2", lw=1)
    ax.axvline(B.loc[size, "nb_obs"], color="#1baf7a", lw=1, ls=":")
    ax.set_yscale("log"); ax.set_title(f"size {size}", color="#0b0b0b")
    ax.set_xlabel("nb", color="#52514e"); ax.grid(alpha=0.25, lw=0.6)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
axs[0].set_ylabel("time [ms]", color="#52514e")
axs[0].legend(fontsize=8, frameon=False, loc="upper right")
fig.suptitle("Flow2 p=192: DAG starvation (blue - gray) vs observed excess. "
             "vertical: predicted nb (gray), observed best nb fast (green dotted)", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "fig_f_time_vs_nb.png", dpi=130)
