"""図を作る。data/a_points.csv と data/b_fit.csv を読む（当てはめ直さない）。
  fig_all.png（1920×1080、4パネル）、fig_<機種>.png（960×690、機種ごと）
  横軸 タスク数 N³/3+N²/2（log）、縦軸 余分な時間 [s]（log）。色 = nb（連続）、形 = size、塗り = nb ≥ 予測 nb、白抜き = nb < 予測 nb。
  実線 = 余分な時間 = τ·タスク数（傾き1に固定した log-log 当てはめ、excess>0 の全点）、点線 = 同じ当てはめを nb < 予測 nb の点だけで。
  不老・弐は 速い水準を主、遅い水準・5回の平均は薄い小さい点。破線 = size ごとの c0 + τ·タスク数（d_rest_fit.csv 式1、速い水準、当てはめ直さない）。"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from common import *
from tileqr_data.style import _find_jp_font  # common27.jp_font と同じ設定（common の名前が衝突するので直接）
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False
INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D", 16384: "v"}
NORM = LogNorm(32, 512); CM = plt.get_cmap("viridis_r")
d = pd.read_csv(OUT / "data/a_points.csv"); f = pd.read_csv(OUT / "data/b_fit.csv")
c0 = pd.read_csv(OUT / "data/b_flow2_c0tau.csv"); c0 = c0[c0["agg"] == "fast"].set_index("scope")
NOTE = ("余分な時間: 3機種 = 実測の QR の時間 − 当てはめなしのモデルの時間（r0 = 1、E_並列 は理論値 c = √7.5・k = 2、E_カーネルは機種ごとの A・β）。"
        "不老・弐 = 実測 − 完全に並列な時間 W/(p·A·E_カーネル)（E_並列 を引かない）。\n"
        "タスク数 = N³/3 + N²/2（N = size/nb）。τ = 傾き1に固定した log-log 当てはめ（余分な時間 > 0 の点、τ·タスク数の直線）。"
        "傾き・R² は傾きを自由にした log-log 当てはめ。")

def panel(ax, pn, small=False):
    g = d[d.panel == pn]; flow = pn == FLOW2
    if flow:
        for a in ("slow", "mean"):
            h = g[g["agg"] == a]
            ax.scatter(h.tasks, h.excess_s, c=h.nb, cmap=CM, norm=NORM, s=14, alpha=.25, marker="o", linewidths=0)
        g = g[g["agg"] == "fast"]
    for size, h in g.groupby("size"):
        h = h[h.positive]
        for lt, hh in ((False, h[h.rel_pred == "ge_pred"]), (True, h[h.rel_pred == "lt_pred"])):
            if len(hh) == 0: continue
            kw = dict(facecolors="none", edgecolors=CM(NORM(hh.nb)), linewidths=1.0) if lt else dict(c=hh.nb, cmap=CM, norm=NORM, linewidths=0)
            ax.scatter(hh.tasks, hh.excess_s, s=34 if flow else 24, marker=MK[int(size)], alpha=.85, **kw)
    ft = lambda sub: f[(f.panel == pn) & (f["agg"] == ("fast" if flow else "best-of-ib")) & (f.subset == sub)].iloc[0]
    A, L = ft("all"), ft("lt_pred")
    xs = np.array([g.tasks.min() / 1.5, g.tasks.max() * 1.5])
    ax.plot(xs, A.tau_us * 1e-6 * xs, color=INK, lw=1.6)
    txt = [f"傾き {A.slope:.2f}、R² = {A.R2:.2f}（log-log）", f"τ = {A.tau_us:.1f} µs（実線、全点 n = {int(A.n)}）"]
    if not flow and L.n >= 3:
        ax.plot(xs, L.tau_us * 1e-6 * xs, color=INK, lw=1.2, ls=":")
        txt.append(f"τ = {L.tau_us:.1f} µs（点線、nb < 予測 nb、n = {int(L.n)}）")
    if flow:
        for size, h in g.groupby("size"):
            r = c0.loc[int(size)]; x = np.array([h.tasks.min(), h.tasks.max()]); x = np.geomspace(x[0] / 1.3, x[1] * 1.3, 20)
            ax.plot(x, r.c0_ms * 1e-3 + r.tau_us * 1e-6 * x, color=MUTED, lw=1.1, ls="--")
        txt.append("破線: c0 + τ·タスク数（size ごと）")
    ex = int(A.n_excluded_nonpositive) if False else int(f[(f.panel == pn) & (f["agg"] == ("fast" if flow else "best-of-ib")) & (f.subset == "all")].n_excluded_nonpositive.iloc[0])
    if ex: txt.append(f"余分な時間 ≤ 0 の {ex} 点は描かない")
    ax.text(.02, .98, "\n".join(txt), transform=ax.transAxes, va="top", fontsize=8.5 if small else 10, color=INK,
            bbox=dict(fc=BG, ec="none", alpha=.85))
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG)
    ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.set_title(pn, fontsize=12, color=INK, loc="left")
    ax.set_xlabel("タスク数 N³/3 + N²/2"); ax.set_ylabel("余分な時間 [s]")

def legend(fig, ax, flow_note=False):
    h = [Line2D([], [], marker=MK[s], ls="", color=MUTED, label=f"size {s}") for s in MK]
    h += [Line2D([], [], marker="o", ls="", color=MUTED, label="塗り: nb ≥ 予測 nb"),
          Line2D([], [], marker="o", ls="", mfc="none", color=MUTED, label="白抜き: nb < 予測 nb")]
    return h

def finish(fig, axes, small, flow=True):
    import textwrap
    sm = plt.cm.ScalarMappable(norm=NORM, cmap=CM); sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, pad=.01, fraction=.025 if not small else .04); cb.set_label("nb"); cb.set_ticks([32, 64, 128, 256, 512]); cb.set_ticklabels(["32", "64", "128", "256", "512"]); cb.ax.minorticks_off()
    fig.legend(handles=legend(fig, None), loc="lower center", ncol=4 if small else 7, frameon=False, fontsize=9 if small else 10, bbox_to_anchor=(.45, .17 if small else .06))
    extra = "不老・弐: 速い水準が主（濃い点）、遅い水準だけ・5回の平均は薄い点。nb < 予測 nb の点は計算していない（予測 nb と最適 nb 付近のみ）。" if flow else ""
    w = 105 if small else 250
    txt = "\n".join(textwrap.fill(t, w) for t in (NOTE.replace("\n", " ") + " " + extra).split("\n"))
    fig.text(.01, .005, txt, fontsize=7.5 if small else 8.5, color=INK, va="bottom")

panels = list(MACHINES.values()) + [FLOW2]
fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
for ax, pn in zip(axes.flat, panels): panel(ax, pn)
fig.suptitle("余分な時間とタスク数の関係", fontsize=15, color=INK, x=.01, ha="left")
fig.subplots_adjust(left=.05, right=.93, top=.93, bottom=.19, wspace=.16, hspace=.32)
finish(fig, list(axes.flat), False); fig.savefig(OUT / "fig_all.png", dpi=100, facecolor=BG); plt.close(fig)
names = ["epyc7543", "epyc7702", "xeon4214", "flow2"]
for pn, nm in zip(panels, names):
    fig, ax = plt.subplots(figsize=(9.6, 6.9), dpi=100); fig.patch.set_facecolor(BG)
    panel(ax, pn, True); ax.set_title(f"余分な時間とタスク数の関係：{pn}", fontsize=11, loc="left")
    fig.subplots_adjust(left=.09, right=.88, top=.93, bottom=.36)
    finish(fig, [ax], True, pn == FLOW2); fig.savefig(OUT / f"fig_{nm}.png", dpi=100, facecolor=BG); plt.close(fig)
