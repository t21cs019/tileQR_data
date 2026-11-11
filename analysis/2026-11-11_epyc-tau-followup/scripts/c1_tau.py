"""計測 C1：中身 0 / 20000 / 100000 ns の空タスク。中央値と、直列・並列モデルの予測。"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import C1_CSV, C10_CSV, OUT

d = pd.read_csv(C1_CSV)
d["per_task_us"] = d.total_sec / d.ntasks * 1e6
d["sub_ratio"] = d.submit_sec / d.total_sec
g = d.groupby(["runtime", "tiles", "threads", "work_ns"]).agg(
    n=("tau_us", "size"), tau=("tau_us", "median"), tau_min=("tau_us", "min"), tau_max=("tau_us", "max"),
    per_task=("per_task_us", "median"), sub_ratio=("sub_ratio", "median")).reset_index()
t0 = g[g.work_ns == 0].set_index(["runtime", "tiles", "threads"]).tau
g["tau0"] = [t0[(r, t, p)] for r, t, p in zip(g.runtime, g.tiles, g.threads)]
g["work_per_p"] = g.work_ns / g.threads / 1e3
g["pred_serial"] = np.maximum(g.tau0 - g.work_per_p, 0)        # max(τ0, 中身/p) − 中身/p
g["pred_parallel"] = g.tau0                                     # (中身 + o)/p − 中身/p = o/p = τ0
g["pred_master_idle"] = g.work_ns / 1e3 / (g.threads * (g.threads - 1))  # 投げる1本が実行しない：中身/(p−1) − 中身/p
g["o_per_core"] = g.tau * g.threads                             # 並列と見たときの、1タスクを実行したコアの余分な時間
g.to_csv(OUT / "c1_tau.csv", index=False, float_format="%.4f")

pd.set_option("display.width", 220)
tiles = int(sys.argv[1]) if len(sys.argv) > 1 else 128
cols = ["runtime", "threads", "work_ns", "tau", "tau_min", "tau_max", "sub_ratio", "work_per_p", "pred_serial", "pred_parallel", "pred_master_idle"]
print(f"tiles = {tiles}")
print(g[g.tiles == tiles][cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))

if tiles == 128:
    # 11-10 との比較（中身 0）
    a = pd.read_csv(C10_CSV)
    a = a[(a.work_ns == 0) & a.threads.isin([4, 8, 16, 32]) & a.tiles.isin([64, 128])]
    m = a.groupby(["runtime", "tiles", "threads"]).tau_us.median().rename("tau_1110").reset_index()
    m = m.merge(g[g.work_ns == 0][["runtime", "tiles", "threads", "tau"]].rename(columns={"tau": "tau_1111"}))
    m.to_csv(OUT / "c1_work0_vs_1110.csv", index=False, float_format="%.4f")
    print(m[m.tiles == 128].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
