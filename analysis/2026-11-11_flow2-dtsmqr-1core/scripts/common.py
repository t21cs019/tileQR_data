"""
共通層：不老・弐 DTSMQR 1コア計測（2026-11-11、size 4096、r1〜r5）と EPYC 7543（raw/ssrfb/epyc、size 4096、r1〜r5）の読み込みと、
β・A の当てはめ（analysis/2026-10-21/scripts/common.py の beta_from_ssrfb と同じ手続き）。

- ~/Download/flow/ は読むだけ
- CSV の行の順 = 実行の順（nb の昇順、その中で ib の昇順）。seq 列に 0 始まりの実行順を入れる
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]                       # tileQR_data
DATA = OUT / "data"
DATA.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))

from tileqr_data import kurzak  # noqa: E402

SRC = Path.home() / "Download/flow/ssrfb"
PREFIX = "flow2-t1_s1_smt-off_core1_ssrfb_size4096_nb32-512_th1"
REPS = [1, 2, 3, 4, 5]
MRE_MAX = 0.05


def load_flow2() -> pd.DataFrame:
    out = []
    for r in REPS:
        d = pd.read_csv(SRC / f"{PREFIX}_r{r}.csv")
        d["rep"], d["seq"] = r, np.arange(len(d))
        out.append(d)
    return pd.concat(out, ignore_index=True)


def load_epyc() -> pd.DataFrame:
    out = []
    for r in REPS:
        d = pd.read_csv(ROOT / f"raw/ssrfb/epyc/epyc_size4096_t1_nb32-512_20260714-051903_r{r}.csv")
        d["rep"], d["seq"] = r, np.arange(len(d))
        out.append(d)
    return pd.concat(out, ignore_index=True)


def load_clock() -> pd.DataFrame:
    out = []
    for r in REPS:
        c = pd.read_csv(SRC / f"{PREFIX}_r{r}_clock.txt", sep=r"\s+", header=None, names=["date", "time", "mhz"])
        c["rep"] = r
        out.append(c)
    return pd.concat(out, ignore_index=True)


def curve_slice(a: pd.DataFrame) -> pd.DataFrame:
    """ib = nb/8 の断面（nb ≥ 64）。a は列 nb, ib, GFlops。"""
    return kurzak.ib_rule_slice(a, rho=8.0)


def curve_maxib(a: pd.DataFrame, nb_min=64) -> pd.DataFrame:
    """nb ごとに ib について最大。断面と比べるため nb ≥ 64 に揃える。"""
    a = a[a.nb >= nb_min]
    return a.loc[a.groupby("nb")["GFlops"].idxmax(), ["nb", "ib", "GFlops"]].reset_index(drop=True)


def fit(curve: pd.DataFrame) -> dict:
    nb, y = curve["nb"].to_numpy(float), curve["GFlops"].to_numpy(float)
    A, beta = kurzak.fit_E(nb, y)
    rel = A * nb / (nb + beta) / y - 1
    return dict(A=float(A), beta=float(beta), mre=float(np.mean(np.abs(rel))), max_abs=float(np.abs(rel).max()),
                n=len(nb), rel=rel)


def mean_grid(d: pd.DataFrame) -> pd.DataFrame:
    return d.groupby(["nb", "ib"], as_index=False)["GFlops"].mean()


def setup_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 110
    return plt
