"""
C6. 集計の方法の比較　と　D. 結果がもっともらしいか。

集計の方法（点 (nb, ib) ごとに 5 回をまとめる）:
  mean      GFlops の平均（tileQR_data/scripts/ingest.py のいまの定義）
  median    GFlops の中央値
  hmean     時間の平均を GFlops に直したもの（調和平均）
  max       GFlops の最大（= 最小時間）
  fastmean  速い水準（ex ≤ 6 ms）に入った回だけの平均（1 回もなければ欠測）
  base      速い水準の見積もり（3×3 近傍の、速い水準に入った実行の時間の中央値。common.add_baseline）を GFlops に直したもの

出力:
  data/c6_aggregation.csv   方法ごとの最適 (nb, ib) と値、ほかの方法で見たときの値
  data/d1_optimum.csv       推奨の集計での最適点と、1%・2% 以内の範囲
  data/d2_per_rep.csv       反復ごとの最適 nb
  data/d3_ab_compare.csv    A/B テスト（close、--membind）との突き合わせ
  data/d4_machines.csv      ほかの機種の最適 nb と性能
  data/agg_points.csv       点ごとの各集計値（後の解析用）
  fig_d_gflops_vs_nb.png    nb ごと（ib について最高）の GFlops。集計の方法ごと
  fig_d_heatmap.png         推奨の集計の (nb, ib) ヒートマップ
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import DATA, OUT, REPS, SIZES, SLOW_MS, add_baseline, flops_dgeqrf, load_all, setup_plot, step_of

REPO = Path(__file__).resolve().parents[3]
AB_DIR = Path.home() / "Download/flow/flow_bind-ab_20261031_082853"
METHODS = ["mean", "median", "hmean", "max", "fastmean", "base"]


def aggregate(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(["size", "nb", "ib"])
    a = g.GFlops.agg(mean="mean", median="median", max="max", sd="std").reset_index()
    a["hmean"] = (flops_dgeqrf(a["size"]) / (g.t_ms.mean().values * 1e6))
    f = d[d.ex <= SLOW_MS].groupby(["size", "nb", "ib"]).GFlops.agg(fastmean="mean", n_fast="size").reset_index()
    a = a.merge(f, on=["size", "nb", "ib"], how="left")
    a["n_fast"] = a.n_fast.fillna(0).astype(int)
    b = d.drop_duplicates(["size", "nb", "ib"])[["size", "nb", "ib", "base"]]
    a = a.merge(b, on=["size", "nb", "ib"])
    a["base"] = flops_dgeqrf(a["size"]) / (a.base * 1e6)
    return a


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    plt = setup_plot()
    d = add_baseline(load_all())
    a = aggregate(d)
    a.to_csv(DATA / "agg_points.csv", index=False, float_format="%.6g")

    # ---------------- C6 集計の方法 ----------------
    rows = []
    for s in SIZES:
        x = a[a["size"] == s].set_index(["nb", "ib"])
        for m in METHODS:
            nb, ib = x[m].idxmax()
            row = dict(size=s, method=m, nb=nb, ib=ib, value=x.loc[(nb, ib), m])
            for m2 in ("mean", "median", "max", "base"):
                row[f"at_{m2}"] = x.loc[(nb, ib), m2]                    # この点を別の方法で見た値
                row[f"rel_{m2}"] = x.loc[(nb, ib), m2] / x[m2].max()     # その方法の最高に対する比
            # nb ごと（ib について最高）の曲線での最適 nb
            row["nb_curve_opt"] = x[m].groupby("nb").max().idxmax()
            rows.append(row)
    c6 = pd.DataFrame(rows)
    c6.to_csv(DATA / "c6_aggregation.csv", index=False, float_format="%.5g")
    print("== C6 集計の方法ごとの最適点 ==")
    print(c6[["size", "method", "nb", "ib", "value", "at_mean", "at_median", "at_max", "at_base", "rel_mean",
              "rel_median", "rel_max", "rel_base"]].to_string(index=False, float_format="%.4g"))
    piv = c6.pivot(index="method", columns="size", values="value").loc[METHODS]
    print("\n最適点の値 [GFlops] と、mean に対する比")
    print(pd.concat([piv.round(1), (piv / piv.loc["mean"]).round(3).add_prefix("x")], axis=1).to_string())
    print("\n5 回とも遅い水準だった点の割合（fastmean が欠測）:",
          a.groupby("size").n_fast.apply(lambda v: (v == 0).mean()).round(3).to_dict())
    # max の「勝者の呪い」：最大の点での max と base の差
    mx = c6[c6.method == "max"]
    print("max の最適点で、max が base（近傍でならした速い水準）を上回る割合 [%]:",
          (100 * (mx.value / mx.at_base - 1)).round(1).tolist())

    # ---------------- 図：nb ごとの曲線 ----------------
    fig, axes = plt.subplots(1, 4, figsize=(18, 4))
    for ax, s in zip(axes, SIZES):
        x = a[a["size"] == s]
        for m, c in zip(["mean", "median", "max", "base"], ["#999999", "#ee7733", "#0077bb", "k"]):
            y = x.groupby("nb")[m].max()
            ax.plot(y.index, y.values, lw=1.2 if m != "base" else 0.8, color=c, label=m)
        ax.set_title(f"size {s}")
        ax.set_xlabel("nb")
        ax.legend()
    axes[0].set_ylabel("GFlops（ib について最高）")
    fig.suptitle("C6/D. 集計の方法ごとの nb に対する性能（不老・弐 p = 192、固定あり）", y=1.02)
    fig.savefig(OUT / "fig_d_gflops_vs_nb.png", bbox_inches="tight")

    # ---------------- D1 推奨の集計（max と base）での最適点と範囲 ----------------
    rows = []
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    for ax, s in zip(axes, SIZES):
        x = a[a["size"] == s]
        st = step_of(s)
        for m in ("max", "base", "median"):
            top = x.loc[x[m].idxmax()]
            row = dict(size=s, method=m, nb=int(top.nb), ib=int(top.ib), GFlops=top[m],
                       ib_over_nb=top.ib / top.nb,
                       at_nb_edge=bool(top.nb in (32, 512)),
                       at_ib_edge=bool(top.ib == 8 or top.ib + st > top.nb // 2))
            for pct in (1, 2, 5):
                w = x[x[m] >= top[m] * (1 - pct / 100)]
                row[f"n_{pct}%"] = len(w)
                row[f"nb_{pct}%"] = f"{w.nb.min()}-{w.nb.max()}"
                row[f"ib_{pct}%"] = f"{w.ib.min()}-{w.ib.max()}"
            rows.append(row)
        sc = ax.scatter(x.nb, x.ib, c=x.base / x.base.max(), s=3 if s < 8192 else 10, marker="s", cmap="viridis",
                        vmin=0.5, vmax=1, linewidths=0)
        top = x.loc[x.base.idxmax()]
        ax.plot(top.nb, top.ib, "r*", ms=10)
        w = x[x.base >= 0.98 * x.base.max()]
        ax.scatter(w.nb, w.ib, s=6, facecolors="none", edgecolors="r", linewidths=0.4)
        ax.set_title(f"size {s}：最適 nb {int(top.nb)}・ib {int(top.ib)}（{top.base:.0f} GFlops）")
        ax.set_xlabel("nb")
    axes[0].set_ylabel("ib")
    fig.colorbar(sc, ax=axes, shrink=0.8, pad=0.01).set_label("base ÷ 最高（0.5 未満は同じ色）")
    fig.suptitle("D1. 速い水準（base）の (nb, ib) 分布。星 = 最適、赤い枠 = 2% 以内", y=1.02)
    fig.savefig(OUT / "fig_d_heatmap.png", bbox_inches="tight")
    d1 = pd.DataFrame(rows)
    d1.to_csv(DATA / "d1_optimum.csv", index=False, float_format="%.5g")
    print("\n== D1 最適点と、最適から 1%・2%・5% 以内の範囲 ==")
    print(d1.to_string(index=False, float_format="%.4g"))

    # ---------------- D2 反復ごと ----------------
    rows = []
    for s in SIZES:
        for r in REPS:
            x = d[(d["size"] == s) & (d.rep == r)]
            top = x.loc[x.GFlops.idxmax()]
            # ならした版：nb ごとに ib についての上位 3 点の中央値をとり、その最大の nb
            cur = x.groupby("nb").GFlops.apply(lambda v: v.nlargest(3).median())
            rows.append(dict(size=s, rep=r, node=top.node, nb_point=int(top.nb), ib_point=int(top.ib),
                             G_point=top.GFlops, nb_curve=int(cur.idxmax()), G_curve=cur.max()))
    d2 = pd.DataFrame(rows)
    d2.to_csv(DATA / "d2_per_rep.csv", index=False, float_format="%.5g")
    print("\n== D2 反復ごとの最適（nb_point = 1 回の値の最大の点。nb_curve = nb ごとに上位 3 点の中央値をとった曲線の最大）==")
    print(d2.to_string(index=False, float_format="%.4g"))
    print(d2.groupby("size").agg(nb_point_min=("nb_point", "min"), nb_point_max=("nb_point", "max"),
                                 nb_curve_min=("nb_curve", "min"), nb_curve_max=("nb_curve", "max"),
                                 G_point_min=("G_point", "min"), G_point_max=("G_point", "max")).to_string())

    # ---------------- D3 A/B テスト ----------------
    rows = []
    for s in (2048, 4096, 8192):
        ab = pd.read_csv(AB_DIR / f"bind-close_size{s}.csv")
        for (nb, ib), y in ab.groupby(["nb", "ib"]):
            x = a[(a["size"] == s) & (a.nb == nb) & (a.ib == ib)].iloc[0]
            rows.append(dict(size=s, nb=nb, ib=ib, ab_mean=y.GFlops.mean(), ab_median=y.GFlops.median(),
                             ab_max=y.GFlops.max(), ab_min=y.GFlops.min(), sw_mean=x["mean"], sw_median=x["median"],
                             sw_max=x["max"], sw_min=d[(d["size"] == s) & (d.nb == nb) & (d.ib == ib)].GFlops.min(),
                             sw_base=x.base))
    d3 = pd.DataFrame(rows)
    d3["median_ratio"] = d3.sw_median / d3.ab_median
    d3["max_ratio"] = d3.sw_max / d3.ab_max
    d3.to_csv(DATA / "d3_ab_compare.csv", index=False, float_format="%.5g")
    print("\n== D3 A/B テスト（close、--membind、ib = 32、5 回）とスイープの同じ点 ==")
    print(d3.to_string(index=False, float_format="%.4g"))

    # ---------------- D4 ほかの機種 ----------------
    q = pd.read_parquet(REPO / "derived/qr_sweep.parquet")
    q = q[q.GFlops > 0]
    rows = []
    for cfg, p in [("epyc_s1_smt-off", 32), ("aoba-b_s1_smt-off", 64), ("calc_s1_smt-off", 12)]:
        x = q[(q.config == cfg) & q["size"].isin(SIZES)]
        m = x.groupby(["size", "nb", "ib"]).GFlops.agg(["mean", "max"]).reset_index()
        for s, y in m.groupby("size"):
            t = y.loc[y["mean"].idxmax()]
            t2 = y.loc[y["max"].idxmax()]
            rows.append(dict(config=cfg, p=p, size=s, nb_mean=int(t.nb), ib_mean=int(t.ib), G_mean=t["mean"],
                             nb_max=int(t2.nb), ib_max=int(t2.ib), G_max=t2["max"]))
    for s in SIZES:
        x = a[a["size"] == s]
        t, t2, t3 = x.loc[x["mean"].idxmax()], x.loc[x["max"].idxmax()], x.loc[x.base.idxmax()]
        rows.append(dict(config="flow2-t1_s1_smt-off（今回）", p=192, size=s, nb_mean=int(t.nb), ib_mean=int(t.ib),
                         G_mean=t["mean"], nb_max=int(t2.nb), ib_max=int(t2.ib), G_max=t2["max"],
                         nb_base=int(t3.nb), ib_base=int(t3.ib), G_base=t3.base))
    d4 = pd.DataFrame(rows)
    d4["G_per_core"] = d4.G_max / d4.p
    d4.to_csv(DATA / "d4_machines.csv", index=False, float_format="%.5g")
    print("\n== D4 機種ごとの最適（mean = 5 回の平均の最大。max = 最大値の最大）==")
    print(d4.to_string(index=False, float_format="%.4g"))


if __name__ == "__main__":
    main()
