"""
E と η のどちらが崩れているかの切り分け。

(1) 片方だけ自由にしたフィット（1 構成ずつ、サイズごと）
    E 側: η = 理論値 (c=√7.5, k=2) に固定し、β だけを (構成, size) ごとにフィット
    η 側: E = 単体 DTSMQR の β に固定し、c だけ (k=2) / c と k を (構成, size) ごとにフィット
    E 側の項が正しく選ばれていれば、その自由パラメータは size に依らない値になるはず。
(2) 同じ自由度を構成ごと（全サイズ共通の1値）に与えたときの曲線 RMS と性能比。
残差は kurzak.fit と同じ「群ごとに最大で正規化、振幅は解析的に消去」。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from common27 import C_TH, DATA, K_TH, TAB, load57, summ


def eta(nb, size, p, c, k):
    return 1.0 / (1.0 + (c * np.sqrt(p) * nb / size) ** k)


def resid_groups(groups, f_of):
    """groups: [(nb, yn, size, p, beta)], f_of(i, g) -> 形。振幅は群ごとに解析消去。"""
    out = []
    for i, g in enumerate(groups):
        nb, yn = g[0], g[1]
        f = f_of(i, g)
        a = (yn @ f) / max(f @ f, 1e-300)
        out.append((yn - a * f) / np.sqrt(len(nb)))
    return np.concatenate(out)


def fit(groups, f_of, z0, lo, hi):
    r = least_squares(lambda z: resid_groups(groups, lambda i, g: f_of(z, i, g)), z0,
                      bounds=(lo, hi), xtol=1e-12, ftol=1e-12)
    return r.x, float(np.sqrt(np.sum(r.fun**2) / len(groups)))


def argmax_perf(o, f):
    i = int(np.argmax(f))
    return o["nb"][i], o["G"][i] / o["peak"]


VARIANTS = {
    # name: (f(z, nb, size, p, beta), z0, lo, hi)
    "β自由(η理論)": (lambda z, nb, s, p, b: nb / (nb + z[0]) * eta(nb, s, p, C_TH, K_TH),
                    [150.0], [1.0], [5000.0]),
    "c自由(E固定,k=2)": (lambda z, nb, s, p, b: nb / (nb + b) * eta(nb, s, p, z[0], K_TH),
                       [2.7], [0.05], [50.0]),
    "c,k自由(E固定)": (lambda z, nb, s, p, b: nb / (nb + b) * eta(nb, s, p, z[0], z[1]),
                      [2.7, 2.0], [0.05, 0.3], [50.0, 20.0]),
    "β,c自由(k=2)": (lambda z, nb, s, p, b: nb / (nb + z[0]) * eta(nb, s, p, z[1], K_TH),
                    [150.0, 2.7], [1.0, 0.05], [5000.0, 50.0]),
}


def main():
    df, obs = load57()
    rows_sz, rows_cfg = [], []
    for cfg, tc in TAB.groupby("config"):
        groups, keys = [], []
        for t in tc.itertuples():
            o = obs[(cfg, t.size)]
            groups.append((o["nb"], o["G"] / o["peak"], float(t.size), float(t.p), t.beta))
            keys.append(t)
        for name, (f, z0, lo, hi) in VARIANTS.items():
            fo = lambda z, i, g, f=f: f(z, g[0], g[2], g[3], g[4])
            # (a) サイズごと
            for g, t in zip(groups, keys):
                z, rms = fit([g], fo, z0, lo, hi)
                nbp, perf = argmax_perf(obs[(cfg, t.size)], fo(z, 0, g))
                rows_sz.append(dict(variant=name, config=cfg, label=t.label, p=t.p, size=t.size,
                                    beta_k=t.beta, z0=z[0], z1=z[1] if len(z) > 1 else np.nan,
                                    rms=rms, nb_opt=t.nb_opt, nb_pred=nbp, perf=perf))
            # (b) 構成ごと（全サイズ共通）
            z, rms = fit(groups, fo, z0, lo, hi)
            for i, (g, t) in enumerate(zip(groups, keys)):
                nbp, perf = argmax_perf(obs[(cfg, t.size)], fo(z, i, g))
                rows_cfg.append(dict(variant=name, config=cfg, label=t.label, p=t.p, size=t.size,
                                     beta_k=t.beta, z0=z[0], z1=z[1] if len(z) > 1 else np.nan,
                                     rms_cfg=rms, nb_opt=t.nb_opt, nb_pred=nbp, perf=perf, WpD=t.WpD))
    sz, cf = pd.DataFrame(rows_sz), pd.DataFrame(rows_cfg)
    sz.to_csv(DATA / "decompose_per_size.csv", index=False, float_format="%.4g")
    cf.to_csv(DATA / "decompose_per_config.csv", index=False, float_format="%.4g")
    pd.set_option("display.width", 250)
    # サイズに対するドリフト: log(param) を log(size) に回帰した傾き（構成ごと）
    def slope(d, col):
        return np.polyfit(np.log2(d["size"]), np.log2(d[col]), 1)[0]
    dr = []
    for (v, cfg), d in sz.groupby(["variant", "config"]):
        dr.append(dict(variant=v, label=d.label.iloc[0], p=d.p.iloc[0],
                       slope0=slope(d, "z0"), cv0=d.z0.std() / d.z0.mean(),
                       vals=" ".join(f"{x:.3g}" for x in d.sort_values("size").z0)))
    dr = pd.DataFrame(dr).sort_values(["variant", "p"], ascending=[True, False])
    dr.to_csv(DATA / "decompose_drift.csv", index=False, float_format="%.3f")
    print(dr.to_string(index=False))
    print()
    s = []
    for v, d in cf.groupby("variant"):
        for sc, m in {"全57": d.p > 0, "p≥24": d.p >= 24, "p≤12": d.p <= 12}.items():
            s.append(dict(variant=v, scope=sc, rms=d[m].drop_duplicates("config").rms_cfg.mean(),
                          **summ(d[m].perf)))
    print(pd.DataFrame(s).to_string(index=False, float_format="%.3f"))
    print(cf[cf.variant == "β自由(η理論)"].drop_duplicates("config")[["label", "p", "beta_k", "z0", "rms_cfg"]]
          .assign(ratio=lambda d: d.z0 / d.beta_k).sort_values("p").to_string(index=False, float_format="%.3g"))


if __name__ == "__main__":
    main()
