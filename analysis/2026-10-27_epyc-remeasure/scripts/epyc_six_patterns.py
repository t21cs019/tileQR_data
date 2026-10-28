"""
EPYC 7543 で、(c, k) 3通り × β 2通り = 6パターンの予測性能比を比べる。

(c, k)
  theory  : c = √7.5, k = 2（Brent の定理から）
  k_fit   : c = √7.5 に固定し、k だけを中間40条件に当てはめる
  ck_fit  : c, k とも中間40条件に当てはめる（../data/fold_constants.csv の ALL 行と同じ手続き）
  当てはめは差し替え後のデータで、β は fold_constants.py の値（BETA_FOLD）。
  「全点」は40条件すべて、「LOAO」は EPYC 7543 を抜いた36条件で当てはめた値。
β
  1core : 184.2（DTSMQR を1コアで計測、MAT_SIZE 1024/2048/8192 の当てはめの中央値。4096 は誤差 11.5% で除外）
  multi : 143.6（DTSMQR を32本同時に計測、MAT_SIZE 1024、ib = nb/8 断面）
  参考に、32本同時と同じ方法で1本だけ動かした p=1 の β（173.1）も出す。

出力: ../s1_smt-off/data/epyc_six_patterns.csv
--set 57 で、c, k を57条件（13機種 × 全サイズ、fold_constants57.py と同じ）に当てはめる。
「LOAO」は EPYC 7543 の5サイズを抜いた52条件。出力は epyc_six_patterns57.csv
"""
import os
import sys

os.environ.setdefault("TILEQR_SUBSET", "s1_smt-off")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import BETA_FOLD, CONFIGS40, GEN3_FIXED, OUT, SIZES40, eta_x, kurzak, load_curves  # noqa: E402

CFG, P = "epyc_s1_smt-off", 32.0
SIZES = [1024, 2048, 4096, 8192, 16384]
BETAS = {"1core": 184.2, "multi": 143.6, "p1_ref": 173.1}


SET57 = "--set" in sys.argv and sys.argv[sys.argv.index("--set") + 1] == "57"


def train_set(df):
    """当てはめに使う条件と β。中間40条件（BETA_FOLD）か、57条件（task_a_table の β）。"""
    if not SET57:
        return df[df.config.isin(CONFIGS40) & df["size"].isin(SIZES40)], BETA_FOLD
    tab = pd.read_csv(OUT / "data/task_a_table.csv")
    conds = set(zip(tab.config, tab["size"]))
    d = df[[(c, s) in conds for c, s in zip(df.config, df["size"])]]
    arch = d.groupby("config")["arch"].first()
    return d, {arch[c]: b for c, b in tab.groupby("config")["beta"].first().items()}


def fit_ck(df, fix_c=None, exclude=None):
    d, beta = train_set(df)
    if exclude:
        d = d[d.config != exclude]
    fixed = dict(GEN3_FIXED) if fix_c is None else dict(GEN3_FIXED, c2=fix_c)
    r = kurzak.fit(d, fixed=fixed, beta_fixed=beta)
    return r["c2"], r["kappa"]


def main():
    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)].reset_index(drop=True)
    obs = kurzak.observed(df)
    c0 = np.sqrt(7.5)
    consts = {}
    for scope, ex in [("全点", None), ("LOAO", CFG)]:
        consts[("theory", scope)] = (c0, 2.0)
        consts[("k_fit", scope)] = fit_ck(df, fix_c=c0, exclude=ex)
        consts[("ck_fit", scope)] = fit_ck(df, exclude=ex)
    for k, v in consts.items():
        print(f"{k[0]:7s} {k[1]:4s} c = {v[0]:.4f}  k = {v[1]:.4f}")

    rows = []
    for (ck, scope), (c, k) in consts.items():
        for bname, beta in BETAS.items():
            for size in SIZES:
                t = obs[(CFG, size)]
                f = t["nb"] / (t["nb"] + beta) * eta_x(t["nb"], float(size), P, c, k)
                i = int(np.argmax(f))
                rows.append(dict(ck=ck, scope=scope, beta_src=bname, beta=beta, c=c, k=k, size=size,
                                 nb_opt=t["nb_opt"], nb_pred=t["nb"][i], perf=100 * t["G"][i] / t["peak"]))
    r = pd.DataFrame(rows)
    r.round(4).to_csv(OUT / f"data/epyc_six_patterns{'57' if SET57 else ''}.csv", index=False)
    for scope in ["全点", "LOAO"]:
        s = r[r.scope == scope]
        tab = s.pivot_table(index=["ck", "beta_src"], columns="size", values="perf", sort=False)
        tab["平均"] = tab.mean(axis=1)
        nb = s.pivot_table(index=["ck", "beta_src"], columns="size", values="nb_pred", sort=False)
        print(f"\n== {scope}（性能比 %）\n{tab.round(1).to_string()}\n-- 予測 nb\n{nb.astype(int).to_string()}")
    print("\n実測最適 nb:", {s: obs[(CFG, s)]["nb_opt"] for s in SIZES})


if __name__ == "__main__":
    main()
