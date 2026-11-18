"""図：計時区間の内訳（p × Time に対する割合、round 1）。"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
import c_breakdown_lib as cb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]

rows = [r for r in cb.table() if r["size"] != 512]
order = ["blas_compute", "core_blas", "blas_alloc", "omp_task", "omp_other", "omp_wait", "kernel_unres", "libc", "plasma", "other_user", "offcpu"]
labels = {"blas_compute": "OpenBLAS（計算）", "core_blas": "libplasma_core_blas", "blas_alloc": "OpenBLAS blas_memory_alloc/free",
          "omp_task": "libiomp5（タスク）", "omp_other": "libiomp5（その他）", "omp_wait": "libiomp5（待ち）",
          "kernel_unres": "カーネル等（dso 不明）", "libc": "libc", "plasma": "libplasma", "other_user": "その他", "offcpu": "CPU に乗っていない"}
cols = ["#4C78A8", "#9ECAE9", "#E45756", "#F58518", "#FFBF79", "#B6992D", "#54A24B", "#88D27A", "#B279A2", "#BAB0AC", "#D3D3D3"]
fig, ax = plt.subplots(figsize=(10, 4.8))
rows = sorted(rows, key=lambda r: (r["p"], r["size"], r["nb"]))
x = range(len(rows))
bot = [0] * len(rows)
for k, c in zip(order, cols):
    v = [100 * r[k] / r["core_s"] for r in rows]
    ax.bar(x, v, bottom=bot, color=c, label=labels[k], width=0.75)
    bot = [b + a for b, a in zip(bot, v)]
ax.set_xticks(list(x))
ax.set_xticklabels([f"p={r['p']}\n{r['size']}\nnb {r['nb']}" for r in rows], fontsize=8)
ax.set_ylabel("p × Time に対する割合 [%]（オンCPU の試料）")
ax.set_title("EPYC 7543：QR の計時区間の内訳（perf、round 1）", fontsize=10)
ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.0, 0.5))
fig.tight_layout()
fig.savefig(ROOT / "fig_breakdown.png", dpi=150)
