"""EPYC 7543 の DTSMQR（MAT_SIZE 1024、ib = nb/8 の断面）：1本（p=1）と32本同時（p=32）の nb–GFlops と、E(nb) のフィット。
左は GFlops そのまま、右はそれぞれの A で割った効率。β は E = 0.5 になる nb（2026-10-28 ゼミのスライド用）。"""
import sys
from pathlib import Path
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tileqr_data import kurzak

D = HERE.parent / "data/ssrfb_par"
RUNS = [("p = 1（1本だけ）", "#2a6fdb", D / "epyc_ssrfb-par1_size1024_nb32-512_t1_20261027_020223.csv"),
        ("p = 32（32本同時）", "#e0601b", D / "epyc_ssrfb-par32_size1024_nb32-512_t1_20261026_234740.csv")]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), dpi=200, layout="constrained")
xs = np.linspace(32, 512, 200)
for label, col, f in RUNS:
    g = pd.read_csv(f).groupby(["nb", "ib"], as_index=False).GFlops.mean()
    s = kurzak.ib_rule_slice(g)[["nb", "GFlops"]]
    fit = s[s.nb >= 64]
    A, beta = kurzak.fit_E(fit.nb.to_numpy(float), fit.GFlops.to_numpy(float))
    ax1.plot(s.nb, s.GFlops, "o", color=col, ms=3.5, label=f"{label}　A = {A:.1f}")
    ax1.plot(xs, A * xs / (xs + beta), color=col, lw=1.6, alpha=0.8)
    ax2.plot(s.nb, s.GFlops / A, "o", color=col, ms=3.5, label=label)
    ax2.plot(xs, xs / (xs + beta), color=col, lw=1.6, alpha=0.8)
    ax2.plot([beta, beta], [0, 0.5], color=col, ls=":", lw=1.4)
    ax2.plot(beta, 0.5, "D", color=col, ms=7)
    ax2.annotate(f"β = {beta:.0f}", (beta, 0.5), xytext=(4 if beta > 160 else -4, -22), textcoords="offset points",
                 ha="left" if beta > 160 else "right", color=col, fontsize=11,
                 bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.5))
ax1.set_title("DTSMQR の性能（GFlops）：32本同時だと全体に 0.78 倍", fontsize=12)
ax1.set_ylabel("DTSMQR 1本あたりの性能 [GFlops]")
ax2.set_title("それぞれの A で割った効率 E(nb)：32本同時は早く頭打ちになる", fontsize=12)
ax2.set_ylabel("E(nb) ＝ 性能 ／ A")
ax2.axhline(0.5, color="#999999", lw=0.8, ls="--")
for ax in (ax1, ax2):
    ax.set_xlabel("nb（ib ＝ nb/8）")
    ax.set_xlim(32, 512)
    ax.set_ylim(0, None)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=10)
fig.suptitle("EPYC 7543、MAT_SIZE 1024。点 ＝ 実測、線 ＝ A·nb/(nb＋β) のフィット（nb ≥ 64）。A は nb を大きくしたときの上限", fontsize=11, x=0.01, ha="left")
fig.savefig(HERE / "fig_ssrfb_par.png")
