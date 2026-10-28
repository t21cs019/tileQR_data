"""
2026-10-27 分析の共通層。2026-10-21 の common.py（TILEQR_SUBSET=s1_smt-off）をそのまま使う。
対象は HT 無効・1ソケットの13構成・57条件。条件表（β・p・実測最適 nb・W/(pD)）は、
EPYC 7543 size1024/2048 を再計測に差し替えた版（analysis/2026-10-27_epyc-remeasure）を使う。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["TILEQR_SUBSET"] = "s1_smt-off"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "2026-10-21" / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import common as c21  # noqa: E402
from common import kurzak, load_curves  # noqa: E402

OUT = HERE.parent
DATA = OUT / "data"
TAB = pd.read_csv(HERE.parents[1] / "2026-10-27_epyc-remeasure" / "s1_smt-off" / "data" / "task_a_table.csv")
C_TH, K_TH = np.sqrt(7.5), 2.0


def load57():
    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)]
    keys = set(zip(TAB.config, TAB["size"]))
    df = df[[g in keys for g in df.g]].reset_index(drop=True)
    return df, kurzak.observed(df)


def beta_arch():
    df = load_curves()
    arch_of = df.groupby("config")["arch"].first().to_dict()
    return {arch_of[c]: b for c, b in TAB.groupby("config")["beta"].first().items()}


def summ(perf):
    perf = np.asarray(perf)
    return dict(n=len(perf), mean=100 * perf.mean(), min=100 * perf.min(), n95=int((perf >= 0.95).sum()))


def jp_font():
    import matplotlib
    from tileqr_data.style import _find_jp_font
    matplotlib.rcParams["font.family"] = [_find_jp_font() or "sans-serif"]
    matplotlib.rcParams["axes.unicode_minus"] = False
