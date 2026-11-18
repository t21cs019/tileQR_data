"""a. 不老・弐の QR を3通り（＋感度2通り）で集計し、(size, nb) ごとに ib について最大を取った曲線を作る。

集計（点 (nb, ib) ごと）
- fast：速い水準 = add_baseline の base（時間）を GFlops に直したもの（2026-11-10 report.md C 節「用語」、C6 の推奨）
- slow：遅い水準だけ = ex = t − base > SLOW_MS（6 ms）の実行だけの GFlops の平均（同 C 節「用語」の ex > 6 ms）。
        遅い実行が無い点は NaN（ib の最大から外れる）
- mean：5 回の GFlops の平均（ingest.py、11-11 の c_qr.py の G_mean と同じ）
感度
- slow_dt：base の時間 + ΔT（report.md C2 の値）を GFlops に直したもの。遅い水準の判定を点ごとにしない版
- median：5 回の GFlops の中央値（report.md C6 で「感度として並べる」とされたもの）

出力 data/a_points.csv（点ごと）、data/a_curves.csv（(size, nb) ごとの ib 最大）、data/a_counts.csv（遅い実行の数）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from common import DATA, DT_REPORT, sw  # noqa: E402


def main():
    d = sw.add_baseline(sw.load_all())
    d["slow"] = d.ex > sw.SLOW_MS
    fl = sw.flops_dgeqrf(d["size"])
    d["G_slowrun"] = np.where(d.slow, d.GFlops, np.nan)
    pt = d.groupby(["size", "nb", "ib"], as_index=False).agg(
        mean=("GFlops", "mean"), median=("GFlops", "median"), base_ms=("base", "first"),
        slow=("G_slowrun", "mean"), n_slow=("slow", "sum"))
    fl = sw.flops_dgeqrf(pt["size"])
    pt["fast"] = fl / (pt.base_ms * 1e-3) / 1e9
    pt["slow_dt"] = fl / ((pt.base_ms + pt["size"].map(DT_REPORT)) * 1e-3) / 1e9
    pt.to_csv(DATA / "a_points.csv", index=False, float_format="%.5g")

    aggs = ["fast", "slow", "mean", "slow_dt", "median"]
    c = pt.groupby(["size", "nb"], as_index=False)[aggs].max()
    c.to_csv(DATA / "a_curves.csv", index=False, float_format="%.5g")

    # 遅い実行の数：全体の割合と、遅い実行の無い点（slow が NaN）の数。判定が信頼できる範囲（NB_CLASS 以上）とそれ未満
    pt["reliable"] = pt.nb >= pt["size"].map(sw.NB_CLASS)
    cnt = pt.groupby(["size", "reliable"]).agg(points=("n_slow", "size"), slow_frac=("n_slow", lambda x: x.sum() / (5 * len(x))),
                                               no_slow_points=("n_slow", lambda x: int((x == 0).sum()))).reset_index()
    cnt.to_csv(DATA / "a_counts.csv", index=False, float_format="%.4f")
    print(cnt.to_string(index=False))
    print(c.groupby("size")[aggs].max().round(1))


if __name__ == "__main__":
    main()
