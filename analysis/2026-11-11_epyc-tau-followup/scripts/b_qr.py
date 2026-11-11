"""計測 B：p = 1, 2, 4 の QR。1タスクあたりの全時間と、p=4 基準・p=1 基準の余分な時間。"""
import sys
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import B_CSV, B10_CSV, OUT, ntasks, eta, qr_time

b = pd.read_csv(B_CSV); b["day"] = "11-11"
a = pd.read_csv(B10_CSV); a["day"] = "11-10"
a = a[a.nb.isin([32, 64]) & a["size"].isin([4096, 8192])]
print("11-10 の条件:", sorted(a.threads.unique()), sorted(a["size"].unique()), "ib:", sorted(a.ib.unique()))
d = pd.concat([a, b])
g = d.groupby(["day", "size", "nb", "ib", "threads"]).GFlops.agg(["median", "min", "max", "count"]).reset_index()
g["nt"] = [ntasks(s, n) for s, n in zip(g["size"], g.nb)]
g["T"] = [qr_time(s, m) for s, m in zip(g["size"], g["median"])]
g["per_task_us"] = g["T"] / g.nt * 1e6
g["eta"] = [eta(n, s, p) for n, s, p in zip(g.nb, g["size"], g.threads)]

rows = []
for (day, size, nb), x in g.groupby(["day", "size", "nb"]):
    x = x.set_index("threads")
    # 基準は同じ日の p=4。p=1 基準は 11-11 の p=1（11-10 には p=1 がない）
    ref4 = x.loc[4]
    b1 = g[(g.day == "11-11") & (g["size"] == size) & (g.nb == nb) & (g.threads == 1)].iloc[0]
    for p, r in x.iterrows():
        ideal4 = ref4.per_task_us * (4 * ref4.eta) / (p * r.eta)
        ideal1 = b1.per_task_us * (1 * b1.eta) / (p * r.eta)
        rows.append(dict(day=day, size=size, nb=nb, ib=int(r.ib), p=p, n=int(r["count"]), gflops=r["median"],
                         ntasks=int(r.nt), per_task_us=r.per_task_us, eta=r.eta,
                         extra_p4base_us=r.per_task_us - ideal4, extra_p1base_us=r.per_task_us - ideal1))
out = pd.DataFrame(rows).sort_values(["size", "nb", "day", "p"])
out.to_csv(OUT / "b_per_task.csv", index=False, float_format="%.4f")
pd.set_option("display.width", 200)
print(out.drop(columns=["ib", "n", "ntasks"]).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

# p=4 の日による差
m = out[out.p == 4].pivot(index=["size", "nb"], columns="day", values="gflops")
m["diff_%"] = (m["11-11"] / m["11-10"] - 1) * 100
print(m.to_string(float_format=lambda v: f"{v:.2f}"))

# p=1 と p=4 の2点から、τ = 一定 と τ = a·p をそれぞれ解く（η ≈ 1 と置く）
x = out[out.day == "11-11"].pivot(index=["size", "nb"], columns="p", values="per_task_us")
x["tau_const"] = (4 * x[4] - x[1]) / 3            # T1 = k + τ,  T4 = k/4 + τ
x["a_prop"] = (4 * x[4] - x[1]) / 15              # T1 = k + a,  T4 = k/4 + 4a
x["tau32_prop"] = 32 * x["a_prop"]
x["p2_pred_const"] = (x[1] - x["tau_const"]) / 2 + x["tau_const"]
x["total_p32_1110"] = out[(out.day == "11-10") & (out.p == 32)].set_index(["size", "nb"]).per_task_us
x.to_csv(OUT / "b_two_point_models.csv", float_format="%.4f")
print(x.to_string(float_format=lambda v: f"{v:.2f}"))
