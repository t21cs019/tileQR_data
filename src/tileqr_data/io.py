"""
データの読み込み層。

原則: 「最適 nb の定義」はここに書かない。それは scripts/ingest.py の責務で、
結果は derived/optima.csv に落ちる。図もダッシュボードもそれを読むだけにする。
定義が複数箇所にあると、片方だけ直したときに数値が食い違うため。
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml

from . import paths

# {node}_size{N}_t{threads}_nb{lo}-{hi}_{YYYYMMDD-HHMMSS}[_r{k}].csv
#
# 末尾の _r{k} はトライアル番号。1ファイル1トライアルにするとき、
# 同一ファイルから切り出した周はタイムスタンプが同じになるため、
# これが無いと名前が衝突する。1周しか無いファイルには付けない。
FILENAME_RE = re.compile(
    r"^(?P<node>[A-Za-z0-9\-]+)"
    r"_size(?P<size>\d+)"
    r"_t(?P<threads>\d+)"
    r"_nb(?P<nb_lo>\d+)-(?P<nb_hi>\d+)"
    r"_(?P<stamp>[0-9]{8}-[0-9]{6}|nodate)"
    r"(?:_r(?P<rep>\d+))?\.csv$"
)

SCHEMA = ["threads", "size", "nb", "ib", "GFlops"]

# ssrfb は Time_sec 列を持つ。列構成が違うので qr_sweep とは別に読む。
SSRFB_SCHEMA = ["threads", "size", "nb", "ib", "Time_sec", "GFlops"]


def parse_filename(name: str) -> dict | None:
    """規約に沿ったファイル名なら辞書を返す。沿わなければ None。"""
    m = FILENAME_RE.match(name)
    if not m:
        return None
    d = m.groupdict()
    for k in ("size", "threads", "nb_lo", "nb_hi"):
        d[k] = int(d[k])
    d["rep"] = int(d["rep"]) if d["rep"] else 1
    return d


def load_machines() -> dict:
    with paths.MACHINES_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _read_one(
    csv: Path, config: str | None, schema: list[str] | None = None
) -> pd.DataFrame:
    df = pd.read_csv(csv)
    missing = [c for c in (schema or SCHEMA) if c not in df.columns]
    if missing:
        raise ValueError(f"{csv.name}: 必須列が無い {missing}")

    meta = parse_filename(csv.name)
    df["node"] = meta["node"] if meta else csv.name.split("_")[0]
    df["stamp"] = meta["stamp"] if meta else "unknown"
    df["rep"] = meta["rep"] if meta else 1
    df["source_file"] = csv.name
    if config is not None:
        df["config"] = config
    return df


def load_sweeps(use_parquet: bool = True) -> pd.DataFrame:
    """
    raw/qr_sweep/{config}/*.csv を全部読む。

    derived/qr_sweep.parquet があればそちらを使う（速いため）。
    生データから読み直したいときは use_parquet=False。
    """
    if use_parquet and paths.SWEEP_PARQUET.exists():
        return pd.read_parquet(paths.SWEEP_PARQUET)

    frames = [
        _read_one(csv, config=csv.parent.name)
        for csv in sorted(paths.RAW_SWEEP.glob("*/*.csv"))
    ]
    if not frames:
        raise FileNotFoundError(f"qr_sweep の CSV が無い: {paths.RAW_SWEEP}")
    return pd.concat(frames, ignore_index=True)


def load_kernel(use_parquet: bool = True) -> pd.DataFrame:
    """
    raw/kernel_dtsmqr/{node}/*.csv を全部読む。

    注意: qr_sweep と列構成が完全に同一（threads,size,nb,ib,GFlops）で、
    中身からは区別できない。置き場所だけが種別を担保している。
    走査範囲も違う（kernel は nb=4 から、sweep は nb=20 から）。
    """
    if use_parquet and paths.KERNEL_PARQUET.exists():
        return pd.read_parquet(paths.KERNEL_PARQUET)

    frames = [
        _read_one(csv, config=None)
        for csv in sorted(paths.RAW_KERNEL.glob("*/*.csv"))
    ]
    if not frames:
        raise FileNotFoundError(f"kernel_dtsmqr の CSV が無い: {paths.RAW_KERNEL}")
    return pd.concat(frames, ignore_index=True)


def load_ssrfb(use_parquet: bool = True) -> pd.DataFrame:
    """
    raw/ssrfb/{node}/*.csv を全部読む。

    ssrfb は Time_sec 列を持つ点が qr_sweep / kernel_dtsmqr と違う。
    列構成で種別が判別できる唯一の測定。
    """
    if use_parquet and paths.SSRFB_PARQUET.exists():
        return pd.read_parquet(paths.SSRFB_PARQUET)

    frames = [
        _read_one(csv, config=None, schema=SSRFB_SCHEMA)
        for csv in sorted(paths.RAW_SSRFB.glob("*/*.csv"))
    ]
    if not frames:
        raise FileNotFoundError(f"ssrfb の CSV が無い: {paths.RAW_SSRFB}")
    return pd.concat(frames, ignore_index=True)


def load_optima() -> pd.DataFrame:
    """derived/optima.csv を読む。無ければ ingest.py を先に実行する。"""
    if not paths.OPTIMA_CSV.exists():
        raise FileNotFoundError(
            f"{paths.OPTIMA_CSV} がありません。"
            "先に `python scripts/ingest.py` を実行してください。"
        )
    return pd.read_csv(paths.OPTIMA_CSV)


def arch_of(node: str, machines: dict | None = None) -> str | None:
    """ノード名から architecture を引く。"""
    machines = machines or load_machines()
    entry = (machines.get("nodes") or {}).get(node)
    return entry.get("arch") if entry else None
