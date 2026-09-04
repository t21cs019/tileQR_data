"""
Kurzak (2008) の性能モデルと本研究のモデルを、同じデータの上で比較するための層。

**なぜここに置くか。** 「Kurzak の指数と本研究の指数のどちらが実測に合うか」は
図2枚（fig_kurzak_p_exponent / fig_kurzak_size_exponent）の共通の土台になる。
図ごとにフィットを書き直すと、片方だけ直したときに指数が食い違う。

**最適 nb の定義はここに書かない。** それは scripts/ingest.py の責務。
本モジュールの observed() は ingest.py の idxmax / band_range と同じ手続きを、
ノードで割らず構成ごとに平均した曲線に適用するだけで、判定規則は変えていない。

---

## モデル

本研究:

    QR(nb; size) = A * E(nb) * eta_C
    E(nb)   = nb / (nb + beta)
    eta_C   = 1 / (1 + x**k)
    x       = c2 * p**m * nb / (S0 * (size/S0)**delta)
    k       = k0 * (size/S0)**ke                     （ke は実質 0 なので既定で 0）

分母を展開すると 1 + (定数) * p**mu * nb**kappa * size**(-sigma) となり、

    kappa = k0         nb の指数
    mu    = m * k0     コア数 P の指数
    sigma = delta * k0 size の指数

Kurzak の並列項 1 + a/x + b*P/y + c*P*(x/y)**2.5 は
kappa = sigma = 2.5、mu = 1.0 に対応する。両者は同じ関数形で、
**違うのは指数の3つ組 (kappa, mu, sigma) だけ**。この形にしておくと
「Kurzak の指数に固定した場合」を制約付きフィットとして書ける。

## beta は構成ではなく **アーキテクチャ** ごとに持つ

aoba-b_s1（64コア）と aoba-b_s2（128コア）は同じ EPYC 7702 なので beta は同一。
ここを構成ごとに分けると、データ中で唯一の「同一CPU・コア数だけ違う」対比が
beta に吸われて P の指数が同定できなくなる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from . import io

S0 = 4096.0

# 既知の汚染データ。notes/performance_model.md「データ品質の注意」と対応する。
#   i3-7100        … 計測エラー
#   epyc 1024/2048 … タスクオーバーヘッド支配で GFlops が異常に低い
#   i5-8500 8192   … サーマルスロットリング
EXCLUDE_CONFIG = ("i3-7100",)
EXCLUDE_POINTS = (
    ("epyc_s1_smt-off", 1024),
    ("epyc_s1_smt-off", 2048),
    ("i5-8500_s1_smt-off", 8192),
)

# SSRFB 実測から得た beta。fig_kurzak_* と notes/kurzak_verification.md と同じ値。
# i5-7400 はマルチスレッド条件混入のため入れない。
BETA_MEASURED = {
    "epyc-7543": 342.7,
    "coffeelake-i5-8500": 152.6,
    "zen4-ryzen5-7400f": 77.4,
}


# --- データ --------------------------------------------------------------

def physical_cores(config: str, machines: dict) -> float:
    cfg = machines["configs"][config]
    arch = machines["architectures"][cfg["arch"]]
    return arch["physical_cores_total"] * cfg["sockets_used"] / arch["sockets_physical"]


def load_qr_curves(exclude_config=EXCLUDE_CONFIG, exclude_points=EXCLUDE_POINTS):
    """
    (config, size) ごとの nb-性能曲線を返す。

    手続きは scripts/ingest.py と同じ順序:
      1. 同一 (条件, nb, ib) の反復を平均する（最大ではなく平均）
      2. 各 nb で ib を最適化する
    そのうえで、AOBA のようにノードが複数ある構成はノード間で平均する。
    ノードで割ると同じ条件が5本に散り、構成ごとの beta が推定できないため。
    """
    machines = io.load_machines()
    df = io.load_sweeps()
    keys = ["config", "node", "threads", "size", "nb", "ib"]
    a = df.groupby(keys, as_index=False)["GFlops"].mean()
    per_nb = a.loc[a.groupby(keys[:-1], observed=True)["GFlops"].idxmax()]
    c = per_nb.groupby(["config", "threads", "size", "nb"], as_index=False)["GFlops"].mean()

    if exclude_config:
        c = c[~c["config"].str.startswith(tuple(f"{e}_" for e in exclude_config))]
    for cfg, size in exclude_points or ():
        c = c[~((c["config"] == cfg) & (c["size"] == size))]

    c = c.reset_index(drop=True)
    c["p"] = c["config"].map(lambda x: physical_cores(x, machines))
    c["arch"] = c["config"].map(lambda x: machines["configs"][x]["arch"])
    c["g"] = list(zip(c["config"], c["size"]))
    c["gmax"] = c.groupby("g")["GFlops"].transform("max")
    return c


# --- モデル --------------------------------------------------------------

def shape(theta, nb, size, p, beta):
    """A を除いた QR(nb) の形。theta = (c2, m, delta, k0, ke)。"""
    c2, m, delta, k0, ke = theta
    u = size / S0
    return (nb / (nb + beta)) / (1.0 + (c2 * p**m * nb / (S0 * u**delta)) ** (k0 * u**ke))


_DEFAULT = dict(c2=3.40, m=0.240, delta=0.715, k0=2.41, ke=0.0)
_BOUNDS = dict(c2=(0.05, 60.0), m=(-1.0, 3.0), delta=(-1.0, 3.0), k0=(0.2, 25.0))
_ORDER = ["c2", "m", "delta", "k0"]


def fit(df, fixed=None, mu_fixed=None, beta_fixed=None, beta_hi=500.0):
    """
    全点同時フィット。

    残差は「群ごとに最大値で正規化した GFlops」の線形最小二乗で、
    振幅 A は群ごとに解析的に消去する（A は nb の argmax に効かないので、
    自由パラメータとして持つ意味がない）。群 = (config, size)。
    群ごとの点数が違うので、1点あたりでなく1群あたりで重みを揃える。

    fixed      … {"delta": 1.0} のように指数を固定する
    mu_fixed   … P の指数 mu = m*k0 を固定する（Kurzak は 1.0）
    beta_fixed … {arch: beta}。SSRFB 実測 beta を入れて確かめる用
    beta_hi    … 自由 beta の上限。実測 beta が 77〜343 なので、
                 それを大きく超えて発散するのは物理でなくフィットの逃げ場。
    """
    fixed = dict(fixed or {})
    beta_fixed = dict(beta_fixed or {})
    archs = sorted(df["arch"].unique())
    free_archs = [a for a in archs if a not in beta_fixed]
    ai = {a: i for i, a in enumerate(free_archs)}
    nb_ = df["nb"].to_numpy(float)
    size_ = df["size"].to_numpy(float)
    p_ = df["p"].to_numpy(float)
    yn = (df["GFlops"] / df["gmax"]).to_numpy(float)
    gidx = pd.factorize(df["g"])[0]
    aix = np.array([ai.get(a, -1) for a in df["arch"]])
    bfix = np.array([beta_fixed.get(a, np.nan) for a in df["arch"]])
    w = 1.0 / np.sqrt(np.bincount(gidx)[gidx])
    w = w / np.sqrt(np.mean(w**2))
    free = [n for n in _ORDER if n not in fixed]
    n_beta = len(free_archs)

    def unpack(z):
        pr = dict(_DEFAULT)
        pr.update(fixed)
        for i, n in enumerate(free):
            pr[n] = z[i]
        if mu_fixed is not None:
            pr["m"] = mu_fixed / pr["k0"]
        lb = z[len(free):]
        if n_beta == 0:
            beta = bfix.copy()
        else:
            beta = np.where(aix >= 0, np.exp(lb[np.maximum(aix, 0)]), bfix)
        return (pr["c2"], pr["m"], pr["delta"], pr["k0"], pr["ke"]), beta, pr

    def resid(z):
        theta, beta, _ = unpack(z)
        f = shape(theta, nb_, size_, p_, beta)
        num = np.bincount(gidx, weights=yn * f * w**2)
        den = np.bincount(gidx, weights=f * f * w**2)
        amp = num / np.maximum(den, 1e-300)
        return (yn - amp[gidx] * f) * w

    z0 = np.array([_DEFAULT[n] for n in free] + [np.log(120.0)] * n_beta)
    lo = np.array([_BOUNDS[n][0] for n in free] + [np.log(1.0)] * n_beta)
    hi = np.array([_BOUNDS[n][1] for n in free] + [np.log(beta_hi)] * n_beta)
    r = least_squares(resid, z0, bounds=(lo, hi), max_nfev=200000,
                      xtol=1e-15, ftol=1e-15, gtol=1e-15)
    theta, _, pr = unpack(r.x)
    beta_by_arch = {}
    for a in archs:
        if a in ai:
            beta_by_arch[a] = float(np.exp(r.x[len(free) + ai[a]]))
        else:
            beta_by_arch[a] = float(beta_fixed[a])
    cfg2arch = df.groupby("config")["arch"].first().to_dict()
    beta_by_config = {c: beta_by_arch[a] for c, a in cfg2arch.items()}
    c2, m, delta, k0, ke = theta
    return dict(
        theta=theta,
        beta_by_arch=beta_by_arch,
        beta_by_config=beta_by_config,
        rms=float(np.sqrt(np.mean(r.fun**2))),
        kappa=float(k0),
        mu=float(m * k0),
        sigma=float(delta * k0),
        m=float(m),
        delta=float(delta),
        c2=float(c2),
    )


# --- 予測の評価 ----------------------------------------------------------

BAND = 0.95   # scripts/ingest.py と同じ
THR = 0.92    # notes/performance_model.md の推奨しきい値


def _contiguous(ok, i):
    lo = hi = i
    while lo - 1 >= 0 and ok[lo - 1]:
        lo -= 1
    while hi + 1 < len(ok) and ok[hi + 1]:
        hi += 1
    return lo, hi


def observed(df):
    """
    (config, size) ごとの実測ピークと 95% 帯。

    ピークと帯の取り方は scripts/ingest.py の idxmax / band_range と同じ。
    違うのは、ノードで割らず構成ごとに平均した曲線に適用する点だけ。
    """
    out = {}
    for g, sub in df.groupby("g"):
        s = sub.sort_values("nb").reset_index(drop=True)
        peak = float(s["GFlops"].max())
        i = int(s["GFlops"].idxmax())
        lo, hi = _contiguous((s["GFlops"] >= peak * BAND).to_numpy(), i)
        out[g] = dict(
            nb=s["nb"].to_numpy(float),
            G=s["GFlops"].to_numpy(float),
            nb_opt=float(s.loc[i, "nb"]),
            peak=peak,
            lo=float(s.loc[lo, "nb"]),
            hi=float(s.loc[hi, "nb"]),
        )
    return out


def evaluate(theta, beta_by_config, obs, g, p):
    """ゼロショット予測1点の評価。"""
    t = obs[g]
    config, size = g
    f = shape(theta, t["nb"], np.full_like(t["nb"], float(size)),
              np.full_like(t["nb"], float(p)), beta_by_config[config])
    i = int(np.argmax(f))
    lo, hi = _contiguous(f >= THR * f[i], i)
    blo, bhi = t["nb"][lo], t["nb"][hi]
    in_band = (t["nb"] >= t["lo"]) & (t["nb"] <= t["hi"])
    return dict(
        nb_pred=float(t["nb"][i]),
        nb_opt=t["nb_opt"],
        perf=float(t["G"][i] / t["peak"]),
        nb_relerr=abs(t["nb"][i] - t["nb_opt"]) / t["nb_opt"],
        hit=float(t["lo"] <= t["nb"][i] <= t["hi"]),
        recall=float(((t["nb"] >= blo) & (t["nb"] <= bhi) & in_band).sum() / max(in_band.sum(), 1)),
        width=float((bhi - blo) / (t["nb"].max() - t["nb"].min())),
    )


def loocv(df, **fit_kw):
    """(config, size) を1点ずつ抜いて、残りで指数を引き直し、抜いた点を予測する。"""
    obs = observed(df)
    pmap = df.groupby("config")["p"].first().to_dict()
    rows = []
    for g in sorted(obs):
        r = fit(df[df["g"] != g], **fit_kw)
        e = evaluate(r["theta"], r["beta_by_config"], obs, g, pmap[g[0]])
        e.update(config=g[0], size=g[1])
        rows.append(e)
    return pd.DataFrame(rows)


# --- SSRFB カーネル側（タスク1・2） --------------------------------------

def kurzak_kernel(p, nb, ib):
    """Kurzak の DSSRFB モデル a / (1 + b*ib/nb + c/ib + d/nb)。"""
    a, b, c, d = p
    return a / (1.0 + b * ib / nb + c / ib + d / nb)


def beta_from_kurzak(p, rho=8.0):
    """ib = nb/rho を代入して E(nb)=nb/(nb+beta) に畳んだときの beta。"""
    _, b, c, d = p
    return (rho * c + d) / (1.0 + b / rho)


def fit_kernel(nb, ib, y):
    """相対残差での最小二乗。初期値を振って局所解を避ける。"""
    best = None
    for p0 in [(y.max(), 0.3, 10.0, 50.0), (y.max() * 1.5, 0.24, 3.77, 21.4),
               (y.max() * 3, 1.0, 20.0, 140.0)]:
        r = least_squares(lambda lp: kurzak_kernel(np.exp(lp), nb, ib) / y - 1.0,
                          np.log(p0), method="lm", max_nfev=40000)
        if best is None or r.cost < best.cost:
            best = r
    return np.exp(best.x)


def fit_E(nb, y):
    """E 形 A*nb/(nb+beta) を相対残差でフィットし (A, beta) を返す。"""
    best = None
    for p0 in [(y.max(), 50.0), (y.max() * 1.2, 150.0), (y.max() * 1.5, 300.0)]:
        r = least_squares(lambda lp: np.exp(lp[0]) * nb / (nb + np.exp(lp[1])) / y - 1.0,
                          np.log(p0), method="lm", max_nfev=40000)
        if best is None or r.cost < best.cost:
            best = r
    return np.exp(best.x)


def ib_rule_slice(g, rho=8.0, nb_min=64.0):
    """
    ib = nb/rho の断面。格子上に厳密な ib が無いので最も近い ib を採る。
    ib の下限が 8 なので nb < 64 は rho=8 の断面を作れない。既定で切る。
    """
    rows = []
    for nb, sub in g[g["nb"] >= nb_min].groupby("nb"):
        j = (sub["ib"] - nb / rho).abs().idxmin()
        rows.append((nb, sub.loc[j, "ib"], sub.loc[j, "GFlops"]))
    return pd.DataFrame(rows, columns=["nb", "ib", "GFlops"])
