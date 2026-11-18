"""i：余分な時間 = c0 + τ·タスク数 を 4機種・size ごとに当てはめる（定義M を主、K を感度）。
手順は 2026-11-17 d_rest_fit.py の式1に合わせる: 重み 1/t_obs の線形最小二乗（相対誤差の二乗和を最小）、c0・τ に符号の制約なし。
  ただし式1の T_sim の代わりに、4機種そろえるため 定義M の基準（T_model）または 定義K の基準（T_ideal）を引く（excess_M / excess_K を y とする）。
当てはめる nb の範囲（2通り）:
  全点     = 格子のすべての nb（機種・size ごと）
  比例範囲 = h の規則B・±30% で決めた「外れ始める nb」の手前まで（nb_min ≤ nb < nb_dep、h_departure.csv）。外れなければ全点
不老・弐は d_rest_fit.csv 式1・5回の平均の値（nb ≥ NB_MIN、T_sim 基準）も参考に並べる（当てはめ直さない）。
傾きの再現: 当てはめ線 y_fit = c0 + τ·タスク数 を実測の各点で評価し（y_fit > 0 の点）、nb ≥ 予測 nb の点を size をまたいでまとめて log-log の傾きを測る。実測の傾き（g_fit.csv）と比べる。
c0 と行列の大きさ: c0 = a + b·MB（MB = size²·8/2²⁰）を size 間で当てはめ。
出力: data/i_c0_tau.csv, data/i_slope_repro.csv, data/i_c0_vs_MB.csv, fig_i_M.png"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.ticker, textwrap
from gcommon import *
from tileqr_data.style import _find_jp_font
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False

d = pd.read_csv(OUT / "data/g_points.csv"); H = pd.read_csv(OUT / "data/h_departure.csv")
H = H[(H.rule == "B") & (H.tol == 0.3)]
gfit = pd.read_csv(OUT / "data/g_fit.csv")
rows, fitted = [], []
for dfn, col in (("M", "excess_M"), ("K", "excess_K")):
    for pn in ORDER:
        for size, g in d[d.panel == pn].groupby("size"):
            g = g.sort_values("nb")
            dep = H[(H.panel == pn) & (H["size"] == int(size)) & (H.definition == dfn)].nb_dep
            dep = dep.iloc[0] if len(dep) else np.nan
            for rng in ("全点", "比例範囲"):
                h = g if (rng == "全点" or np.isnan(dep)) else g[g.nb < dep]
                if len(h) < 4: continue
                w = 1 / h.t_obs.to_numpy(); y = h[col].to_numpy(); X = np.c_[np.ones(len(h)), h.tasks]
                coef, *_ = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)
                rel = (X @ coef - y) / h.t_obs.to_numpy()
                rows.append(dict(definition=dfn, panel=pn, size=int(size), range=rng, nb_lo=h.nb.min(), nb_hi=h.nb.max(), n=len(h), c0_ms=coef[0] * 1e3, tau_us=coef[1] * 1e6,
                                 rel_rms_vs_tobs=float(np.sqrt(np.mean(rel ** 2))), nb_dep=dep))
                gg = g.copy(); gg["y_fit"] = coef[0] + coef[1] * gg.tasks; gg["definition"] = dfn; gg["range"] = rng; fitted.append(gg[["panel", "size", "nb", "tasks", "cls", "y_fit", "definition", "range"]].assign(y_obs=gg[col]))
R = pd.DataFrame(rows); R.to_csv(OUT / "data/i_c0_tau.csv", index=False, float_format="%.5g")
pd.set_option("display.width", 220); print(R.to_string())

F = pd.concat(fitted)
rep = []
for (dfn, rng, pn), g in F.groupby(["definition", "range", "panel"], sort=False):
    for sub, m in (("全点", g.nb > 0), ("nb < 予測 nb", g.cls == "lt_pred"), ("nb ≥ 予測 nb", g.cls == "ge_pred")):
        h = g[m]; po = h[h.y_fit > 0]
        fl = fit_loglog(po.tasks, po.y_fit)
        ob = gfit[(gfit.panel == pn) & (gfit.definition == dfn) & (gfit.subset == sub)].iloc[0]
        rep.append(dict(definition=dfn, fit_range=rng, panel=pn, subset=sub, slope_obs=ob.slope, slope_fitline=fl["slope"], n_fitline=fl["n"], n_nonpos_fitline=len(h) - len(po),
                        drop_obs=1 - ob.slope, drop_fitline=1 - fl["slope"]))
P = pd.DataFrame(rep); P["explained_frac"] = P.drop_fitline / P.drop_obs
P.to_csv(OUT / "data/i_slope_repro.csv", index=False, float_format="%.4g"); print(P.to_string())

cm = []
for (dfn, rng, pn), g in R.groupby(["definition", "range", "panel"], sort=False):
    if len(g) < 3: continue
    mb = (g["size"] ** 2 * 8 / 2 ** 20).to_numpy(); b, a = np.polyfit(mb, g.c0_ms, 1)
    cm.append(dict(definition=dfn, fit_range=rng, panel=pn, n_sizes=len(g), intercept_ms=a, slope_ms_per_MB=b, resid_max_ms=np.abs(a + b * mb - g.c0_ms).max(), c0_ms_by_size=" ".join(f"{v:.3g}" for v in g.c0_ms)))
pd.DataFrame(cm).to_csv(OUT / "data/i_c0_vs_MB.csv", index=False, float_format="%.4g"); print(pd.DataFrame(cm).to_string())

INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D", 16384: "v"}
SC = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#2f9e5a", 8192: "#8a4fbf", 16384: "#b8860b"}
fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
for ax, pn in zip(axes.flat, ORDER):
    for size, g in d[d.panel == pn].groupby("size"):
        g = g.sort_values("nb"); m = g.excess_M > 0
        ax.scatter(g.tasks[m], g.excess_M[m], s=14, marker=MK[int(size)], color=SC[int(size)], alpha=.7, label=f"size {int(size)}")
        r = R[(R.definition == "M") & (R.panel == pn) & (R["size"] == int(size)) & (R.range == "全点")]
        if len(r):
            x = np.geomspace(g.tasks.min(), g.tasks.max(), 40); yy = r.c0_ms.iloc[0] * 1e-3 + r.tau_us.iloc[0] * 1e-6 * x
            ax.plot(x[yy > 0], yy[yy > 0], color=SC[int(size)], lw=1.4)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG); ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.set_title(pn, fontsize=12, loc="left"); ax.set_xlabel("タスク数 N³/3 + N²/2"); ax.set_ylabel("余分な時間（定義M）[s]"); ax.legend(frameon=False, fontsize=9, loc="upper left")
fig.suptitle("余分な時間 = c0 + τ·タスク数 の当てはめ（定義M、全点、size ごと）", fontsize=15, x=.01, ha="left")
fig.subplots_adjust(left=.05, right=.98, top=.93, bottom=.12, wspace=.12, hspace=.32)
note = ("点 = 実測の余分な時間（定義M = 実測 − W/(p·A·E_カーネル·E_並列)、E_並列 は理論値 c = √7.5・k = 2、r0 = 1）。線 = size ごとの c0 + τ·タスク数（全 nb の点に、重み 1/実測時間の線形最小二乗。d_rest_fit.csv 式1と同じ手順）。"
        "不老・弐は 5回の平均・c_split の全格子。余分な時間 ≤ 0 の点は描かない。")
fig.text(.01, .005, textwrap.fill(note, 190), fontsize=8.5, va="bottom")
fig.savefig(OUT / "fig_i_M.png", dpi=100, facecolor=BG)
