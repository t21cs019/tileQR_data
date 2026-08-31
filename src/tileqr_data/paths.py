"""
リポジトリ内のパス定義。

データと図が同一リポジトリにあるため、環境変数による場所解決も
submodule も不要。すべてリポジトリルートからの相対パスで解決する。
"""

from __future__ import annotations

from pathlib import Path

# src/tileqr_data/paths.py → リポジトリルートは2つ上
ROOT = Path(__file__).resolve().parents[2]

RAW_DATA = ROOT / "raw_data"   # 計測機から回収したままの原本。触らない
RAW = ROOT / "raw"
RAW_SWEEP = RAW / "qr_sweep"
RAW_KERNEL = RAW / "kernel_dtsmqr"
RAW_SSRFB = RAW / "ssrfb"

DERIVED = ROOT / "derived"
OUT = ROOT / "out"

MACHINES_YAML = ROOT / "machines.yaml"
PLAN_YAML = ROOT / "plan.yaml"

# raw_data → raw の取捨選択（除外・置換）。assemble.py が読む。
CURATION_YAML = ROOT / "curation.yaml"
# いま走らせている計測。COVERAGE.md の進捗表に出る。
RUNNING_YAML = ROOT / "running.yaml"

SWEEP_PARQUET = DERIVED / "qr_sweep.parquet"
KERNEL_PARQUET = DERIVED / "kernel_dtsmqr.parquet"
SSRFB_PARQUET = DERIVED / "ssrfb.parquet"
OPTIMA_CSV = DERIVED / "optima.csv"
COVERAGE_MD = ROOT / "COVERAGE.md"
JOINS_MD = RAW / "JOINS.md"
CURATION_MD = RAW / "CURATION.md"
# assemble.py が前回書き出したファイルの台帳。掃除の対象をこれで限る。
ASSEMBLED_TXT = RAW / "ASSEMBLED.txt"
