"""2026-10-21（s1_smt-off）と、EPYC 1024/2048 を差し替えた再実行の主要な数字を並べる。"""
from pathlib import Path
import pandas as pd

A = Path(__file__).resolve().parents[2]
OLD, NEW = A / "2026-10-21/s1_smt-off/data", A / "2026-10-27_epyc-remeasure/s1_smt-off/data"


def summ(t, col):
    s = t[col].dropna()
    big = t.p >= 24
    return dict(n=len(s), mean=100 * s.mean(), min=100 * s.min(), below95=int((s < .95).sum()),
                big_below95=int((t.loc[big, col].dropna() < .95).sum()), n_big=int(big.sum()),
                big_mean=100 * t.loc[big, col].mean(), small_mean=100 * t.loc[~big, col].mean(),
                small_min=100 * t.loc[~big, col].min())


rows = []
for name, d in [("10-21", OLD), ("10-27", NEW)]:
    t = pd.read_csv(d / "task_a_table.csv")
    for col in ["perf", "perf_zs"]:
        rows.append(dict(data=name, metric=f"task_a.{col}", **summ(t, col)))
    lo = pd.read_csv(d / "loao_subset.csv")
    for m, g in lo.groupby("model"):
        rows.append(dict(data=name, metric=f"loao_subset.{m}", **summ(g, "perf")))
r = pd.DataFrame(rows)
print(r.round(1).to_string(index=False))
r.round(2).to_csv(NEW / "compare_1021.csv", index=False)

t_old = pd.read_csv(OLD / "task_a_table.csv"); t_new = pd.read_csv(NEW / "task_a_table.csv")
k = ["config", "size"]
m = t_old[k + ["label", "p", "nb_opt", "nb_pred", "perf", "perf_zs", "WpD"]].merge(
    t_new[k + ["nb_opt", "nb_pred", "perf", "perf_zs", "WpD"]], on=k, suffixes=("_old", "_new"))
print("\n95% 未満の条件（どちらかで）")
sel = (m.perf_zs_old < .95) | (m.perf_zs_new < .95) | (m.perf_old < .95) | (m.perf_new < .95)
print(m[sel].round(3).to_string(index=False))
