"""
2026-10-21 ゼミ用分析の共通層。

既存の tileqr_data.kurzak の関数 (load_qr_curves, observed, fit_E, ib_rule_slice, shape)
をそのまま使い、モデル式は書き直さない。
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]          # tileQR_data
BASE = Path(__file__).resolve().parents[1]          # analysis/2026-10-21

# 環境変数 TILEQR_SUBSET で対象構成を絞る。
#   all          … 全構成（report.md）
#   s1_smt-off   … HT 無効かつ 1 ソケット（report_s1_smt-off.md、出力は BASE/s1_smt-off/）
SUBSET = os.environ.get("TILEQR_SUBSET", "all")
OUT = BASE if SUBSET == "all" else BASE / SUBSET
(OUT / "data").mkdir(parents=True, exist_ok=True)


def keep_config(cfg: str) -> bool:
    if SUBSET == "all":
        return True
    if SUBSET == "s1_smt-off":
        return "_s1_" in cfg and cfg.endswith("smt-off")
    raise ValueError(SUBSET)
sys.path.insert(0, str(ROOT / "src"))

from tileqr_data import io, kurzak  # noqa: E402

C_FIT, K_FIT = 2.56418, 1.35174      # derived/fold_constants.csv の ALL 行
GEN3_FIXED = {"m": 0.5, "delta": 1.0, "ke": 0.0}

# scripts/fold_constants.py の CONFIGS (中間発表 40 条件) と同じ β。
BETA_FOLD = {
    "aoba-b": 186.3, "epyc-7543": 184.2, "xeon-silver-4214": 111.2,
    "broadwell-e-i7-6900k": 200.5, "zen4-ryzen5-7400f": 76.2,
    "coffeelake-i5-8500": 170.0, "cometlake-i3-10100": 159.6,
    "kabylake-i7-7700": 169.5, "kabylake-i5-7400": 160.5, "kabylake-i3-7100": 139.8,
}
CONFIGS40 = [
    "aoba-b_s1_smt-off", "epyc_s1_smt-off", "calc_s1_smt-off", "dogwood_s1_smt-off",
    "ryzen5-7400f_s1_smt-off", "i5-8500_s1_smt-off", "i3-10100_s1_smt-off",
    "i7-7700_s1_smt-off", "i5-7400_s1_smt-off", "i3-7100_s1_smt-off",
]
SIZES40 = (1024, 2048, 4096, 8192)

LABEL = {
    "aoba-b_s1_smt-off": "EPYC7702 s1", "aoba-b_s2_smt-off": "EPYC7702 s2",
    "epyc_s1_smt-off": "EPYC7543", "calc_s1_smt-off": "Xeon4214 s1",
    "calc_s2_smt-off": "Xeon4214 s2", "dogwood_s1_smt-off": "i7-6900K",
    "ryzen5-7400f_s1_smt-off": "R5-7400F", "ryzen5-7400f_s1_smt-on": "R5-7400F HT",
    "ryzen7-5800x_s1_smt-on": "R7-5800X HT", "i5-8500_s1_smt-off": "i5-8500",
    "i3-10100_s1_smt-off": "i3-10100", "i3-10100_s1_smt-on": "i3-10100 HT",
    "i7-7700_s1_smt-off": "i7-7700", "i7-7700_s1_smt-on": "i7-7700 HT",
    "i5-7400_s1_smt-off": "i5-7400", "i3-7100_s1_smt-off": "i3-7100",
    "i3-7100_s1_smt-on": "i3-7100 HT", "xeon-e3-1220v3_s1_smt-off": "E3-1220v3",
    "i3-8100_s1_smt-off": "i3-8100", "i5-9600_s1_smt-off": "i5-9600",
}


def beta_from_ssrfb(mre_max=0.05):
    """
    指示書 model-crossval-2026-09-06 3.1 の手続き:
    (node,size) ごとに ib=nb/8 断面 → fit_E → MRE>5% の曲線を除外 → arch 平均。
    戻り値: (arch 表, 曲線ごとの表)
    """
    machines = io.load_machines()
    s = io.load_ssrfb()
    rows = []
    for (node, size), g in s.groupby(["node", "size"]):
        a = g.groupby(["nb", "ib"], as_index=False)["GFlops"].mean()
        sl = kurzak.ib_rule_slice(a, rho=8.0)
        nb, y = sl["nb"].to_numpy(float), sl["GFlops"].to_numpy(float)
        A, beta = kurzak.fit_E(nb, y)
        mre = float(np.mean(np.abs(A * nb / (nb + beta) / y - 1)))
        rows.append(dict(node=node, size=size, arch=machines["nodes"][node]["arch"],
                         beta=beta, A=A, mre=mre, n=len(sl), nb_max=nb.max(),
                         used=mre <= mre_max))
    curves = pd.DataFrame(rows)
    arch = (curves[curves.used].groupby("arch")
            .agg(beta=("beta", "mean"), n_curves=("beta", "size"),
                 nodes=("node", lambda x: ",".join(sorted(set(x))))).reset_index())
    return arch, curves


def load_curves():
    """全構成・全サイズの nb–性能曲線 (除外なし。fold_constants.py と同じ)。"""
    return kurzak.load_qr_curves(exclude_config=(), exclude_points=())


def theta_gen3(c=C_FIT, k=K_FIT):
    return (c, 0.5, 1.0, k, 0.0)


# ---- 並列効率の別定式 (タスクC) ----------------------------------------

def D_formula(N):
    return 30.0 * N - 34.0


def W_formula(N):
    return 4.0 * N**3


def eta_brent(nb, size, p):
    """(iii) η = 1/(1 + p·D/W), N = size/nb (連続値)。"""
    N = size / nb
    return 1.0 / (1.0 + p * D_formula(N) / W_formula(N))


def eta_min(nb, size, p):
    """(iv) η = min(1, W/(p·D))。"""
    N = size / nb
    return np.minimum(1.0, W_formula(N) / (p * D_formula(N)))


def eta_x(nb, size, p, c, k):
    x = c * np.sqrt(p) * nb / size
    return 1.0 / (1.0 + x**k)


def predict_nb(nb, beta, eta):
    """argmax_nb E(nb)·η(nb)。nb は実測格子。"""
    f = nb / (nb + beta) * eta
    return int(np.argmax(f)), f
