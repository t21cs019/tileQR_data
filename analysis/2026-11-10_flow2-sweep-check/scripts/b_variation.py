"""
B. 値がおかしくないか：反復 5 回のばらつき、外れ値、ジョブ（ノード）ごとの偏り、実行順のドリフト。

出力:
  data/b1_variation.csv   size × nb の帯ごとの、時間の変動係数と最大/最小
  data/b2_job_ratio.csv   ジョブごとの、点の中央値に対する時間の比（全体と nb の帯ごと）
  data/b2_outliers.csv    点の中央値の 1.5 倍より遅い実行
  data/b4_drift.csv       ジョブごと・実行順の 10 等分ごとの比
  fig_b_residual.png      (nb, ib) ごとの、点の中央値に対する時間の比（size × 反復）
  fig_b_drift.png         実行順に沿った比
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import DATA, OUT, REPS, SIZES, load_all, nb_band, setup_plot


def main():
    pd.set_option("display.width", 250)
    d = load_all()
    g = d.groupby(["size", "nb", "ib"]).t_ms
    d["t_med"] = g.transform("median")
    d["ratio"] = d.t_ms / d.t_med
    d["band"] = nb_band(d.nb)

    # --- B1 ---
    pt = g.agg(mean="mean", sd=lambda v: v.std(ddof=1), mn="min", mx="max", med="median").reset_index()
    pt["cv"] = 100 * pt.sd / pt["mean"]
    pt["maxmin"] = pt.mx / pt.mn
    pt["band"] = nb_band(pt.nb)
    b1 = pt.groupby(["size", "band"], observed=True).agg(
        points=("cv", "size"), t_med_ms=("med", "median"), cv_med=("cv", "median"),
        cv_p90=("cv", lambda v: v.quantile(0.9)), maxmin_med=("maxmin", "median"),
        maxmin_p90=("maxmin", lambda v: v.quantile(0.9)), maxmin_max=("maxmin", "max")).reset_index()
    tot = pt.groupby("size").agg(points=("cv", "size"), t_med_ms=("med", "median"), cv_med=("cv", "median"),
                                 cv_p90=("cv", lambda v: v.quantile(0.9)), maxmin_med=("maxmin", "median"),
                                 maxmin_p90=("maxmin", lambda v: v.quantile(0.9)),
                                 maxmin_max=("maxmin", "max")).reset_index()
    tot["band"] = "全体"
    b1 = pd.concat([b1, tot], ignore_index=True)
    b1.to_csv(DATA / "b1_variation.csv", index=False, float_format="%.4g")
    print("== B1 時間の変動係数 [%] と最大/最小（点ごと、5 回）==")
    print(b1.to_string(index=False, float_format="%.3g"))
    pt["ibr"] = pd.cut(pt.ib / pt.nb, [0, 0.125, 0.25, 0.375, 0.5])
    print("\nib/nb ごとの cv の中央値 [%]")
    print(pt.pivot_table(index="size", columns="ibr", values="cv", aggfunc="median", observed=True).round(1))

    # --- B2 ジョブごとの比 ---
    # 中央値に対する比の中央値は、5 回のうち 1 回が必ず 1 になるので使えない。幾何平均と順位で見る
    gm = lambda v: float(np.exp(np.log(v).mean()))
    d["rank"] = d.groupby(["size", "nb", "ib"]).t_ms.rank()
    jr = d.groupby(["size", "rep", "node"]).agg(all=("ratio", gm), rank_mean=("rank", "mean"),
                                                fastest=("rank", lambda v: (v == 1).mean()),
                                                slowest=("rank", lambda v: (v == 5).mean())).reset_index()
    jb = d.pivot_table(index=["size", "rep"], columns="band", values="ratio", aggfunc=gm, observed=True)
    b2 = jr.merge(jb.reset_index(), on=["size", "rep"])
    b2.to_csv(DATA / "b2_job_ratio.csv", index=False, float_format="%.4f")
    print("\n== B2 ジョブごとの時間の比（その点の 5 回の中央値に対する比の幾何平均。rank_mean は 5 回の中の順位の平均で、偏りがなければ 3。fastest・slowest は 0.2）==")
    print(b2.to_string(index=False, float_format="%.3f"))

    # 外れ値
    out = d[d.ratio > 1.5].copy()
    out[["size", "rep", "node", "nb", "ib", "seq", "GFlops", "t_ms", "t_med", "ratio"]].to_csv(
        DATA / "b2_outliers.csv", index=False, float_format="%.5g")
    print("\n== 外れ値（点の中央値の 1.5 倍より遅い）の数：size × 反復 ==")
    print(out.pivot_table(index="size", columns="rep", values="ratio", aggfunc="size", fill_value=0))
    print("size × nb の帯")
    print(out.pivot_table(index="size", columns="band", values="ratio", aggfunc="size", fill_value=0, observed=True))
    print("比が 3 を超えるもの:")
    print(out[out.ratio > 3][["size", "rep", "node", "nb", "ib", "seq", "GFlops", "t_ms", "t_med", "ratio"]]
          .sort_values("ratio", ascending=False).head(20).to_string(index=False, float_format="%.4g"))
    fast = d[d.ratio < 1 / 1.5]
    print("点の中央値の 1/1.5 より速い実行の数：", fast.groupby("size").size().to_dict())

    # --- B4 ドリフト ---
    d["decile"] = d.groupby(["size", "rep"]).seq.transform(lambda v: pd.qcut(v, 10, labels=False))
    b4 = d.pivot_table(index=["size", "decile"], columns="rep", values="ratio", aggfunc=gm)
    nbr = d.groupby(["size", "decile"]).nb.agg(["min", "max"])
    b4 = b4.join(nbr)
    b4.to_csv(DATA / "b4_drift.csv", float_format="%.4f")
    print("\n== B4 実行順の 10 等分ごとの比（反復ごと）==")
    print(b4.round(3).to_string())

    # --- 図 ---
    plt = setup_plot()
    fig, axes = plt.subplots(4, 5, figsize=(17, 12), sharex=True, sharey=True)
    for i, s in enumerate(SIZES):
        for j, r in enumerate(REPS):
            x = d[(d["size"] == s) & (d.rep == r)]
            ax = axes[i, j]
            sc = ax.scatter(x.nb, x.ib, c=np.log2(x.ratio), s=2 if s < 8192 else 7, marker="s",
                            cmap="RdBu_r", vmin=-0.6, vmax=0.6, linewidths=0)
            ax.set_title(f"size {s}  r{r}（{x.node.iloc[0]}）", fontsize=10)
            if i == 3:
                ax.set_xlabel("nb")
            if j == 0:
                ax.set_ylabel("ib")
    cb = fig.colorbar(sc, ax=axes, shrink=0.6, pad=0.01)
    cb.set_label("log2（時間 ÷ その点の 5 回の中央値）。赤 = 遅い")
    fig.suptitle("B. 点の中央値に対する時間の比（不老・弐 p=192、2026-11-10）", y=0.995)
    fig.savefig(OUT / "fig_b_residual.png", bbox_inches="tight")

    fig, axes = plt.subplots(1, 4, figsize=(17, 3.8))
    for ax, s in zip(axes, SIZES):
        for r in REPS:
            x = d[(d["size"] == s) & (d.rep == r)].sort_values("seq")
            w = max(len(x) // 40, 5)
            ax.plot(x.seq, x.ratio.rolling(w, center=True).apply(gm, raw=True), lw=1, label=f"r{r}（{x.node.iloc[0]}）")
        ax.axhline(1, color="k", lw=0.5)
        ax.set_title(f"size {s}")
        ax.set_xlabel("実行順（= nb の昇順）")
        ax.set_ylim(0.8, 1.25)
        ax.legend(fontsize=7)
    axes[0].set_ylabel("時間 ÷ 点の中央値（移動幾何平均）")
    fig.savefig(OUT / "fig_b_drift.png", bbox_inches="tight")


if __name__ == "__main__":
    main()
