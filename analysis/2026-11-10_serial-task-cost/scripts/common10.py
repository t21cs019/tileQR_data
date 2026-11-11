"""
2026-11-10 分析の共通層。

  load_s1()  : HT 無効・1ソケットの13構成・57条件。../2026-10-27_gen4-kernel-term/data/eta_eff.csv をそのまま読む
               （G は各 nb の最高、A_k・β_k は1コアの DTSMQR、eta_th は c = √7.5, k = 2）
  load_all() : derived/qr_sweep.parquet の全構成（2ソケット、SMT 有効を含む）。G は (nb, ib) ごとの平均の、ib についての最高。
               A_k・β_k は同じ機械の1ソケット・SMT 無効の値を使い、p は使った物理コア数（1ソケットのコア数 × ソケット数）

どちらも次の列を足す。
  W = 4/3·size³、tasks = N³/3 + N²/2（N = size/nb）、D = 30N − 28
  G_model = p·A_k·E_k(nb)·η理論(nb)、t_obs = W/G、t_model = W/G_model [秒]
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
DATA = OUT / "data"
ROOT = OUT.parents[1]
ETA_EFF = OUT.parent / "2026-10-27_gen4-kernel-term" / "data" / "eta_eff.csv"
C_TH = np.sqrt(7.5)


def _derive(e):
    e["N"] = e["size"] / e.nb
    e["W"] = 4 / 3 * e["size"] ** 3
    e["tasks"] = e.N**3 / 3 + e.N**2 / 2
    e["D"] = 30 * e.N - 28
    e["eta_th"] = 1 / (1 + (C_TH * np.sqrt(e.p) * e.nb / e["size"]) ** 2)
    e["G_model"] = e.p * e.A_k * e.nb / (e.nb + e.beta_k) * e.eta_th
    e["t_obs"] = e.W / e.G / 1e9
    e["t_model"] = e.W / e.G_model / 1e9
    e["us_per_task"] = e.t_obs / e.tasks * 1e6
    e["excess_us_per_task"] = (e.t_obs - e.t_model) / e.tasks * 1e6
    return e


def load_s1():
    return _derive(pd.read_csv(ETA_EFF))


def load_all():
    k = pd.read_csv(ETA_EFF).groupby("config").agg(A_k=("A_k", "first"), beta_k=("beta_k", "first"),
                                                   p1=("p", "first"), label=("label", "first")).reset_index()
    k["machine"] = k.config.str.replace("_s1_smt-off", "")
    d = pd.read_parquet(ROOT / "derived" / "qr_sweep.parquet")
    c = (d.groupby(["config", "size", "nb", "ib"]).GFlops.mean().reset_index()
         .groupby(["config", "size", "nb"]).GFlops.max().reset_index().rename(columns={"GFlops": "G"}))
    c = c[(c.nb >= 32) & (c.nb <= 512)]
    c["machine"] = c.config.str.replace(r"_s\d_smt-o\w+", "", regex=True)
    c["sockets"] = c.config.str.extract(r"_s(\d)_")[0].astype(int)
    c["smt"] = c.config.str.contains("smt-on")
    c = c.merge(k[["machine", "A_k", "beta_k", "p1", "label"]], on="machine")
    c["p"] = c.p1 * c.sockets
    c["threads"] = c.p * np.where(c.smt, 2, 1)
    return _derive(c)


def perf_at_argmin(g, t_pred):
    """size ごとに、予測時間が最小の nb での実測性能 ÷ 実測の最高。"""
    out = []
    for size, gs in g.assign(t_pred=t_pred).groupby("size"):
        gs = gs.set_index("nb")
        nb = gs.t_pred.idxmin()
        out.append(dict(size=size, nb_opt=gs.G.idxmax(), nb_pred=nb, perf=gs.G[nb] / gs.G.max()))
    return out


def summ(perf):
    perf = np.asarray(perf)
    return f"平均 {100 * perf.mean():.1f} 最低 {100 * perf.min():.1f} 95%以上 {(perf >= 0.95).sum()}/{len(perf)}"
