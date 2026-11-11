"""
A/B テストの GFlops を実行時間に直し、「固定なしで増える時間」と「タスク1個あたりの時間」を出す。

  時間       = W / GFlops、W = 4/3·size³
  タスク数   = Σ_{k=1..N} k² = N(N+1)(2N+1)/6、N = ceil(size/nb)（各ステップ k で (N−k+1)² 個）
各点は5回の中央値。

入力: data/bind_ab_points.csv（collect_bind_ab.py の出力）
出力: data/bind_ab_time.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"


def main():
    d = pd.read_csv(DATA / "bind_ab_points.csv")
    g = d.groupby(["machine", "p", "size", "nb", "cond"]).GFlops.median().unstack("cond").reset_index()
    N = np.ceil(g["size"] / g.nb)
    g["tasks"] = N * (N + 1) * (2 * N + 1) / 6
    W = 4 / 3 * g["size"] ** 3
    g["t_none_ms"] = W / g["none"] / 1e6
    g["t_close_ms"] = W / g["close"] / 1e6
    g["lost_ms"] = g.t_none_ms - g.t_close_ms
    g["us_per_task_none"] = g.t_none_ms * 1e3 / g.tasks
    g["us_per_task_close"] = g.t_close_ms * 1e3 / g.tasks
    g = g.rename(columns={"none": "G_none", "close": "G_close", "close-intlv": "G_close_intlv"})
    g.to_csv(DATA / "bind_ab_time.csv", index=False, float_format="%.5g")
    cols = ["machine", "size", "nb", "G_none", "G_close", "t_none_ms", "t_close_ms", "lost_ms", "us_per_task_none",
            "us_per_task_close"]
    print(g[cols].to_string(index=False, float_format="%.1f"))


if __name__ == "__main__":
    main()
