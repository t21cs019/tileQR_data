"""k：スライド用。(1) 予測 nb の定義の確認と data/pred_nb.csv、(2) 予測 nb を赤で強調した fig_g_M_pred.png・fig_i_M_pred.png（1920×1080）、
(3) data/i_table_c0_tau_MB.csv（i の「全点」・定義M の c0・τ と、行列の大きさ。RESULT.md の i 節の表と assert で照合）。
予測 nb の定義（確認）: 当てはめなしのモデル（E_並列 理論値 c = √7.5・k = 2、機種ごとの A・β、r0 = 1）の最適 nb = 格子上でモデルの時間が最小の nb。
  3機種 = tau_predictions.csv の nb_theory（serial_tau.py の idxmax(G_model)）、不老・弐 = c_table_points の tag = pred。どちらも格子上の nb なので、格子で使った nb と同じ。"""
import re, textwrap
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from gcommon import *
from tileqr_data.style import _find_jp_font
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False

d = pd.read_csv(OUT / "data/g_points.csv")
# ---- 予測 nb の確認 ----
rows = []
for pn in ORDER:
    for size, g in d[d.panel == pn].groupby("size"):
        nbm = g.loc[g.t_model.idxmin(), "nb"]          # モデルの時間が最小の nb（格子上）
        src = g.nb_pred.iloc[0]
        used = g.loc[(g.nb - src).abs().idxmin(), "nb"]
        assert nbm == src, (pn, size, nbm, src)
        rows.append(dict(panel=SHORT[pn], size=int(size), pred_nb_source=src, grid_nb_used=used, on_grid=bool(used == src), argmin_model_time_on_grid=nbm,
                         source=("tau_predictions.csv nb_theory" if pn != FLOW2 else "c_table_points tag=pred")))
P = pd.DataFrame(rows); P.to_csv(OUT / "data/pred_nb.csv", index=False); print(P.to_string())

INK, MUTED, GRID, BG, RED = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb", "#d62728"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D", 16384: "v"}
SC = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#2f9e5a", 8192: "#8a4fbf", 16384: "#b8860b"}
NORM = LogNorm(32, 512); CM = plt.get_cmap("viridis_r")
R = pd.read_csv(OUT / "data/i_c0_tau.csv"); R = R[(R.definition == "M") & (R.range == "全点")]
gfit = pd.read_csv(OUT / "data/g_fit.csv"); gfit = gfit[gfit.definition == "M"]
FS = 14

def style(ax, pn):
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG); ax.grid(color=GRID, lw=.7); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.set_title(pn, fontsize=16, loc="left"); ax.set_xlabel("タスク数 N³/3 + N²/2", fontsize=FS); ax.set_ylabel("余分な時間（定義M）[s]", fontsize=FS)
    ax.tick_params(labelsize=13)

def pred_marks(ax, g):
    for size, h in g[(g.nb == g.nb_pred) & (g.excess_M > 0)].groupby("size"):
        ax.scatter(h.tasks, h.excess_M, s=260, marker=MK[int(size)], facecolors=CM(NORM(h.nb)), edgecolors=RED, linewidths=3.2, zorder=6)

def finish(fig, axes, title, note, ncol=8):
    sm = plt.cm.ScalarMappable(norm=NORM, cmap=CM); sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, pad=.01, fraction=.025); cb.set_label("nb", fontsize=FS); cb.set_ticks([32, 64, 128, 256, 512]); cb.set_ticklabels(["32", "64", "128", "256", "512"]); cb.ax.minorticks_off(); cb.ax.tick_params(labelsize=13)
    return cb

def legend_handles(i_fig):
    h = [Line2D([], [], marker=m, ls="", color=MUTED, ms=11, label=f"size {s}") for s, m in MK.items()]
    h += [Line2D([], [], marker="o", ls="", color=MUTED, ms=11, label="塗り: nb ≥ 予測 nb"), Line2D([], [], marker="o", ls="", mfc="none", color=MUTED, ms=11, label="白抜き: nb < 予測 nb"),
          Line2D([], [], marker="o", ls="", mfc=MUTED, mec=RED, mew=3, ms=14, label="赤の印 = 予測 nb")]
    h += [Line2D([], [], color=INK, lw=1.8, label="傾き1の直線（τ·タスク数）")] if not i_fig else [Line2D([], [], color=MUTED, lw=2, label="c0 + τ·タスク数（size ごと）")]
    return h

# ---- fig_g_M_pred ----
fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
for ax, pn in zip(axes.flat, ORDER):
    g = d[d.panel == pn]; pos = g[g.excess_M > 0]
    for size, h in pos.groupby("size"):
        for lt, hh in ((False, h[h.cls == "ge_pred"]), (True, h[h.cls == "lt_pred"])):
            if not len(hh): continue
            kw = dict(facecolors="none", edgecolors=CM(NORM(hh.nb)), linewidths=1.3) if lt else dict(c=hh.nb, cmap=CM, norm=NORM, linewidths=0)
            ax.scatter(hh.tasks, hh.excess_M, s=40, marker=MK[int(size)], alpha=.9, **kw)
    ft = gfit[gfit.panel == pn].set_index("subset"); A = ft.loc["全点"]
    xs = np.array([g.tasks.min() / 1.5, g.tasks.max() * 1.5]); ax.plot(xs, A.tau_us * 1e-6 * xs, color=INK, lw=1.8)
    pred_marks(ax, g); style(ax, pn)
    ax.text(.02, .98, f"全点の傾き {A.slope:.2f}（R² {A.R2:.2f}）\\nnb < 予測 nb: {ft.loc['nb < 予測 nb'].slope:.2f}　nb ≥ 予測 nb: {ft.loc['nb ≥ 予測 nb'].slope:.2f}".replace("\\n", "\n"),
            transform=ax.transAxes, va="top", fontsize=13, color=INK, bbox=dict(fc=BG, ec="none", alpha=.9))
fig.suptitle("余分な時間とタスク数の関係（定義M）", fontsize=19, x=.01, ha="left")
fig.subplots_adjust(left=.06, right=.93, top=.92, bottom=.2, wspace=.17, hspace=.34)
finish(fig, list(axes.flat), "", "")
fig.legend(handles=legend_handles(False), loc="lower center", ncol=5, frameon=False, fontsize=FS, bbox_to_anchor=(.47, .065))
note = ("余分な時間 = 実測 − 当てはめなしのモデルの時間 W/(p·A·E_カーネル·E_並列)（r0 = 1、E_並列 は理論値 c = √7.5・k = 2）。タスク数 = N³/3 + N²/2（N = size/nb）。"
        "黒の直線 = 傾き1に固定した log-log 当てはめ（τ·タスク数）。不老・弐は 5回の平均（c_split の全格子）。余分な時間 ≤ 0 の点は描かない。予測 nb = 当てはめなしのモデルの最適 nb。")
fig.text(.01, .005, textwrap.fill(note, 175), fontsize=11, va="bottom")
fig.savefig(OUT / "fig_g_M_pred.png", dpi=100, facecolor=BG); plt.close(fig)

# ---- fig_i_M_pred ----
fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
for ax, pn in zip(axes.flat, ORDER):
    g = d[d.panel == pn]
    for size, h in g.groupby("size"):
        h = h.sort_values("nb"); hp = h[h.excess_M > 0]
        for lt, hh in ((False, hp[hp.cls == "ge_pred"]), (True, hp[hp.cls == "lt_pred"])):
            if not len(hh): continue
            kw = dict(facecolors="none", edgecolors=CM(NORM(hh.nb)), linewidths=1.3) if lt else dict(c=hh.nb, cmap=CM, norm=NORM, linewidths=0)
            ax.scatter(hh.tasks, hh.excess_M, s=40, marker=MK[int(size)], alpha=.9, **kw)
        r = R[(R.panel == pn) & (R["size"] == int(size))]
        if len(r):
            x = np.geomspace(h.tasks.min(), h.tasks.max(), 60); yy = r.c0_ms.iloc[0] * 1e-3 + r.tau_us.iloc[0] * 1e-6 * x
            ax.plot(x[yy > 0], yy[yy > 0], color=MUTED, lw=2)
    pred_marks(ax, g); style(ax, pn)
fig.suptitle("余分な時間 = c0 + τ·タスク数 の当てはめ（定義M、全点、size ごと）", fontsize=19, x=.01, ha="left")
fig.subplots_adjust(left=.06, right=.93, top=.92, bottom=.2, wspace=.17, hspace=.34)
finish(fig, list(axes.flat), "", "")
fig.legend(handles=legend_handles(True), loc="lower center", ncol=5, frameon=False, fontsize=FS, bbox_to_anchor=(.47, .065))
note = ("点 = 実測の余分な時間（定義M = 実測 − W/(p·A·E_カーネル·E_並列)、E_並列 は理論値 c = √7.5・k = 2、r0 = 1）。灰色の線 = size ごとの c0 + τ·タスク数"
        "（全 nb の点に、重み 1/実測時間の線形最小二乗）。予測 nb = 当てはめなしのモデルの最適 nb。不老・弐は 5回の平均（c_split の全格子）。余分な時間 ≤ 0 の点は描かない。")
fig.text(.01, .005, textwrap.fill(note, 175), fontsize=11, va="bottom")
fig.savefig(OUT / "fig_i_M_pred.png", dpi=100, facecolor=BG); plt.close(fig)

# ---- 表用データ ----
T = R.assign(machine=R.panel.map(SHORT), matrix_MB=lambda x: x["size"] ** 2 * 8 / 2 ** 20)[["machine", "size", "c0_ms", "tau_us", "matrix_MB", "n", "nb_lo", "nb_hi"]]
T["machine"] = pd.Categorical(T.machine, [SHORT[p] for p in ORDER]); T = T.sort_values(["machine", "size"])
T.to_csv(OUT / "data/i_table_c0_tau_MB.csv", index=False, float_format="%.5g")
label = {"EPYC 7543": "7543 全点", "EPYC 7702": "7702 全点", "Xeon 4214": "Xeon 4214 全点", "不老・弐": "不老・弐 全点"}
txt = open(OUT / "RESULT.md").read(); n_chk = 0
for m, lab in label.items():
    line = [l for l in txt.splitlines() if l.startswith(f"| {lab} |")][0]
    cells = [c.strip() for c in line.strip("|").split("|")][1:]
    sizes = [1024, 2048, 4096, 8192, 16384]
    for sz, c in zip(sizes, cells):
        r = T[(T.machine == m) & (T["size"] == sz)]
        if c == "—": assert len(r) == 0; continue
        a, b = [x.strip() for x in c.split("/")]
        for s_, v in ((a.replace("−", "-"), r.c0_ms.iloc[0]), (b, r.tau_us.iloc[0])):
            dec = len(s_.split(".")[1]) if "." in s_ else 0
            assert abs(float(s_) - v) <= 0.5 * 10 ** -dec + 1e-9, (m, sz, s_, v); n_chk += 1
print("assert OK:", n_chk, "値")
print(T.to_string())
