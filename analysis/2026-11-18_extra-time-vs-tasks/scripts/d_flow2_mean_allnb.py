"""不老・弐（p=192）を 5回の平均・全 nb の格子で作り直す（a〜c とは別ファイル）。
入力: 2026-11-17_dag-parallelism/data/c_split.csv の kernel=ib=nb/8（A=99.7, β=124）, policy=fifo の行、列 excess_mean
      （= T_obs_mean − T_ideal、T_ideal = W/(p·A·E_カーネル)。E_並列 を引かない。DAG の c_split と同じ定義）。5回平均・ib について最大は 3agg の定義。
      予測 nb = c_table_points の tag=pred（size 1024/2048/4096/8192 で 32/40/72/128）。最適 nb = 格子上で T_obs_mean が最小の nb。
      範囲: size 1024〜4096 は nb 32〜512（4刻み、各121点）、size 8192 は nb 64〜512（8刻み、57点。nb<64 はタスク>100万で模擬なし）。
      タスク数は N³/3+N²/2（N=size/nb）で数え直す。
分類: lt_pred = nb < 予測 nb（8192 は nb 64〜120 が該当）／ mid = 予測 nb ≤ nb < 0.9·最適 nb ／ ge_opt = nb ≥ 0.9·最適 nb
出力: data/d_flow2_mean_allnb_points.csv, data/d_flow2_mean_allnb_fit.csv, fig_flow2_mean_allnb.png（1920×1080）, fig_flow2_mean_allnb_960.png（960×690）"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from common import *
from tileqr_data.style import _find_jp_font
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False

c = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/c_split.csv")
c = c[(c.kernel == "ib=nb/8") & (c.policy == "fifo")].copy()
pt = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/c_table_points.csv")
pred = pt[(pt.tag == "pred") & (pt.kernel == "ib=nb/8")].set_index("size").nb
c["nb_pred"] = c["size"].map(pred)
opt = c.loc[c.groupby("size").T_obs_mean.idxmin()].set_index("size").nb
c["nb_opt"] = c["size"].map(opt)
N = c["size"] / c.nb
c["tasks_formula"] = N**3 / 3 + N**2 / 2
c["excess_s"] = c.excess_mean
c["cls"] = np.where(c.nb < c.nb_pred, "lt_pred", np.where(c.nb < 0.9 * c.nb_opt, "mid", "ge_opt"))
out = c[["size", "nb", "tasks_formula", "tasks", "excess_s", "T_obs_mean", "T_ideal", "nb_pred", "nb_opt", "cls"]]
out.to_csv(OUT / "data/d_flow2_mean_allnb_points.csv", index=False, float_format="%.6g")

def fit(x, y):
    lx, ly = np.log10(x), np.log10(y)
    if len(x) < 3: return dict(n=len(x), slope=np.nan, R2=np.nan, tau_us=np.nan)
    s, a = np.polyfit(lx, ly, 1)
    return dict(n=len(x), slope=s, R2=1 - ((ly - a - s * lx) ** 2).sum() / ((ly - ly.mean()) ** 2).sum(), tau_us=10 ** (ly - lx).mean() * 1e6)
rows = []
for name, m in [("全点", c.nb > 0), ("nb < 予測 nb", c.cls == "lt_pred"), ("nb ≥ 予測 nb", c.cls != "lt_pred"), ("予測 nb ≤ nb < 0.9·最適", c.cls == "mid"), ("nb ≥ 0.9·最適 nb", c.cls == "ge_opt")]:
    g = c[m]; rows.append(dict(scope="all sizes", subset=name, **fit(g.tasks_formula.values, g.excess_s.values)))
for s, gs in c.groupby("size"):
    for name, m in [("全点", gs.nb > 0), ("nb < 予測 nb", gs.cls == "lt_pred"), ("nb ≥ 予測 nb", gs.cls != "lt_pred")]:
        g = gs[m]; rows.append(dict(scope=f"size {s}", subset=name, **fit(g.tasks_formula.values, g.excess_s.values)))
f = pd.DataFrame(rows); f.to_csv(OUT / "data/d_flow2_mean_allnb_fit.csv", index=False, float_format="%.4g"); print(f.to_string())

r = pd.read_csv(AN / "2026-11-17_dag-parallelism/data/d_rest_fit.csv"); r = r[(r.form == "式1") & (r["agg"] == "mean") & (r.scope != "all")].set_index("scope"); r.index = r.index.astype(int)
INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D"}
NORM = LogNorm(32, 512); CM = plt.get_cmap("viridis_r")
NOTE = ("不老・弐（p = 192）、5回の平均（点ごとの5回の GFlops の平均、ib について最大）、DAG の c_split の全格子（kernel A = 99.7・β = 124）。"
        "余分な時間 = 実測 − 完全に並列な時間 W/(p·A·E_カーネル)（E_並列 を引かない。3機種の図とは定義が違う）。タスク数 = N³/3 + N²/2（N = size/nb）。"
        "τ = 傾き1に固定した log-log 当てはめ。傾き・R² は傾きを自由にした log-log 当てはめ。細い線 = 傾き1の参考線（τ の実線）、破線 = size ごとの c0 + τ·タスク数（d_rest_fit.csv 式1、5回の平均）。"
        "size 8192 は nb < 64 の模擬が無い（タスク100万超）。")

def draw(ax, small):
    for size, h in c.groupby("size"):
        for cl, kw in (("lt_pred", dict(facecolors="none")), ("mid", dict()), ("ge_opt", dict(edgecolors=INK, linewidths=.8))):
            hh = h[h.cls == cl]
            if not len(hh): continue
            if cl == "lt_pred": ax.scatter(hh.tasks_formula, hh.excess_s, s=24, marker=MK[size], edgecolors=CM(NORM(hh.nb)), facecolors="none", linewidths=1.0, alpha=.9)
            else: ax.scatter(hh.tasks_formula, hh.excess_s, s=26, marker=MK[size], c=hh.nb, cmap=CM, norm=NORM, alpha=.9, **({"linewidths": 0} if cl == "mid" else kw))
        k = r.loc[size]; x = np.geomspace(h.tasks_formula.min() / 1.3, h.tasks_formula.max() * 1.3, 30)
        ax.plot(x, k.c0_ms * 1e-3 + k.tau_us * 1e-6 * x, color=MUTED, lw=1.1, ls="--")
    A = f[(f.scope == "all sizes") & (f.subset == "全点")].iloc[0]; L = f[(f.scope == "all sizes") & (f.subset == "nb < 予測 nb")].iloc[0]; G = f[(f.scope == "all sizes") & (f.subset == "nb ≥ 予測 nb")].iloc[0]
    xs = np.array([c.tasks_formula.min() / 1.5, c.tasks_formula.max() * 1.5])
    ax.plot(xs, A.tau_us * 1e-6 * xs, color=INK, lw=1.3)
    ax.text(.02, .98, f"全点（n = {int(A.n)}）：傾き {A.slope:.2f}、R² = {A.R2:.2f}、τ = {A.tau_us:.1f} µs（実線）\nnb < 予測 nb（n = {int(L.n)}）：傾き {L.slope:.2f}、R² = {L.R2:.2f}\nnb ≥ 予測 nb（n = {int(G.n)}）：傾き {G.slope:.2f}、R² = {G.R2:.2f}",
            transform=ax.transAxes, va="top", fontsize=8.5 if small else 10.5, color=INK, bbox=dict(fc=BG, ec="none", alpha=.85))
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG); ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.set_xlabel("タスク数 N³/3 + N²/2"); ax.set_ylabel("余分な時間 [s]")

def finish(fig, ax, small):
    import textwrap
    sm = plt.cm.ScalarMappable(norm=NORM, cmap=CM); sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, pad=.01, fraction=.04 if small else .025); cb.set_label("nb"); cb.set_ticks([32, 64, 128, 256, 512]); cb.set_ticklabels(["32", "64", "128", "256", "512"]); cb.ax.minorticks_off()
    h = [Line2D([], [], marker=m, ls="", color=MUTED, label=f"size {s}") for s, m in MK.items()]
    h += [Line2D([], [], marker="o", ls="", mfc="none", color=MUTED, label="白抜き: nb < 予測 nb"), Line2D([], [], marker="o", ls="", color=MUTED, label="塗り: 予測 nb ≤ nb"),
          Line2D([], [], marker="o", ls="", color=MUTED, mec=INK, label="黒縁: 最適 nb 付近以上（nb ≥ 0.9·最適）")]
    fig.legend(handles=h, loc="lower center", ncol=4 if small else 7, frameon=False, fontsize=8.5 if small else 10, bbox_to_anchor=(.45, .17 if small else .09))
    fig.text(.01, .005, textwrap.fill(NOTE, 105 if small else 190), fontsize=7.5 if small else 8.5, color=INK, va="bottom")

for small, fn, size_in in ((False, "fig_flow2_mean_allnb.png", (19.2, 10.8)), (True, "fig_flow2_mean_allnb_960.png", (9.6, 6.9))):
    fig, ax = plt.subplots(figsize=size_in, dpi=100); fig.patch.set_facecolor(BG)
    draw(ax, small); ax.set_title("余分な時間とタスク数の関係：不老・弐（p = 192、5回の平均、全 nb）", fontsize=11 if small else 14, loc="left")
    fig.subplots_adjust(left=.09 if small else .06, right=.88 if small else .93, top=.93, bottom=.38 if small else .22)
    finish(fig, ax, small); fig.savefig(OUT / fn, dpi=100, facecolor=BG); plt.close(fig)
