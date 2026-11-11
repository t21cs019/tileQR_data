"""
optuna_replay_runs.csv を集計する。57条件と、EPYC 7702 の size 1024 を抜いた56条件の両方を出す。

出力（data/）:
  summary.csv          条件の集合×目的関数×範囲ごとの要約（全回をまとめた値）
  summary_by_cond.csv  条件×目的関数×範囲ごとの要約（20回の中央値・平均）と、全範囲に対する比
実行: .venv/bin/python analysis/2026-11-10_brent-search-range/scripts/summarize.py
"""
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).resolve().parents[1] / "data"
N = 100
r = pd.read_csv(D / "optuna_replay_runs.csv")
r["n95c"], r["n99c"] = r.n95.fillna(N + 1), r.n99.fillna(N + 1)     # 届かなかった回は 101 として中央値を取る
excl = (r.config == "aoba-b_s1_smt-off") & (r["size"] == 1024)
sets = {"57条件": r, "56条件（EPYC 7702 の 1024 を抜く）": r[~excl], "56条件のうち p>=24（9）": r[~excl & (r.p >= 24)],
        "p<=12（47）": r[r.p <= 12], "EPYC 7702 の 1024 だけ": r[excl]}
order = ["full", "B", "B_tau", "thr92"]
rows = []
for sname, x in sets.items():
    for (mode, rg), g in x.groupby(["mode", "range"]):
        row = dict(set=sname, mode=mode, range=rg, n_cond=g.groupby(["config", "size"]).ngroups, n_runs=len(g),
                   n95_median=g.n95c.median(), n99_median=g.n99c.median())
        for n in (10, 20, 30, 50, 100):
            row[f"reach95_within{n}"] = (g.n95c <= n).mean(); row[f"reach99_within{n}"] = (g.n99c <= n).mean()
        for n in (5, 10, 20, 30, 50, 100):
            row[f"q{n}_mean"] = g[f"q{n}"].mean(); row[f"q{n}_min"] = g[f"q{n}"].min()
        rows.append(row)
s = pd.DataFrame(rows)
s["range"] = pd.Categorical(s["range"], order); s = s.sort_values(["set", "mode", "range"], kind="stable")
s.to_csv(D / "summary.csv", index=False, float_format="%.4g")

c = r.groupby(["config", "label", "p", "size", "mode", "range"]).agg(
    lo=("lo", "first"), hi=("hi", "first"), n95_median=("n95c", "median"), n99_median=("n99c", "median"),
    reach99_within100=("n99", lambda v: v.notna().mean()), q10_mean=("q10", "mean"), q20_mean=("q20", "mean"), q50_mean=("q50", "mean"),
    q100_mean=("q100", "mean"), q100_min=("q100", "min"), cumsec20=("cumsec20", "mean"), cumsec50=("cumsec50", "mean"), cumsec100=("cumsec100", "mean")).reset_index()
f = c[c.range == "full"].set_index(["config", "size", "mode"])
for k in ("cumsec20", "cumsec50", "cumsec100"):
    c[k + "_vs_full"] = c[k].to_numpy() / f[k].reindex(pd.MultiIndex.from_frame(c[["config", "size", "mode"]])).to_numpy()
for k in ("n95_median", "n99_median", "q20_mean", "q100_mean"):
    c[k + "_full"] = f[k].reindex(pd.MultiIndex.from_frame(c[["config", "size", "mode"]])).to_numpy()
c.to_csv(D / "summary_by_cond.csv", index=False, float_format="%.4g")

pd.set_option("display.width", 250)
cols = ["mode", "range", "n95_median", "n99_median", "reach99_within50", "reach99_within100", "q10_mean", "q20_mean", "q50_mean", "q100_mean", "q20_min", "q100_min"]
for sname in sets:
    print("###", sname); print(s[s.set == sname][cols].round(3).to_string(index=False))
print("\n### 条件ごと（56条件）：全範囲との比較")
c56 = c[~((c.config == "aoba-b_s1_smt-off") & (c["size"] == 1024))]
for mode in ("single", "mean5"):
    for rg in order[1:]:
        g = c56[(c56["mode"] == mode) & (c56.range == rg)]
        print(f"{mode} {rg}: 99%までの試行 少ない {(g.n99_median < g.n99_median_full).sum()} 同じ {(g.n99_median == g.n99_median_full).sum()} 多い {(g.n99_median > g.n99_median_full).sum()}"
              f"｜条件の中央値 {g.n99_median_full.median():.0f}→{g.n99_median.median():.0f}｜95%まで {g.n95_median_full.median():.0f}→{g.n95_median.median():.0f}"
              f"｜実行時間の比 20試行 {g.cumsec20_vs_full.median():.2f}（p>=24 {g[g.p>=24].cumsec20_vs_full.median():.2f}）100試行 {g.cumsec100_vs_full.median():.2f}（p>=24 {g[g.p>=24].cumsec100_vs_full.median():.2f}）"
              f"｜100試行の到達度が全範囲より1pt以上低い条件 {(g.q100_mean < g.q100_mean_full - 0.01).sum()}")
