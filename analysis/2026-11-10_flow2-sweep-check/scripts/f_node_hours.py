"""
F. ノード時間とポイントの突き合わせ。

_meta.txt の「開始」「終了」から実行時間を計算し直し、見積もり（notes/flow2_sweep_plan.md）と、
ユーザーが 2026-11-10 に貼った show_point の値（Used = 2811）と比べる。

出力: data/f_node_hours.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from common import DATA, REPS, SIZES, base, base_r0, load_all, parse_meta

POINT_PER_SEC = 0.034            # Type I、1 ノード（flow2_sweep_plan.md。手引書と消費単価のページから）
SHOW_POINT_USED = 2811           # ユーザーが貼った show_point の Used（全ジョブ終了後）
PRE_PRODUCTION = 9               # 本番の前のテストジョブなど（weekly/2026-11-11.md）
# 見積もり（flow2_sweep_plan.md の表。1 本あたりの時間 [h] と、5 本のノード時間）
EST = {"1024+2048": ((1, 2), (5, 10)), "4096": ((4, 6), (20, 30)), "8192": ((7, 8), (35, 40))}


def main():
    pd.set_option("display.width", 250)
    d = load_all()
    fact = d.groupby(["size", "rep"]).t_ms.sum() / 1e3       # 分解そのものの時間の合計 [s]
    rows = []
    for s in SIZES:
        for r in REPS:
            m = parse_meta(Path(str(base(s, r)) + "_meta.txt"))
            n = len(d[(d["size"] == s) & (d.rep == r)])
            rows.append(dict(size=s, rep=r, job=m["job"], node=m["host"], start=m["start_time"], end=m["end_time"],
                             elapsed_s=m["elapsed_s"], points=n, s_per_point=m["elapsed_s"] / n,
                             factor_s=fact[(s, r)], factor_share=fact[(s, r)] / m["elapsed_s"]))
    f = pd.DataFrame(rows)
    f.to_csv(DATA / "f_node_hours.csv", index=False, float_format="%.5g")
    print(f.to_string(index=False, float_format="%.4g"))

    t = f.groupby("size").agg(elapsed_s=("elapsed_s", "sum"), per_job_h_min=("elapsed_s", lambda v: v.min() / 3600),
                              per_job_h_max=("elapsed_s", lambda v: v.max() / 3600),
                              s_per_point=("s_per_point", "mean"), factor_share=("factor_share", "mean"))
    t["node_h"] = t.elapsed_s / 3600
    t["points"] = t.elapsed_s * POINT_PER_SEC
    print("\n== size ごと ==")
    print(t.round(3).to_string())
    tot = f.elapsed_s.sum()
    print(f"\n合計 {tot:.0f} 秒 = {tot / 3600:.2f} ノード時間 = {tot * POINT_PER_SEC:.1f} ポイント")

    print("\n== 見積もりとの差（ジョブ単位。1024 と 2048 は同じジョブ）==")
    job = {"1024+2048": f[f["size"].isin([1024, 2048])], "4096": f[f["size"] == 4096], "8192": f[f["size"] == 8192]}
    for k, x in job.items():
        per = x.groupby("rep").elapsed_s.sum() / 3600
        (lo, hi), (nlo, nhi) = EST[k]
        print(f"{k:10s} 見積もり 1 本 {lo}〜{hi} h・5 本 {nlo}〜{nhi} ノード時間 / 実績 1 本 {per.min():.2f}〜{per.max():.2f} h・"
              f"5 本 {per.sum():.2f} ノード時間（見積もりの {per.sum() / nhi:.2f}〜{per.sum() / nlo:.2f} 倍）")
    print(f"合計       見積もり 60〜80 ノード時間 / 実績 {tot / 3600:.2f}（{tot / 3600 / 80:.2f}〜{tot / 3600 / 60:.2f} 倍）")

    # 同じジョブの中の 1024 の終了と 2048 の開始の間（_meta に入らない時間の目安）
    gap = []
    for r in REPS:
        a = parse_meta(Path(str(base(1024, r)) + "_meta.txt"))
        b = parse_meta(Path(str(base(2048, r)) + "_meta.txt"))
        gap.append((b["start_time"] - a["end_time"]).total_seconds())
    print("\n1024 の終了から 2048 の開始まで [s]:", gap)

    # A/B テストの 1 点あたりの時間（見積もりのもと）
    ab = parse_meta(Path.home() / "Download/flow/flow_bind-ab_20261031_082853/meta.txt")
    print(f"A/B テスト：{ab['elapsed_s']:.0f} 秒 / 225 点 = {ab['elapsed_s'] / 225:.1f} 秒/点")
    # A/B テストと同じ 15 点（size 2048・4096・8192 × nb 64〜384、ib 32）を、スイープの 1 点あたりの時間で置き換えると
    sw = f.groupby("size").s_per_point.mean()
    print("スイープの 1 点あたりの時間 [s]:", sw.round(3).to_dict())

    used = SHOW_POINT_USED - PRE_PRODUCTION
    print(f"\nshow_point の Used {SHOW_POINT_USED} − 本番前 {PRE_PRODUCTION} = {used} ポイント = {used / (POINT_PER_SEC * 3600):.2f} ノード時間")
    print(f"_meta からの計算 {tot * POINT_PER_SEC:.1f} ポイントとの差 {used - tot * POINT_PER_SEC:.1f} ポイント"
          f" = {(used - tot * POINT_PER_SEC) / POINT_PER_SEC:.0f} 秒（15 ジョブで割ると {(used - tot * POINT_PER_SEC) / POINT_PER_SEC / 15:.1f} 秒/ジョブ）")
    r0 = parse_meta(Path(str(base_r0()) + "_meta.txt"))
    print(f"r0（テスト）の開始〜終了：{r0['elapsed_s']:.0f} 秒")


if __name__ == "__main__":
    main()


def extra():
    """見積もりが外れた理由の材料：分解の時間が nb のどこに集まっているか、A/B テストの分解の時間。"""
    import numpy as np
    from common import flops_dgeqrf
    d = load_all()
    d["small"] = np.where(d.nb < 96, "nb<96", "nb>=96")
    t = d.groupby(["size", "small"]).agg(points=("t_ms", "size"), factor_s=("t_ms", lambda v: v.sum() / 1e3))
    t["points"] = t.points / 5
    t["factor_s"] = t.factor_s / 5
    t["s_per_point"] = t.factor_s / t.points
    print("\n== スイープ 1 本の中の、分解の時間（nb < 96 とそれ以外）==")
    print(t.round(3).to_string())
    ab_dir = Path.home() / "Download/flow/flow_bind-ab_20261031_082853"
    rows = []
    for f in sorted(ab_dir.glob("bind-*_size*.csv")):
        x = pd.read_csv(f)
        x["t_s"] = flops_dgeqrf(x["size"]) / (x.GFlops * 1e9)
        rows.append(x)
    x = pd.concat(rows)
    print(f"\nA/B テスト 225 点の分解の時間の合計 {x.t_s.sum():.0f} 秒（1 点 {x.t_s.mean():.2f} 秒）。"
          f"うち nb 64 の 45 点が {x[x.nb == 64].t_s.sum():.0f} 秒")
    print(x.groupby(["size", "nb"]).t_s.mean().unstack().round(2).to_string())


if __name__ == "__main__":
    extra()
