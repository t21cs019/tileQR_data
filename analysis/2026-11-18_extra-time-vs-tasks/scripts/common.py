"""共通層。2026-11-10 の common10.load_s1（当てはめなしのモデル r0=1・E_並列 理論値 c=√7.5,k=2・機種ごとの A_k,β_k）を読み、
余分な時間 = t_obs − t_model [s]、タスク数 = N³/3 + N²/2 を使う。元のコードは変えない。"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
AN = OUT.parent
sys.path.insert(0, str(AN / "2026-11-10_serial-task-cost" / "scripts"))
sys.path.insert(0, str(AN / "2026-10-27_gen4-kernel-term" / "scripts"))
from common10 import load_s1  # noqa: E402

MACHINES = {  # label in eta_eff.csv -> 表示名
    "EPYC7543": "EPYC 7543（p = 32）",
    "EPYC7702 s1": "EPYC 7702（p = 64、1ソケット）",
    "Xeon4214 s1": "Xeon Silver 4214（p = 12、1ソケット）",
}
FLOW2 = "不老・弐（p = 192）"
