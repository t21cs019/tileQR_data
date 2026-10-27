import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).parent
d = pd.read_csv(HERE / "sim.csv")
# EPYC 1024/2048 は 2026-10-27 の再計測に差し替えたので、全条件を使う
d["lr"] = np.log(d.t_meas / d.t_sim)
pd.set_option("display.width", 220)

def pred(g):
    """sim が最短になる nb での実測性能 / 実測ピーク"""
    i = g.t_sim.idxmin()
    return pd.Series(dict(nb_opt=g.loc[g.G.idxmax(), "nb"], nb_sim=g.loc[i, "nb"], perf=g.loc[i, "G"] / g.G.max() * 100))

# 1. オーバーヘッドなし
z = d[(d.o == 0) & (d.L == 0)]
print("== オーバーヘッドなし: 実測時間 / シミュレーション時間 ==")
for (cfg, src, size), g in z.groupby(["config", "src", "size"]):
    g = g.set_index("nb")
    pick = [n for n in [32, 64, 96, 128, 192, 256, 384, 512] if n in g.index]
    r = " ".join(f"{n}:{g.loc[n,'t_meas']/g.loc[n,'t_sim']:.2f}" for n in pick)
    p = pred(g.reset_index())
    print(f"{cfg:22s} {src:8s} {size:5d}  {r}   nb実測={p.nb_opt:.0f} nb_sim={p.nb_sim:.0f} 性能比={p.perf:.1f}%")

# 2. 構成ごとに (o, L) を当てはめる。カーネルの実効速度の違いは倍率 s で吸収（s は log 残差の平均）
def fit(sub):
    best = None
    for (o, L), g in sub.groupby(["o", "L"]):
        s = g.lr.mean()
        err = np.mean(np.abs(g.lr - s))
        if best is None or err < best[0]:
            best = (err, o, L, np.exp(s))
    return best

print("\n== 構成ごとの当てはめ（3サイズまとめて, 誤差 = 平均 |log(実測/sim)|） ==")
rows = []
for (cfg, src), sub in d.groupby(["config", "src"], sort=False):
    res = {}
    for name, m in [("なし", (sub.o == 0) & (sub.L == 0)), ("o のみ", sub.L == 0),
                    ("L のみ", sub.o == 0), ("o と L", slice(None))]:
        err, o, L, s = fit(sub[m])
        best = sub[(sub.o == o) & (sub.L == L)].copy()
        best["t_sim"] = best.t_sim * s
        pr = best.groupby("size").apply(pred, include_groups=False)
        res[name] = (err, o, L, s, pr)
        rows.append(dict(config=cfg, src=src, model=name, err=round(err * 100, 1), o_us=o * 1e6, L_us=L * 1e6,
                         scale=round(s, 2), **{f"perf{sz}": round(pr.loc[sz, "perf"], 1) for sz in pr.index},
                         **{f"nb{sz}": f"{pr.loc[sz,'nb_sim']:.0f}/{pr.loc[sz,'nb_opt']:.0f}" for sz in pr.index}))
r = pd.DataFrame(rows)
print(r.to_string(index=False))
r.to_csv(HERE / "fit_summary.csv", index=False)

print("\n== サイズごとに別々に当てはめた場合（o と L） ==")
for (cfg, src, size), sub in d.groupby(["config", "src", "size"], sort=False):
    err, o, L, sc = fit(sub)
    b = sub[(sub.o == o) & (sub.L == L)].copy(); b["t_sim"] *= sc
    p = pred(b)
    print(f"{cfg:22s} {src:8s} {size:5d} o={o*1e6:5.0f}us L={L*1e6:5.0f}us scale={sc:5.2f} err={err*100:4.1f}%  nb {p.nb_sim:.0f}/{p.nb_opt:.0f} 性能比 {p.perf:.1f}%")
