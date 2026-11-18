"""
共通層：2026-11-17_flow2-perf-ratio-3agg の集計済みの表を読むだけ（集計し直さない）。

- 曲線：../2026-11-17_flow2-perf-ratio-3agg/data/a_curves.csv（size, nb ごとに ib について最大を取った GFlops。
  列 fast = 速い水準、slow = 遅い水準だけ、mean = 5回の平均）
- 性能比（理論値の c, k）：同 data/b_summary.csv の kernel = ib=nb/8 の行
- 図のスタイルは 11-11 の p.9 右の図（analysis/2026-11-11_flow2-curves/scripts/ratio.py）に合わせる
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]                                   # tileQR_data
SRC = ROOT / "analysis/2026-11-17_flow2-perf-ratio-3agg"
DATA = OUT / "data"
DATA.mkdir(exist_ok=True)

P = 192
SIZES = [1024, 2048, 4096, 8192]
AGGS = {"fast": "速い水準", "slow": "遅い水準だけ", "mean": "5回の平均"}
AGG_COLORS = {"fast": "#1f77b4", "slow": "#d62728", "mean": "#2ca02c"}   # 3agg の fig_b_ratio.png と同じ
SIZE_COLORS = {1024: "#2a78d6", 2048: "#1baf7a", 4096: "#eda100", 8192: "#e87ba4"}  # p.9 の図（ratio.py）と同じ
BG = "#fcfcfb"


def curves() -> pd.DataFrame:
    return pd.read_csv(SRC / "data/a_curves.csv")


def summary() -> pd.DataFrame:
    S = pd.read_csv(SRC / "data/b_summary.csv")
    return S[S.kernel == "ib=nb/8"]


def setup_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 110
    return plt
