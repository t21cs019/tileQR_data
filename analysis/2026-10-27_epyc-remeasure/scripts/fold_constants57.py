"""
57条件（HT 無効・1ソケットの13機種、size 1024〜16384）すべてで leave-one-arch-out。

fold_constants.py は中間40条件（10機種 × 1024〜8192）だけで当てはめるので、
追加の17条件（新しい3機種と size 16384）は当てはめに入らない。ここでは
57条件を当てはめに使い、1機種ずつ（その機種の全サイズを）抜いて c, k を当てはめ直す。

c, k の当てはめは fold_constants.py と同じ（kurzak.fit、m=0.5, delta=1.0, ke=0.0 固定、
β は測定値で固定）。β は ../s1_smt-off/data/task_a_table.csv の値
（中間10機種は BETA_FOLD、追加3機種は raw/ssrfb の MRE≤5% 平均）。
出力は ../data/fold_constants57.csv（held_out_config = config キー、ALL 行 = 57条件全点）。
"""
import os
import sys
from pathlib import Path

import pandas as pd

os.environ["TILEQR_SUBSET"] = "s1_smt-off"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GEN3_FIXED, BASE, kurzak, load_curves  # noqa: E402


def main():
    tab = pd.read_csv(BASE / "s1_smt-off/data/task_a_table.csv")
    conds = set(zip(tab.config, tab["size"]))
    df = load_curves()
    df = df[[(c, s) in conds for c, s in zip(df.config, df["size"])]].reset_index(drop=True)
    if df.groupby("g").ngroups != 57:
        raise SystemExit(f"条件数が57でない: {df.groupby('g').ngroups}")
    arch = df.groupby("config")["arch"].first()
    beta = {arch[c]: b for c, b in tab.groupby("config")["beta"].first().items()}

    rows = []
    for held in [None] + sorted(df.config.unique()):
        train = df if held is None else df[df.config != held]
        r = kurzak.fit(train, fixed=GEN3_FIXED, beta_fixed=beta)
        rows.append(dict(held_out_config=held or "ALL", n_train_conditions=train.groupby("g").ngroups,
                         c=r["c2"], k=r["kappa"]))
        print(f"{held or 'ALL':28s} n={rows[-1]['n_train_conditions']:2d}  c={r['c2']:.4f}  k={r['kappa']:.4f}")
    out = BASE / "data/fold_constants57.csv"
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
