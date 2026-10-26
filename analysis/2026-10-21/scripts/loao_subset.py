"""
対象構成すべて (TILEQR_SUBSET で絞った後の全条件) で leave-one-arch-out をやり直す。

現行 c=2.564, k=1.352 は中間40条件 (10構成) だけでフィットしている。絞り込み後に
新機種 (E3-1220v3, i3-8100, i5-9600) と size 16384 を加えた全条件を使い、
  gen3 : c, k をフィット
  ii   : c = √7.5 固定, k だけフィット
を構成単位の LOAO で評価する。フィットは kurzak.fit (β は task_a と同じ値で固定)。
aoba-b のように 1 arch = 1 構成なので、arch を抜く = 構成を丸ごと抜く。

出力: data/loao_subset.csv, data/loao_subset_folds.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import GEN3_FIXED, OUT, kurzak, load_curves, predict_nb, eta_x

DATA = OUT / "data"


def main():
    tab = pd.read_csv(DATA / "task_a_table.csv")
    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)]
    keys = set(zip(tab.config, tab["size"]))
    df = df[[g in keys for g in df.g]].reset_index(drop=True)
    obs = kurzak.observed(df)
    arch_of = df.groupby("config")["arch"].first().to_dict()
    beta_cfg = tab.groupby("config")["beta"].first().to_dict()
    beta_arch = {arch_of[c]: b for c, b in beta_cfg.items()}

    models = {
        "gen3": dict(GEN3_FIXED),
        "ii": dict(GEN3_FIXED, c2=np.sqrt(7.5)),
    }
    rows, folds = [], []
    for name, fixed in models.items():
        r_all = kurzak.fit(df, fixed=fixed, beta_fixed=beta_arch)
        folds.append(dict(model=name, held_out="ALL", c=r_all["c2"], k=r_all["kappa"]))
        for cfg in sorted(beta_cfg):
            r = kurzak.fit(df[df.config != cfg], fixed=fixed, beta_fixed=beta_arch)
            c, k = r["c2"], r["kappa"]
            folds.append(dict(model=name, held_out=cfg, c=c, k=k))
            for t in tab[tab.config == cfg].itertuples():
                o = obs[(cfg, t.size)]
                i, _ = predict_nb(o["nb"], t.beta, eta_x(o["nb"], t.size, t.p, c, k))
                rows.append(dict(model=name, config=cfg, label=t.label, p=t.p, size=t.size,
                                 nb_opt=o["nb_opt"], nb_pred=o["nb"][i],
                                 perf=o["G"][i] / o["peak"]))
    res = pd.DataFrame(rows)
    res.to_csv(DATA / "loao_subset.csv", index=False, float_format="%.4g")
    fo = pd.DataFrame(folds)
    fo.to_csv(DATA / "loao_subset_folds.csv", index=False, float_format="%.4g")
    print(fo.to_string(index=False))
    print(res.groupby("model").perf.agg(n="size", mean="mean", min="min",
                                         n95=lambda s: int((s >= 0.95).sum())))


if __name__ == "__main__":
    main()
