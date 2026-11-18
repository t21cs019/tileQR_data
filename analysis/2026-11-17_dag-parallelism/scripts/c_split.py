"""
c：実測の余分な時間を「並列度の不足（模擬の空き）」と「残り（τ の候補）」に分ける。集計3通り × A・β 2通り。
  s        = (nb³/3)/(A·E)                     単位から秒への換算（E = nb/(nb+β)）
  T_ideal  = flops/(p·A·E)                     完全に並列なときの時間（flops は PLASMA の flops_dgeqrf。3agg と同じ）
  T_model  = flops/G_model = T_ideal + D·s     当てはめなしのモデル（c=√7.5, k=2 なら η の項はちょうど D = 30N の時間）
  T_sim    = 模擬の時間（fifo）。starv = T_sim − Σw/p ＝ 空き/p（初め・中・終わり・一度も埋まらない に分ける）
  T_obs    = flops/G_obs（3agg の a_curves.csv の各集計）
  excess   = T_obs − T_ideal、explained = starv/excess、rest = T_obs − T_sim（τ の候補）、rest_per_task = rest/タスク数
出力：data/c_split.csv（全点）、data/c_table_points.csv（予測 nb・実測の最適 nb の付近）、data/c_summary.csv（要約）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

S = pd.read_csv(DATA / "b_sim_units.csv")
C = curves()
B = pd.read_csv(AGG3 / "data/b_summary.csv")
rows = []
for kname, (A, beta) in kernel_params().items():
    for pol in ["fifo", "cp"]:
        sim = S[S.policy == pol]
        m = sim.merge(C, on=["size", "nb"])
        nb = m.nb.astype(float)
        E = nb / (nb + beta)
        s = nb**3 / 3 / (A * 1e9 * E)
        fl = flops_dgeqrf(m["size"])
        out = m[["size", "nb", "N", "tasks", "max_busy"]].copy()
        out["kernel"], out["policy"] = kname, pol
        out["T_ideal"] = fl / (P * A * 1e9 * E)
        out["T_model"] = fl / (predict(m["size"], nb, A, beta) * 1e9)
        out["D_time"] = out.T_model - out.T_ideal
        out["CP_time"] = m.CP_units * s
        out["T_sim"] = m.T_sim * s
        for c in ["idle_total", "idle_start", "idle_mid", "idle_end", "idle_never"]:
            out["starv" + c[4:]] = m[c] / P * s
        for a in AGGS:
            T_obs = fl / (m[a] * 1e9)
            out[f"T_obs_{a}"] = T_obs
            out[f"excess_{a}"] = T_obs - out.T_ideal
            out[f"explained_{a}"] = out["starv_total"] / out[f"excess_{a}"]
            out[f"rest_{a}"] = T_obs - out.T_sim
            out[f"rest_per_task_us_{a}"] = out[f"rest_{a}"] / m.tasks * 1e6
        rows.append(out)
df = pd.concat(rows, ignore_index=True)
df.to_csv(DATA / "c_split.csv", index=False)

# 予測 nb と実測の最適 nb（集計ごと）とその両隣
pts = []
for kname in kernel_params():
    b = B[B.kernel == kname]
    for size in SIZES:
        bs = b[b["size"] == size]
        cand = {("pred", int(bs.nb_pred.iloc[0]))}
        for _, r in bs[bs["agg"].isin(AGGS)].iterrows():
            cand.add((f"opt_{r["agg"]}", int(r["nb_obs"])))
        step = 8 if size == 8192 else 4
        for tag, nb0 in sorted(cand, key=lambda x: x[1]):
            for nb in [nb0 - step, nb0, nb0 + step] if tag.startswith("opt") else [nb0]:
                pts.append(dict(kernel=kname, size=size, nb=nb, tag=tag if nb == nb0 else "near"))
P_ = pd.DataFrame(pts).drop_duplicates(["kernel", "size", "nb"], keep="first")
T = P_.merge(df[df.policy == "fifo"], on=["kernel", "size", "nb"], how="left")
T.to_csv(DATA / "c_table_points.csv", index=False)
pd.set_option("display.width", 250)
cols = ["kernel", "size", "nb", "tag", "N", "tasks", "max_busy", "T_ideal", "D_time", "T_sim", "starv_total",
        "starv_start", "starv_mid", "starv_end", "starv_never", "T_obs_fast", "explained_fast", "explained_slow", "explained_mean",
        "rest_per_task_us_fast", "rest_per_task_us_mean"]
X = T[T.kernel == "ib=nb/8"][cols].copy()
for c in ["T_ideal", "D_time", "T_sim", "starv_total", "starv_start", "starv_mid", "starv_end", "starv_never", "T_obs_fast"]:
    X[c] = (X[c] * 1e3).round(3)
print(X.round(3).to_string(index=False))

# 要約：集計ごとの予測 nb・実測の最適 nb で、A・β 2通り × policy 2通り → data/c_summary.csv
rows = []
for _, b in B[B["agg"].isin(AGGS)].iterrows():
    for which, nb in [("pred", b.nb_pred), ("opt", b.nb_obs)]:
        for pol in ["fifo", "cp"]:
            r = df[(df.kernel == b.kernel) & (df.policy == pol) & (df["size"] == b["size"]) & (df.nb == nb)]
            if len(r) == 0:
                continue
            r = r.iloc[0]; a = b["agg"]
            rows.append(dict(kernel=b.kernel, agg=a, size=b["size"], which=which, nb=nb, policy=pol, max_busy=r.max_busy,
                             explained=r[f"explained_{a}"], starv_ms=r.starv_total * 1e3, starv_start_ms=r.starv_start * 1e3,
                             starv_end_ms=r.starv_end * 1e3, starv_never_ms=r.starv_never * 1e3, D_ms=r.D_time * 1e3,
                             T_sim_over_T_model=r.T_sim / r.T_model, T_obs_ms=r[f"T_obs_{a}"] * 1e3,
                             excess_ms=r[f"excess_{a}"] * 1e3, rest_ms=r[f"rest_{a}"] * 1e3))
pd.DataFrame(rows).to_csv(DATA / "c_summary.csv", index=False)
