"""
第4世代（改善C）を 57 条件で評価する。

  g4_vault : vault の定数 (c2=3.40, m=0.240, δ=0.715, k0=2.41)、ゼロショット
  g4_bench : tileQR_bench/tuning/model_predict.py の定数 (3.43, 0.19, 0.836, 2.3)
  g3_theory: c=√7.5, k=2 (m=0.5, δ=1)
  g3 / g3+m / g3+δ / g4 : 57 条件で再フィット（β 固定）。全点 fit と構成単位 LOAO
β・p・nb 格子は 2026-10-21 と同じ。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common27 import C_TH, DATA, K_TH, TAB, beta_arch, kurzak, load57, summ

FAMILIES = {
    "g3": dict(m=0.5, delta=1.0, ke=0.0),
    "g3+m": dict(delta=1.0, ke=0.0),
    "g3+δ": dict(m=0.5, ke=0.0),
    "g4": dict(ke=0.0),
}
FIXED_THETA = {
    "g4_vault": (3.40, 0.240, 0.715, 2.41, 0.0),
    "g4_bench": (3.43, 0.19, 0.836, 2.3, 0.0),
    "g3_theory": (C_TH, 0.5, 1.0, K_TH, 0.0),
    "g3_fit40": (2.56418, 0.5, 1.0, 1.35174, 0.0),
}


def predict(theta, o, size, p, beta):
    f = kurzak.shape(theta, o["nb"], size, p, beta)
    i = int(np.argmax(f))
    return o["nb"][i], o["G"][i] / o["peak"]


def main():
    df, obs = load57()
    ba = beta_arch()
    rows, consts = [], []
    thetas = {k: {cfg: v for cfg in TAB.config.unique()} for k, v in FIXED_THETA.items()}
    for name, fixed in FAMILIES.items():
        r = kurzak.fit(df, fixed=fixed, beta_fixed=ba)
        consts.append(dict(model=name + "_full", fold="ALL", c2=r["c2"], m=r["m"], delta=r["delta"],
                           k0=r["kappa"], rms=r["rms"]))
        thetas[name + "_full"] = {cfg: r["theta"] for cfg in TAB.config.unique()}
        thetas[name + "_loao"] = {}
        for cfg in TAB.config.unique():
            rr = kurzak.fit(df[df.config != cfg], fixed=fixed, beta_fixed=ba)
            thetas[name + "_loao"][cfg] = rr["theta"]
            consts.append(dict(model=name + "_loao", fold=cfg, c2=rr["c2"], m=rr["m"], delta=rr["delta"],
                               k0=rr["kappa"], rms=rr["rms"]))
    for model, th in thetas.items():
        for t in TAB.itertuples():
            nbp, perf = predict(th[t.config], obs[(t.config, t.size)], t.size, t.p, t.beta)
            rows.append(dict(model=model, config=t.config, label=t.label, p=t.p, size=t.size,
                             WpD=t.WpD, nb_opt=t.nb_opt,
                             nb_pred=nbp, perf=perf))
    res = pd.DataFrame(rows)
    res.to_csv(DATA / "gen4_predictions.csv", index=False, float_format="%.4g")
    pd.DataFrame(consts).to_csv(DATA / "gen4_constants.csv", index=False, float_format="%.4g")
    print(pd.DataFrame(consts).query("fold=='ALL'").to_string(index=False))
    scopes = {"全57": res.p > 0, "p≥24": res.p >= 24, "p≤12": res.p <= 12,
              "W/(pD)<1.5": res.WpD < 1.5, "W/(pD)≥1.5": res.WpD >= 1.5}
    out = []
    for model, d in res.groupby("model", sort=False):
        for sc, m in scopes.items():
            out.append(dict(model=model, scope=sc, **summ(d.loc[m[d.index], "perf"])))
    out = pd.DataFrame(out)
    out.to_csv(DATA / "gen4_summary.csv", index=False, float_format="%.1f")
    print(out.pivot(index="model", columns="scope", values="mean").round(1).to_string())
    print(out.pivot(index="model", columns="scope", values="min").round(1).to_string())
    print(out.pivot(index="model", columns="scope", values="n95").to_string())


if __name__ == "__main__":
    main()
