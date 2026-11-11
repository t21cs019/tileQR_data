"""1. データの確認：格子、回ごとのばらつき、外れ点、回の順の傾向、クロック。出力 data/a_*.csv"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python -I でも common を読めるようにする

import numpy as np
import pandas as pd

from common import DATA, load_clock, load_epyc, load_flow2  # noqa: E402

pd.set_option("display.width", 200)


def spread(d, name):
    w = d.pivot_table(index=["nb", "ib"], columns="rep", values="GFlops")
    med = w.median(axis=1)
    sp = (w.max(axis=1) - w.min(axis=1)) / med
    q = sp.quantile([0.5, 0.9, 0.99]).round(4).tolist()
    print(f"[{name}] 点数 {len(w)}  (max-min)/median: 中央 {q[0]:.4f}  90% {q[1]:.4f}  99% {q[2]:.4f}  最大 {sp.max():.3f}"
          f"  >2% {int((sp > 0.02).sum())} 点  >5% {int((sp > 0.05).sum())} 点")
    return w, med, sp


def main():
    d = load_flow2()
    # 格子
    exp = [(nb, ib) for nb in range(32, 513, 4) for ib in range(8, nb // 2 + 1, 4)]
    for r, g in d.groupby("rep"):
        ok = list(zip(g.nb, g.ib)) == exp
        print(f"r{r}: 行 {len(g)}  格子と順が期待どおり {ok}  threads {set(g.threads)} size {set(g['size'])}"
              f"  NaN {int(g.GFlops.isna().sum())}  GFlops≤0 {int((g.GFlops <= 0).sum())}")
    w, med, sp = spread(d, "flow2")
    # 外れ点：回ごとに、中央値からの相対差
    dev = w.div(med, axis=0) - 1
    rows = []
    for r in w.columns:
        x = dev[r]
        rows.append(dict(rep=r, mean_dev=x.mean(), median_dev=x.median(), n_low2=int((x < -0.02).sum()),
                         n_low5=int((x < -0.05).sum()), n_high2=int((x > 0.02).sum()), min_dev=x.min(), max_dev=x.max()))
    t = pd.DataFrame(rows)
    t.to_csv(DATA / "a_rep_deviation.csv", index=False, float_format="%.5f")
    print(t.round(4).to_string(index=False))
    out = dev.stack().rename("dev").reset_index()
    out = out[out.dev.abs() > 0.05].sort_values("dev")
    out.to_csv(DATA / "a_outliers_gt5pct.csv", index=False, float_format="%.4f")
    print("5% を超えて外れた (点, 回)：", len(out))
    print(out.head(12).round(3).to_string(index=False))
    # 最初の点（起動直後）
    print("最初の点 (nb 32, ib 8) の GFlops：", d[(d.nb == 32) & (d.ib == 8)].GFlops.round(3).tolist())
    # nb 帯ごとのばらつき
    b = pd.cut(sp.index.get_level_values("nb"), [31, 63, 127, 255, 383, 512])
    print("nb 帯ごとの (max-min)/median の中央値・95%：")
    print(sp.groupby(b, observed=True).quantile([0.5, 0.95]).unstack().round(4).to_string())
    # クロック
    c = load_clock()
    ct = c.groupby("rep").mhz.agg(["count", "mean", "median", "min", "max"]).round(1)
    ct.to_csv(DATA / "a_clock.csv")
    print(ct.to_string())
    print("3740 MHz 未満の記録：", c[c.mhz < 3740][["time", "mhz", "rep"]].values.tolist())
    # 比較：EPYC 7543
    e = load_epyc()
    spread(e, "epyc-7543")
    ew = e.pivot_table(index=["nb", "ib"], columns="rep", values="GFlops")
    print("EPYC 回ごとの中央値からの平均差：", (ew.div(ew.median(axis=1), axis=0) - 1).mean().round(4).tolist(),
          " 行数", e.groupby("rep").size().tolist())


if __name__ == "__main__":
    main()
