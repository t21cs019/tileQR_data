"""
共通層：不老・弐の本番スイープ（size 1024〜8192、p = 192）の読み込みと、当てはめなしのモデル。

- スイープの読み込み・base（速い水準）は analysis/2026-11-10_flow2-sweep-check/scripts/common.py をそのまま使う
  （load_all, add_baseline, SLOW_MS, NB_CLASS, flops_dgeqrf）
- A・β は analysis/2026-11-11_flow2-dtsmqr-1core/data/b_fits.csv の flow2・mean5 の値（ib=nb/8 と MaxIB の2通り）
- モデル：G = p·A·nb/(nb+β)·η理論、η理論 = 1/(1 + (c·√p·nb/size)^k)、c = √7.5、k = 2
  （analysis/2026-11-11_flow2-dtsmqr-1core/scripts/c_qr.py と同じ式）
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]                       # tileQR_data
DATA = OUT / "data"
DATA.mkdir(exist_ok=True)

P, C_TH, K_TH = 192, np.sqrt(7.5), 2.0
BAND = 0.95

_spec = importlib.util.spec_from_file_location(
    "sweep_common", ROOT / "analysis/2026-11-10_flow2-sweep-check/scripts/common.py")
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)

# 遅い水準の遅れ ΔT [ms]：2026-11-10_flow2-sweep-check/report.md の C2 の表から写した値（計算し直していない）。
# 8192 は表で括弧つき（判定できない）の 17 ms
DT_REPORT = {1024: 15.3, 2048: 12.7, 4096: 13.0, 8192: 17.0}


def kernel_params() -> dict:
    F = pd.read_csv(ROOT / "analysis/2026-11-11_flow2-dtsmqr-1core/data/b_fits.csv")
    F = F[F.machine.str.startswith("flow2") & (F.target == "mean5")].set_index("proc")
    return {k: (float(F.loc[k, "A"]), float(F.loc[k, "beta"])) for k in ["ib=nb/8", "MaxIB"]}


def predict(size, nb, A, beta):
    size, nb = np.asarray(size, float), np.asarray(nb, float)
    eta = 1 / (1 + (C_TH * np.sqrt(P) * nb / size) ** K_TH)
    return P * A * nb / (nb + beta) * eta


def band(nb, g):
    """最大と、最大から 5% 以内で連続する nb の範囲（c_qr.py と同じ）。"""
    i = int(np.nanargmax(g))
    ok = g >= BAND * g[i]
    lo = hi = i
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < len(g) - 1 and ok[hi + 1]:
        hi += 1
    return int(nb[i]), int(nb[lo]), int(nb[hi])


def setup_plot():
    return sw.setup_plot()
