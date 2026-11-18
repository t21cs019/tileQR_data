"""j：傾きが場所で変わる原因（nb < 予測 nb で 0.8〜1.0、nb ≥ 予測 nb で 0.4〜0.6）の候補を、手元のデータだけで1つずつ確かめる。
  傾きの低下 = 1 − 実測の傾き（nb ≥ 予測 nb、定義M、g_fit.csv）。候補を入れた/直した後の傾きを s_c として、説明した割合 = (s_c − s_obs)/(1 − s_obs)。
  1. c0（size ごとの一定の時間）: 同じ式の形を 機種ごとにまとめて（size 共通のパラメータ）当てはめ、傾きと誤差を比べる
       F1: τ·タスク数 ／ F2: a·t_ideal + τ·タスク数（計算時間に比例する項 = r0 型）／ F3: (a0 + b·MB) + τ·タスク数（行列の大きさに比例する一定の時間 c0）。MB = size²·8/2²⁰
       重み 1/実測時間の線形最小二乗。当てはめ線で nb ≥ 予測 nb の log-log の傾きを測る。i_c0_tau.csv の c0 が size³ と size² のどちらに近い増え方かも
  2. 余分/実測時間の小ささとノイズ: nb ≥ 予測 nb の 余分/実測、実測の繰り返し間のばらつき（3機種 = derived/qr_sweep.parquet の5回、不老・弐 = 速い・遅い水準の差）、
       実測を nb 方向に5点の中央値でならしたときの傾きの変化、定義M と K の傾きの違い
  3. 並列度の不足（不老・弐だけ）: c_split の rest_mean（= 余分な時間(K) − explained_mean）で傾きを測り直す
  4. 格子の端・ばらつき: nb ≥ 予測 nb で nb > 448（端の約10%）を除いた傾き、size 1024（c0 が最も大きい）を除いた傾き
出力: data/j_pooled_forms.csv, data/j_noise.csv, data/j_candidates.csv"""
import numpy as np, pandas as pd
from gcommon import *

d = pd.read_csv(OUT / "data/g_points.csv"); gfit = pd.read_csv(OUT / "data/g_fit.csv")
s_obs = {pn: gfit[(gfit.panel == pn) & (gfit.definition == "M") & (gfit.subset == "nb ≥ 予測 nb")].slope.iloc[0] for pn in ORDER}
cands = []
def add(pn, cand, metric, value, s_c=None, note="", base=None, mode="remove"):
    """mode=remove: 候補を直した後の傾き s_c が 1 に近づいた割合 (s_c − s_base)/(1 − s_base)。mode=reproduce: 式の形の当てはめ線の傾きが 実測の低下を再現した割合 (1 − s_c)/(1 − s_base)。
    base は比べる実測の傾き（既定 = 定義M の nb ≥ 予測 nb）。"""
    b = s_obs[pn] if base is None else base
    r = dict(panel=pn, candidate=cand, metric=metric, value=value, slope_base=b, slope_candidate=s_c, mode=mode, note=note)
    if s_c is not None and not np.isnan(s_c): r["explained_frac"] = (s_c - b) / (1 - b) if mode == "remove" else (1 - s_c) / (1 - b)
    cands.append(r)

def slope_ge(g, y, mask=None):
    h = g[(g.cls == "ge_pred") & (y > 0)] if mask is None else g[(g.cls == "ge_pred") & (y > 0) & mask]
    return fit_loglog(h.tasks, y[h.index])["slope"]

# 1 -------------------------------------------------------------------
rows = []
for pn in ORDER:
    g = d[d.panel == pn].copy(); g["MB"] = g["size"] ** 2 * 8 / 2 ** 20
    y = g.excess_M.to_numpy(); w = 1 / g.t_obs.to_numpy()
    forms = {"F1: τ·タスク数": np.c_[g.tasks], "F2: a·t_ideal + τ·タスク数": np.c_[g.t_ideal, g.tasks], "F3: (a0 + b·MB) + τ·タスク数": np.c_[np.ones(len(g)), g.MB, g.tasks]}
    for fn, X in forms.items():
        coef, *_ = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)
        yf = pd.Series(X @ coef, index=g.index); rel = (yf - g.excess_M) / g.t_obs
        sc = slope_ge(g, yf); sa = fit_loglog(g[yf > 0].tasks, yf[yf > 0])["slope"]
        rows.append(dict(panel=pn, form=fn, coef=" ".join(f"{c:.4g}" for c in coef), rel_rms_vs_tobs=float(np.sqrt((rel ** 2).mean())), slope_fitline_ge_pred=sc, n_nonpos_fitline=int((yf <= 0).sum())))
        add(pn, "1 c0（" + fn + "）", "rel_rms_vs_tobs", float(np.sqrt((rel ** 2).mean())), sc, "当てはめ線の傾きが実測の低下を再現した割合", mode="reproduce")
    # c0 の size 依存（i の全点当てはめ）
    R = pd.read_csv(OUT / "data/i_c0_tau.csv"); R = R[(R.definition == "M") & (R.panel == pn) & (R.range == "全点") & (R.c0_ms > 0)]
    if len(R) >= 3:
        sl = np.polyfit(np.log(R["size"]), np.log(R.c0_ms), 1)[0]
        rows.append(dict(panel=pn, form="c0 ∝ size^k（i、c0 > 0 の size）", coef=f"k = {sl:.2f}（size² なら 2、size³ なら 3）", rel_rms_vs_tobs=np.nan, slope_fitline_ge_pred=np.nan, n_nonpos_fitline=np.nan))
        add(pn, "1 c0 の size 依存", "k（c0 ∝ size^k）", sl)
pd.DataFrame(rows).to_csv(OUT / "data/j_pooled_forms.csv", index=False, float_format="%.4g"); print(pd.DataFrame(rows).to_string())

# 2 -------------------------------------------------------------------
sw = pd.read_parquet(AN.parent / "derived" / "qr_sweep.parquet")
cfg = {MACHINES["EPYC7543"]: "epyc_s1_smt-off", MACHINES["EPYC7702 s1"]: "aoba-b_s1_smt-off", MACHINES["Xeon4214 s1"]: "calc_s1_smt-off"}
noise = []
for pn in ORDER:
    g = d[d.panel == pn].copy(); g["frac"] = g.excess_M / g.t_obs
    if pn in cfg:
        s = sw[sw.config == cfg[pn]]
        a = s.groupby(["size", "nb", "ib"]).GFlops.agg(["mean", "std"]).reset_index()
        a = a.loc[a.groupby(["size", "nb"])["mean"].idxmax()]
        a["cv_mean"] = a["std"] / a["mean"] / np.sqrt(5)
        g = g.merge(a[["size", "nb", "cv_mean"]], on=["size", "nb"], how="left")
    else:
        g["cv_mean"] = (g.T_obs_slow - g.T_obs_fast).abs() / g.t_obs   # 速い・遅い水準の差（集計の不確かさの目安。5回の平均の標準誤差ではない）
    g["noise_over_excess"] = g.cv_mean / g.frac.where(g.frac > 0)
    for sub, m in (("nb < 予測 nb", g.cls == "lt_pred"), ("nb ≥ 予測 nb", g.cls == "ge_pred")):
        h = g[m]
        noise.append(dict(panel=pn, subset=sub, n=len(h), frac_excess_median=h.frac.median(), frac_nonpositive=(h.frac <= 0).mean(), cv_mean_median=h.cv_mean.median(),
                          noise_over_excess_median=h.noise_over_excess.median()))
    # ならした傾き（size ごとに nb 方向の5点中央値で t_obs をならす）
    g = g.sort_values(["size", "nb"]); g["t_s"] = g.groupby("size").t_obs.transform(lambda x: x.rolling(5, center=True, min_periods=3).median())
    ys = g.t_s - g.t_model
    g = g.sort_index()
    sc = slope_ge(g, ys.sort_index()); add(pn, "2 ノイズ（nb 方向5点の中央値でならす）", "余分/実測の中央値（nb ≥ 予測 nb）", noise[-1]["frac_excess_median"], sc,
                                          f"ばらつき/余分の中央値 {noise[-1]['noise_over_excess_median']:.3g}")
    sK = gfit[(gfit.panel == pn) & (gfit.definition == "K") & (gfit.subset == "nb ≥ 予測 nb")].slope.iloc[0]
    add(pn, "2 定義K（E_並列 を引かない）の傾き", "slope_K（nb ≥ 予測 nb）", sK, None, "定義M の傾きは上の slope_obs。K のほうが低い")
pd.DataFrame(noise).to_csv(OUT / "data/j_noise.csv", index=False, float_format="%.4g"); print(pd.DataFrame(noise).to_string())

# 3 -------------------------------------------------------------------
g = d[d.panel == FLOW2].copy()
sl = slope_table(g.assign(rest=g.rest_mean), "rest").set_index("subset")
for sub in ("全点", "nb < 予測 nb", "nb ≥ 予測 nb"):
    print("rest_mean", sub, sl.loc[sub, ["n", "n_nonpositive", "slope", "R2"]].to_dict())
sK2 = gfit[(gfit.panel == FLOW2) & (gfit.definition == 'K') & (gfit.subset == 'nb ≥ 予測 nb')].slope.iloc[0]
add(FLOW2, "3 並列度の不足（rest_mean = 余分な時間(K) − explained_mean）", "slope_rest（nb ≥ 予測 nb）", sl.loc["nb ≥ 予測 nb", "slope"], sl.loc["nb ≥ 予測 nb", "slope"],
    "rest は K 基準なので 定義K の傾きと比べる", base=sK2)
fr = (g.starv_total / g.excess_K).groupby(g.cls).median(); print("starv/excess_K median", fr.to_dict())
add(FLOW2, "3 starv_total / 余分な時間(K)", "中央値（nb ≥ 予測 nb）", fr["ge_pred"], None, f"nb < 予測 nb: {fr['lt_pred']:.3g}")

# 4 -------------------------------------------------------------------
for pn in ORDER:
    g = d[d.panel == pn]
    y = g.excess_M
    sc = slope_ge(g, y, g.nb <= 448); add(pn, "4 格子の端（nb > 448 を除く）", "n（nb ≥ 予測 nb）", int(((g.cls == "ge_pred") & (y > 0) & (g.nb <= 448)).sum()), sc)
    sc = slope_ge(g, y, g["size"] != 1024); add(pn, "4 size 1024 を除く", "n", int(((g.cls == "ge_pred") & (y > 0) & (g["size"] != 1024)).sum()), sc)
C = pd.DataFrame(cands); C.to_csv(OUT / "data/j_candidates.csv", index=False, float_format="%.4g")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(C[["panel", "candidate", "metric", "value", "slope_base", "slope_candidate", "explained_frac"]].to_string())
