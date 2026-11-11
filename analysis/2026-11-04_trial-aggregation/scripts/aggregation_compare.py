"""
同じ (nb, ib) の反復の畳み方（平均・中央値・最小を捨てた平均・両端を捨てた平均・最大）で、
実測の最適 nb と、その nb の性能がどれだけ変わるかを比べる。

trial は source_file と rep の組。AOBA は1ノード1回なので、ノードが trial になる。
argmax は「各 nb で ib の最大 → nb の最大」。kurzak.load_qr_curves() と違い、
ノードごとに ib を選ばず、畳んだ後に1回だけ選ぶ。

出力:
  data/aggregation_compare.csv  (config, size) ごとの最適 nb と、平均の曲線で見た性能比
  data/trial_level.csv          trial ごとの全体の水準（点ごとの平均に対する比の中央値）
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "data"
CONFIGS = ["epyc_s1_smt-off", "aoba-b_s1_smt-off", "aoba-b_s2_smt-off"]
AGGS = ["mean", "median", "dropmin", "trim", "max"]

d = pd.read_parquet(ROOT / "derived" / "qr_sweep.parquet")
d = d[d["config"].isin(CONFIGS)].copy()
d["trial"] = d["source_file"].astype(str) + "#" + d["rep"].astype(str)

rows, levels = [], []
for (c, s), sub in d.groupby(["config", "size"], observed=True):
    p = sub.pivot_table(index=["nb", "ib"], columns="trial", values="GFlops", aggfunc="mean").dropna()
    n = p.shape[1]
    srt = np.sort(p.values, axis=1)
    agg = {
        "mean": p.mean(axis=1),
        "median": p.median(axis=1),
        "dropmin": pd.Series(srt[:, 1:].mean(axis=1), p.index),
        "trim": pd.Series(srt[:, 1:-1].mean(axis=1) if n >= 3 else srt.mean(axis=1), p.index),
        "max": p.max(axis=1),
    }
    curves = {a: v.groupby(level="nb").max() for a, v in agg.items()}
    ref = curves["mean"]
    r = {"config": c, "size": s, "trials": n,
         "cv_median_pct": round((p.std(axis=1) / p.mean(axis=1)).median() * 100, 2)}
    for a in AGGS:
        nb = int(curves[a].idxmax())
        r[f"nb_{a}"] = nb
        r[f"perf_{a}"] = round(ref[nb] / ref.max(), 4)
    per_trial = [int(p[t].groupby(level="nb").max().idxmax()) for t in p.columns]
    r["nb_per_trial_min"], r["nb_per_trial_max"] = min(per_trial), max(per_trial)
    rows.append(r)

    rel = p.div(p.mean(axis=1), axis=0).median()
    for t, v in rel.items():
        levels.append({"config": c, "size": s, "trial": t, "level": round(v, 4)})

OUT.mkdir(exist_ok=True)
res = pd.DataFrame(rows)
res.to_csv(OUT / "aggregation_compare.csv", index=False)
pd.DataFrame(levels).to_csv(OUT / "trial_level.csv", index=False)
print(res.to_string(index=False))
