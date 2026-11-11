"""
E. 小さい nb で、タスク1個あたりの時間が size によらず一定か。

定義（analysis/2026-11-10_serial-task-cost/scripts/serial_tau.py と同じ）:
  タスク数 = N³/3 + N²/2、N = size/nb（割り切れないときも小数のまま）
  参考に、A/B テストの読み直し（bind_ab_time.py）の定義 N = ceil(size/nb)、Σk² でも出す
時間は、nb ごとに ib について最も短い点の値。5 回の最小（min）と中央値（median）の両方を出す。
不老・弐の 1 コアの DTSMQR（A・β）は未計測なので、「モデルより余分な時間」は出さない。出すのは時間 ÷ タスク数だけ。

出力: data/e_per_task.csv、fig_e_per_task.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import DATA, OUT, P, SIZES, flops_dgeqrf, load_all, setup_plot, tasks

A_US = 0.09          # τ = a·p の a [µs]（2026-11-10_serial-task-cost の交差検証の値）
NBS = [32, 40, 48, 56, 64, 72, 80, 96, 112, 128, 160, 192, 256]


def main():
    pd.set_option("display.width", 250)
    d = load_all()
    g = d.groupby(["size", "nb", "ib"]).t_ms.agg(tmin="min", tmed="median", tmax="max").reset_index()
    # nb ごとに、中央値が最も短い ib を選ぶ
    idx = g.groupby(["size", "nb"]).tmed.idxmin()
    e = g.loc[idx].reset_index(drop=True)
    e["N"] = e["size"] / e.nb
    e["tasks"] = e.N**3 / 3 + e.N**2 / 2
    e["tasks_ceil"] = tasks(e["size"], e.nb)
    for k in ("tmin", "tmed", "tmax"):
        e[f"us_{k[1:]}"] = e[k] * 1e3 / e.tasks
    e["us_med_ceil"] = e.tmed * 1e3 / e.tasks_ceil
    # 計算そのものの時間の目安：その size の最高の GFlops で全体を計算したときの時間（下限の目安）
    best = d.groupby("size").GFlops.max()
    e["t_compute_ms"] = flops_dgeqrf(e["size"]) / (e["size"].map(best) * 1e6)
    e["compute_share"] = e.t_compute_ms / e.tmed
    e["G_med"] = flops_dgeqrf(e["size"]) / (e.tmed * 1e6)
    e["cap_4nb3_over_tau"] = 4 * e.nb**3 / (A_US * P * 1e-6) / 1e9     # τ = a·p のときの性能の上限 [GFlops]
    e.to_csv(DATA / "e_per_task.csv", index=False, float_format="%.5g")

    x = e[e.nb.isin(NBS)]
    print(f"τ = a·p の予測：{A_US} × {P} = {A_US * P:.1f} µs")
    print("\n== タスク1個あたりの時間 [µs]（5 回の中央値、ib は最良）==")
    print(x.pivot(index="nb", columns="size", values="us_med").round(1).to_string())
    print("\n== 同（5 回の最小）==")
    print(x.pivot(index="nb", columns="size", values="us_min").round(1).to_string())
    print("\n== 同（中央値、N = ceil、Σk² の定義）==")
    print(x.pivot(index="nb", columns="size", values="us_med_ceil").round(1).to_string())
    print("\n== 最小と中央値の差 ÷ 中央値 [%]（2 水準の影響の目安）==")
    print((100 * (x.tmed - x.tmin) / x.tmed).groupby([x.nb, x["size"]]).first().unstack().round(1).to_string())
    print("\n== 時間 [ms]（中央値）と、計算そのものの時間の目安が占める割合 [%] ==")
    print(pd.concat([x.pivot(index="nb", columns="size", values="tmed").round(0),
                     (100 * x.pivot(index="nb", columns="size", values="compute_share")).round(1).add_prefix("share_")],
                    axis=1).to_string())
    print("\n== GFlops（中央値）と、τ = 17.3 µs のときの上限 4·nb³/τ ==")
    print(pd.concat([x.pivot(index="nb", columns="size", values="G_med").round(1),
                     x.drop_duplicates("nb").set_index("nb").cap_4nb3_over_tau.round(1)], axis=1).to_string())
    print("\n選ばれた ib:")
    print(x.pivot(index="nb", columns="size", values="ib").to_string())

    plt = setup_plot()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for s in SIZES:
        y = e[(e["size"] == s) & (e.nb <= 256)]
        ax.plot(y.nb, y.us_med, "o-", ms=3, lw=1, label=f"size {s}")
    ax.axhline(A_US * P, color="k", ls="--", lw=0.8, label=f"τ = a·p = {A_US * P:.0f} µs")
    ax.set_yscale("log")
    ax.set_xlabel("nb")
    ax.set_ylabel("時間 ÷ タスク数 [µs]（5 回の中央値、ib は最良）")
    ax.set_title("E. タスク1個あたりの時間（不老・弐 p = 192、固定あり）")
    ax.legend()
    fig.savefig(OUT / "fig_e_per_task.png", bbox_inches="tight")


if __name__ == "__main__":
    main()
