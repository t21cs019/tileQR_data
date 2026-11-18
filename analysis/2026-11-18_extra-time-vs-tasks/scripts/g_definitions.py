"""g：4機種×2定義（M: 実測 − モデル（E_並列 理論値込み）、K: 実測 − W/(p·A·E_カーネル)）で 余分な時間 vs タスク数 の表と全体図を作る。
出力: data/g_points.csv（4機種の全点、両定義）, data/g_fit.csv（全点・nb<予測 nb・nb≥予測 nb の傾き・R²・τ、≤0 の点数）,
      fig_g_M.png, fig_g_K.png（各 1920×1080）"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from gcommon import *
from tileqr_data.style import _find_jp_font
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False

d = points()
d.to_csv(OUT / "data/g_points.csv", index=False, float_format="%.6g")
rows = []
for dfn, col in (("M", "excess_M"), ("K", "excess_K")):
    t = slope_table(d, col); t.insert(1, "definition", dfn); rows.append(t)
f = pd.concat(rows); f.to_csv(OUT / "data/g_fit.csv", index=False, float_format="%.4g")
print(f.to_string())

INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D", 16384: "v"}
NORM = LogNorm(32, 512); CM = plt.get_cmap("viridis_r")
DEF = {"M": "実測 − 当てはめなしのモデルの時間 W/(p·A·E_カーネル·E_並列)（r0 = 1、E_並列 は理論値 c = √7.5・k = 2）",
       "K": "実測 − W/(p·A·E_カーネル)（E_並列 を引かない）"}
for dfn, col in (("M", "excess_M"), ("K", "excess_K")):
    fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
    for ax, pn in zip(axes.flat, ORDER):
        g = d[d.panel == pn]; pos = g[g[col] > 0]
        for size, h in pos.groupby("size"):
            for lt, hh in ((False, h[h.cls == "ge_pred"]), (True, h[h.cls == "lt_pred"])):
                if not len(hh): continue
                kw = dict(facecolors="none", edgecolors=CM(NORM(hh.nb)), linewidths=1.0) if lt else dict(c=hh.nb, cmap=CM, norm=NORM, linewidths=0)
                ax.scatter(hh.tasks, hh[col], s=24, marker=MK[int(size)], alpha=.85, **kw)
        ft = f[(f.panel == pn) & (f.definition == dfn)].set_index("subset")
        A, L, G = ft.loc["全点"], ft.loc["nb < 予測 nb"], ft.loc["nb ≥ 予測 nb"]
        xs = np.array([g.tasks.min() / 1.5, g.tasks.max() * 1.5])
        ax.plot(xs, A.tau_us * 1e-6 * xs, color=INK, lw=1.3)
        ax.text(.02, .98, f"全点（n = {int(A.n)}、≤0: {int(A.n_nonpositive)}）：傾き {A.slope:.2f}、R² = {A.R2:.2f}、τ = {A.tau_us:.1f} µs（実線）\n"
                f"nb < 予測 nb（n = {int(L.n)}、≤0: {int(L.n_nonpositive)}）：傾き {L.slope:.2f}、R² = {L.R2:.2f}\n"
                f"nb ≥ 予測 nb（n = {int(G.n)}、≤0: {int(G.n_nonpositive)}）：傾き {G.slope:.2f}、R² = {G.R2:.2f}",
                transform=ax.transAxes, va="top", fontsize=9.5, color=INK, bbox=dict(fc=BG, ec="none", alpha=.85))
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG); ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.set_title(pn, fontsize=12, loc="left"); ax.set_xlabel("タスク数 N³/3 + N²/2"); ax.set_ylabel("余分な時間 [s]")
    fig.suptitle(f"余分な時間とタスク数の関係（定義{dfn}）", fontsize=15, x=.01, ha="left")
    fig.subplots_adjust(left=.05, right=.93, top=.93, bottom=.17, wspace=.16, hspace=.32)
    sm = plt.cm.ScalarMappable(norm=NORM, cmap=CM); sm.set_array([])
    cb = fig.colorbar(sm, ax=list(axes.flat), pad=.01, fraction=.025); cb.set_label("nb"); cb.set_ticks([32, 64, 128, 256, 512]); cb.set_ticklabels(["32", "64", "128", "256", "512"]); cb.ax.minorticks_off()
    h = [Line2D([], [], marker=m, ls="", color=MUTED, label=f"size {s}") for s, m in MK.items()]
    h += [Line2D([], [], marker="o", ls="", color=MUTED, label="塗り: nb ≥ 予測 nb"), Line2D([], [], marker="o", ls="", mfc="none", color=MUTED, label="白抜き: nb < 予測 nb")]
    fig.legend(handles=h, loc="lower center", ncol=7, frameon=False, fontsize=10, bbox_to_anchor=(.45, .08))
    import textwrap
    note = (f"定義{dfn}の余分な時間 = {DEF[dfn]}。4機種とも同じ式。不老・弐は 5回の平均・c_split の全格子（A = 99.7・β = 124、size 1024〜8192、8192 は nb ≥ 64）、"
            "3機種は eta_eff.csv（各 nb で ib について最高）。タスク数 = N³/3 + N²/2（N = size/nb）。τ = 傾き1に固定した log-log 当てはめ（実線）。傾き・R² は傾きを自由にした log-log 当てはめ。余分な時間 ≤ 0 の点は描かない。")
    fig.text(.01, .005, textwrap.fill(note, 190), fontsize=8.5, va="bottom")
    fig.savefig(OUT / f"fig_g_{dfn}.png", dpi=100, facecolor=BG); plt.close(fig)
