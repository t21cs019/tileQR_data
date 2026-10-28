"""
「nb の項が分かっていれば η は理論値のままでよいか」の確認（構成ごとのインサンプル）。

  E_k·η_理論          : フィットなし (2026-10-21 の (i))
  E_k·M_cfg·η_理論     : M(nb) = 1/(1+(ν/nb)^q) を η_eff/η_理論 から構成ごとにフィット（residual.py）
  E_k·η(c,k 自由)      : 比較用。同じく構成ごとに η 側の 2 定数をフィット（decompose.py）
nb の項は size に依らない 1 本の曲線で、η は N だけの関数のまま。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common27 import C_TH, DATA, K_TH, TAB, load57, summ


def main():
    df, obs = load57()
    rf = pd.read_csv(DATA / "residual_fit.csv").set_index("label")
    dc = pd.read_csv(DATA / "decompose_per_config.csv")
    rows = []
    for t in TAB.itertuples():
        o = obs[(t.config, t.size)]
        nb = o["nb"]
        E = nb / (nb + t.beta)
        eta = 1 / (1 + (C_TH * np.sqrt(t.p) * nb / t.size) ** K_TH)
        r = rf.loc[t.label]
        M = 1 / (1 + (r.nu_q / nb) ** r.q)
        for name, f in {"E_k·η理論": E * eta, "E_k·M·η理論": E * M * eta}.items():
            i = int(np.argmax(f))
            rows.append(dict(model=name, label=t.label, p=t.p, size=t.size, nb_opt=t.nb_opt,
                             nb_pred=nb[i], perf=o["G"][i] / o["peak"]))
    d = dc[dc.variant == "c,k自由(E固定)"]
    for t in d.itertuples():
        rows.append(dict(model="E_k·η(c,k自由)", label=t.label, p=t.p, size=t.size, nb_opt=t.nb_opt,
                         nb_pred=t.nb_pred, perf=t.perf))
    res = pd.DataFrame(rows)
    res.to_csv(DATA / "oracle_predictions.csv", index=False, float_format="%.4g")
    out = []
    for m, d in res.groupby("model", sort=False):
        for sc, k in {"全57": d.p > 0, "p≥24": d.p >= 24, "p≤12": d.p <= 12}.items():
            out.append(dict(model=m, scope=sc, **summ(d[k].perf)))
    print(pd.DataFrame(out).to_string(index=False, float_format="%.1f"))
    pv = res[res.p >= 24].pivot_table(index=["label", "size", "nb_opt"], columns="model", values=["nb_pred", "perf"])
    print(pv.round(3).to_string())


if __name__ == "__main__":
    main()
