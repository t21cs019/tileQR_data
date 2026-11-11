"""
τ なしの理論モデル（A·E·η、c・k は理論値）で、上限の η と下限の η から探索範囲を2通り作り、実測の最適 nb が入るかを数える。
  A：上限の η の予測 nb から、下限の η の予測 nb まで
  B：下限の η での性能（天井）が、上限の η での性能（床）の最大以上になる nb
57条件のほか、参考として2ソケット・SMT 有効の6構成26条件も見る。標準出力は data/range_two_ways.log に残した。
→ data/range_two_ways.csv（条件 × 作り方ごと）
実行: .venv/bin/python analysis/2026-11-10_brent-search-range/scripts/range_two_ways.py
"""
import sys
from pathlib import Path
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent / "2026-11-10_serial-task-cost" / "scripts"))
import numpy as np, pandas as pd
from common10 import load_s1, load_all

def prep(d):
    d = d.copy()
    d["y"] = d.p * d.D / (4 * d.N**3)
    d["E"] = d.nb / (d.nb + d.beta_k)
    d["f_lo"] = d.E / (1 + d.y)              # 上限の時間 → 性能の床
    d["f_hi"] = d.E * np.minimum(1, 1 / d.y) # 下限の時間 → 性能の天井
    return d

def run(d, how):
    rows = []
    for (c, s), g in d.groupby(["config", "size"]):
        g = g.sort_values("nb")
        if how == "A":   # 2つの予測 nb の間
            lo, hi = g.nb[g.f_lo.idxmax()], g.nb[g.f_hi.idxmax()]
            keep = (g.nb >= min(lo, hi)) & (g.nb <= max(lo, hi))
        else:            # 天井が、床の最大以上の nb
            keep = g.f_hi >= g.f_lo.max()
        i = g.G.idxmax()
        rows.append(dict(config=c, label=g.label.iloc[0], p=g.p.iloc[0], size=s, lo=g.nb[keep].min(), hi=g.nb[keep].max(),
                         nb_opt=g.nb[i], hit=bool(keep[i]), frac=keep.mean(), n_keep=keep.sum(), n=len(g),
                         best_in=g.G[keep].max() / g.G.max(), nb_min=g.nb.min(), nb_max=g.nb.max()))
    return pd.DataFrame(rows)

def show(r, name):
    print(f"{name}: 最適 nb を含む {r.hit.sum()}/{len(r)}｜範囲内の最高÷全体の最高 平均 {100*r.best_in.mean():.1f} 最低 {100*r.best_in.min():.1f}｜"
          f"99%以上 {(r.best_in>=0.99).sum()} 95%以上 {(r.best_in>=0.95).sum()}｜残す割合 平均 {100*r.frac.mean():.0f}%（{100*r.frac.min():.0f}〜{100*r.frac.max():.0f}%）｜上端が格子の端 {(r.hi==r.nb_max).sum()}")

ALL = []
s1 = prep(load_s1())
al = prep(load_all())
ex = al[~al.config.isin(s1.config.unique())]
for how, nm in (("A", "A：2つの予測 nb の間"), ("B", "B：天井 ≥ 床の最大")):
    print("\n####", nm)
    r = run(s1, how); show(r, "57条件"); ALL.append(r.assign(how=how, scope="s1_smt-off"))
    for k, m in (("p>=24", r.p >= 24), ("p<=12", r.p <= 12)): show(r[m], "  " + k)
    print("  外れた条件:"); print(r[~r.hit][["label", "p", "size", "lo", "hi", "nb_opt", "best_in"]].round(3).to_string(index=False))
    print("  size別:", r.groupby("size").agg(hit=("hit", "sum"), n=("hit", "size"), frac=("frac", "mean")).round(2).to_dict("index"))
    if how == "B": rB = r
    else: rA = r
    r2 = run(ex, how); ALL.append(r2.assign(how=how, scope="extra")); show(r2, "参考：2ソケット・SMT有効（" + str(ex.config.nunique()) + "構成）")
    print(r2[~r2.hit].groupby("config").agg(miss=("hit", "size"), worst=("best_in", "min")).round(3).to_string())
print("\n#### 57条件の一覧（A の範囲 / B の範囲 / 実測の最適）")
m = rA.merge(rB, on=["config", "size"], suffixes=("_A", "_B"))
m["A"] = m.lo_A.astype(str) + "-" + m.hi_A.astype(str); m["B"] = m.lo_B.astype(str) + "-" + m.hi_B.astype(str)
print(m[["label_A", "p_A", "size", "A", "B", "nb_opt_A", "hit_A", "hit_B", "best_in_A"]].round(3).to_string(index=False))
print("格子:", s1.groupby("config").nb.agg(["min", "max", "nunique"]).drop_duplicates().to_string())

pd.concat(ALL).drop(columns=["nb_min", "nb_max"]).to_csv(OUT / "data" / "range_two_ways.csv", index=False, float_format="%.4g")
