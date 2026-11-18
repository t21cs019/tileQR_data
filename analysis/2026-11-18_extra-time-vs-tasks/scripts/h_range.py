"""h：「余分な時間 = τ·タスク数（原点を通る）」から外れ始める nb を、機種・size・定義（M, K）ごとにルールで決める。
ルール: 1タスクあたりの余分な時間 y = 余分な時間/タスク数 [µs]。
        基準 ref: 規則B（主）= 格子の nb が小さい方から6点の y の中央値。規則A（感度）= nb ≤ 予測 nb の点の中央値（y > 0）。
        規則B は基準の点のあとの格子点を、規則A は nb > 予測 nb の格子点を、nb の小さい順に見て、y が ref の ±tol を外れる（y ≤ 0 も外れ）最小の nb を
        「外れ始める nb」とする。偶然を避けるため、その点とあとの2格子点（あれば）の3点がすべて外れているときだけ採る（3連続）。tol = 20%・30%（主）・50%。
        規則A は、y が予測 nb より前から上がり始める機種（3機種）で基準が上がった値を含み、外れ始めを予測 nb の直後にしてしまう（実測：EPYC 7702 size 4096 で y は nb 88 から上がるが、
        規則A では nb 128）。このため主を規則B にした。
        比例する範囲 = 格子の最小 nb から、外れ始める nb の手前まで。
出力: data/h_departure.csv（nb_dep と 予測 nb・最適 nb（実測）・N・タスク数・余分/実測時間）, data/h_summary.csv（何で決まるかの散らばり）,
      fig_h_M.png, fig_h_K.png"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from gcommon import *
from tileqr_data.style import _find_jp_font
matplotlib.rcParams['font.family'] = [_find_jp_font() or 'sans-serif']; matplotlib.rcParams['axes.unicode_minus'] = False

d = pd.read_csv(OUT / "data/g_points.csv")
TOLS = (0.2, 0.3, 0.5)
rows = []
for pn in ORDER:
  for rule in ("B", "A"):
    for size, g in d[d.panel == pn].groupby("size"):
          g = g.sort_values("nb").reset_index(drop=True)
          pred = g.nb_pred.iloc[0]; opt = g.nb_opt.iloc[0]
          for dfn, col in (("M", "excess_M"), ("K", "excess_K")):
              y = g[col] / g.tasks * 1e6
              ref_pts = y[(g.nb <= pred) & (y > 0)] if rule == "A" else y.iloc[:6]
              if len(ref_pts) == 0: continue
              ref = ref_pts.median()
              start = (g.nb > pred) if rule == "A" else (g.index >= 6)
              for tol in TOLS:
                  out = ((y / ref - 1).abs() > tol) | (y <= 0)
                  dep = None
                  for i in range(len(g)):
                      if start[i] and out[i] and out[i:i + 3].all():
                          dep = i; break
                  r = dict(rule=rule, panel=pn, size=int(size), definition=dfn, tol=tol, ref_us=ref, n_ref=len(ref_pts), nb_pred=pred, nb_opt=opt, nb_min=g.nb.min())
                  if dep is None:
                      r.update(nb_dep=np.nan)
                  else:
                      q = g.loc[dep]
                      r.update(nb_dep=q.nb, dep_over_pred=q.nb / pred, dep_over_opt=q.nb / opt, N_dep=q.N, tasks_dep=q.tasks, excess_s=q[col], frac_excess_of_tobs=q[col] / q.t_obs)
                  rows.append(r)
H = pd.DataFrame(rows); H.to_csv(OUT / "data/h_departure.csv", index=False, float_format="%.4g")
pd.set_option("display.width", 250)
print(H[(H.tol == 0.3) & (H.rule == "B")].to_string())
# nb_dep が tol でどう動くか
w = H.pivot_table(index=["rule", "panel", "size", "definition"], columns="tol", values="nb_dep")
print(w.to_string())
# 何で決まるか: tol=0.3 で、機種・size をまたいだ log の散らばり（std of ln）
S = []
for rule, dfn in [(r_, d_) for r_ in ("B", "A") for d_ in ("M", "K")]:
    h = H[(H.rule == rule) & (H.tol == 0.3) & (H.definition == dfn) & H.nb_dep.notna()]
    for name, v in [("nb_dep/予測 nb", h.dep_over_pred), ("N = size/nb_dep", h.N_dep), ("余分/実測時間", h.frac_excess_of_tobs), ("nb_dep/最適 nb", h.dep_over_opt), ("nb_dep", h.nb_dep)]:
        v = v[v > 0]
        S.append(dict(rule=rule, definition=dfn, variable=name, n=len(v), median=v.median(), min=v.min(), max=v.max(), std_ln=np.log(v).std(), max_over_min=v.max() / v.min()))
S = pd.DataFrame(S); S.to_csv(OUT / "data/h_summary.csv", index=False, float_format="%.4g"); print(S.to_string())

INK, MUTED, GRID, BG = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
MK = {1024: "o", 2048: "s", 4096: "^", 8192: "D", 16384: "v"}
SC = {1024: "#2a78d6", 2048: "#eb6834", 4096: "#2f9e5a", 8192: "#8a4fbf", 16384: "#b8860b"}
for dfn, col in (("M", "excess_M"), ("K", "excess_K")):
    fig, axes = plt.subplots(2, 2, figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
    for ax, pn in zip(axes.flat, ORDER):
        for size, g in d[d.panel == pn].groupby("size"):
            g = g.sort_values("nb"); y = g[col] / g.tasks * 1e6; m = y > 0
            ax.plot(g.nb[m], y[m], color=SC[int(size)], lw=1.2, marker=MK[int(size)], ms=3, label=f"size {int(size)}")
            q = H[(H.rule == "B") & (H.panel == pn) & (H["size"] == int(size)) & (H.definition == dfn)]
            for tol, mk, ms_ in ((0.3, "o", 11),):
                r = q[q.tol == tol]
                if len(r) and r.nb_dep.notna().iloc[0]:
                    nd = r.nb_dep.iloc[0]; ax.plot([nd], [float(y[g.nb == nd].iloc[0])] if float(y[g.nb == nd].iloc[0]) > 0 else [np.nan], mk, mfc="none", mec=INK, mew=2, ms=ms_)
                ax.axhline(r.ref_us.iloc[0], color=SC[int(size)], lw=.6, ls=":") if len(r) else None
            ax.axvline(g.nb_pred.iloc[0], color=SC[int(size)], lw=.8, ls="--", alpha=.6)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_facecolor(BG); ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.set_title(pn, fontsize=12, loc="left"); ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator()); ax.set_xlabel("nb"); ax.set_ylabel("1タスクあたりの余分な時間 [µs]")
        ax.set_xticks([32, 64, 128, 256, 512]); ax.set_xticklabels(["32", "64", "128", "256", "512"]); ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(f"1タスクあたりの余分な時間と nb（定義{dfn}）", fontsize=15, x=.01, ha="left")
    fig.subplots_adjust(left=.05, right=.98, top=.93, bottom=.14, wspace=.14, hspace=.32)
    import textwrap
    note = (f"定義{dfn}：" + ("実測 − W/(p·A·E_カーネル·E_並列)（E_並列 は理論値 c = √7.5・k = 2、r0 = 1）" if dfn == "M" else "実測 − W/(p·A·E_カーネル)（E_並列 を引かない）") +
            "。丸印 = 外れ始める nb（基準 = nb の小さい方6点の中央値（点線）から ±30% を外れ、3 格子点連続で外れる最小の nb。規則B。規則A（nb ≤ 予測 nb の中央値）は data/h_departure.csv）。破線の縦線 = 予測 nb。"
            "比例なら水平。不老・弐は 5回の平均・c_split の全格子（size 8192 は nb ≥ 64）。余分な時間 ≤ 0 の点は描かない。")
    fig.text(.01, .005, textwrap.fill(note, 190), fontsize=8.5, va="bottom")
    fig.savefig(OUT / f"fig_h_{dfn}.png", dpi=100, facecolor=BG); plt.close(fig)
