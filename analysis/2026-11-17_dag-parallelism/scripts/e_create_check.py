"""
e：方法 (c) の確認。主スレッドがタスクを作った順に1個ずつ c 秒で作る（タスク i は時刻 (i+1)·c より前に始まらない）として模擬し、
模擬の時間が実測に一致する c を二分法で求める（「残りをタスクの生成だけで説明するなら、1個あたり何 µs 要るか」）。
目標は2通り：T_obs そのもの、T_obs − c0（d の式1、size ごとの c0。一定の時間を先に除いた場合）。
点は予測 nb と、集計ごとの実測の最適 nb。A・β は ib=nb/8、fifo。
出力：data/e_create_check.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

A, beta = kernel_params()["ib=nb/8"]
T = pd.read_csv(DATA / "c_table_points.csv")
T = T[(T.kernel == "ib=nb/8") & (T.tag != "near")]
F = pd.read_csv(DATA / "d_rest_fit.csv")
F = F[(F.form == "式1") & (F.scope != "all")]
cache = {}
rows = []
for _, r in T.drop_duplicates(["size", "nb"]).iterrows():
    size, nb = int(r["size"]), int(r["nb"])
    kind, fl, by, pr = build_dag(size, nb)
    w = weights(fl, by, nb, A, beta)
    n = len(w)
    idx = np.arange(1, n + 1)

    def T_of(c):
        st, fi = simulate(w, pr, release=idx * c)
        return fi.max()
    for a in AGGS:
        T_obs = r[f"T_obs_{a}"]
        c0 = F[(F["agg"] == a) & (F.scope == str(size))].c0_ms.iloc[0] / 1e3
        for target_name, target in [("T_obs", T_obs), ("T_obs-c0", T_obs - c0)]:
            if target <= T_of(0.0):
                c_need = 0.0
            else:
                lo, hi = 0.0, target / n * 1.01
                while T_of(hi) < target:
                    hi *= 2
                for _ in range(30):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if T_of(mid) < target else (lo, mid)
                c_need = (lo + hi) / 2
            rows.append(dict(size=size, nb=nb, tag=r["tag"], agg=a, target=target_name, tasks=n,
                             T_target_ms=target * 1e3, T_sim0_ms=T_of(0.0) * 1e3,
                             c_needed_us=c_need * 1e6, n_times_c_ms=n * c_need * 1e3))
    print(size, nb, flush=True)
R = pd.DataFrame(rows)
R.to_csv(DATA / "e_create_check.csv", index=False)
print(R[R.target == "T_obs"].round(2).to_string(index=False))
print(R[R.target == "T_obs-c0"].round(2).to_string(index=False))
