#!/usr/bin/env python3
"""
raw/ 配下の健全性を検証する。push 前に走らせる。

検査項目:
  1. ファイル名が命名規則に沿っているか
  2. 必須列が揃っているか
  3. 1ファイルに threads / size が単一値か（混在は分割が必要）
  4. ファイル名の threads / size が中身と一致するか
     （旧命名で t1 がスレッド数でなかった事故の再発防止）
  5. ib <= nb か
  6. config ディレクトリが machines.yaml の configs にあるか
  7. node が machines.yaml の nodes にあるか
  8. 同一条件の重複がないか

使い方:
    python scripts/validate.py          # 問題があれば終了コード 1
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, paths  # noqa: E402


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def dump(self) -> int:
        if self.errors:
            print(f"\n=== エラー ({len(self.errors)}) ===")
            for e in self.errors:
                print(f"  x {e}")
        if self.warnings:
            print(f"\n=== 警告 ({len(self.warnings)}) ===")
            for w in self.warnings:
                print(f"  ! {w}")
        if not self.errors and not self.warnings:
            print("問題なし。")
        return 1 if self.errors else 0


def check_file(csv: Path, config: str | None, rep: Report) -> dict | None:
    meta = io.parse_filename(csv.name)
    if meta is None:
        rep.error(f"{csv.name}: 命名規則に沿っていない")
        return None

    try:
        df = pd.read_csv(csv)
    except Exception as exc:  # noqa: BLE001
        rep.error(f"{csv.name}: 読めない — {exc}")
        return None

    missing = [c for c in io.SCHEMA if c not in df.columns]
    if missing:
        rep.error(f"{csv.name}: 必須列が無い {missing}")
        return None

    threads = sorted(df["threads"].unique())
    sizes = sorted(df["size"].unique())

    if len(threads) != 1:
        rep.error(f"{csv.name}: threads が混在 {threads}。分割が必要")
        return None
    if len(sizes) != 1:
        rep.error(f"{csv.name}: size が混在 {sizes}。分割が必要")
        return None

    if threads[0] != meta["threads"]:
        rep.error(
            f"{csv.name}: ファイル名の threads={meta['threads']} と "
            f"中身の {threads[0]} が不一致"
        )
    if sizes[0] != meta["size"]:
        rep.error(
            f"{csv.name}: ファイル名の size={meta['size']} と "
            f"中身の {sizes[0]} が不一致"
        )

    nb_lo, nb_hi = int(df["nb"].min()), int(df["nb"].max())
    if (nb_lo, nb_hi) != (meta["nb_lo"], meta["nb_hi"]):
        rep.warn(
            f"{csv.name}: ファイル名の nb {meta['nb_lo']}-{meta['nb_hi']} と "
            f"実データ {nb_lo}-{nb_hi} が不一致"
        )

    bad = df[df["ib"] > df["nb"]]
    if not bad.empty:
        rep.error(f"{csv.name}: ib > nb の行が {len(bad)} 件ある")

    if df["GFlops"].isna().any():
        rep.warn(f"{csv.name}: GFlops に欠損値がある")
    if (df["GFlops"] <= 0).any():
        rep.warn(f"{csv.name}: GFlops が 0 以下の行がある")

    if meta["stamp"] == "nodate":
        rep.warn(f"{csv.name}: 計測日時が不明（nodate）")

    return {"config": config, "node": meta["node"],
            "threads": threads[0], "size": sizes[0], "file": csv.name}


def main() -> int:
    rep = Report()
    machines = io.load_machines()
    known_configs = set((machines.get("configs") or {}).keys())
    known_nodes = set((machines.get("nodes") or {}).keys())

    seen: dict[tuple, list[str]] = defaultdict(list)
    n_files = 0

    # --- qr_sweep ---
    for config_dir in sorted(p for p in paths.RAW_SWEEP.glob("*") if p.is_dir()):
        config = config_dir.name
        if config not in known_configs:
            rep.error(
                f"config `{config}` が machines.yaml の configs に無い。"
                "計測条件が記録されないまま埋もれる"
            )
        for csv in sorted(config_dir.glob("*.csv")):
            n_files += 1
            info = check_file(csv, config, rep)
            if info is None:
                continue
            if info["node"] not in known_nodes:
                rep.error(f"node `{info['node']}` が machines.yaml の nodes に無い")
            key = (config, info["node"], info["threads"], info["size"])
            seen[key].append(info["file"])

    # --- kernel_dtsmqr ---
    for node_dir in sorted(p for p in paths.RAW_KERNEL.glob("*") if p.is_dir()):
        if node_dir.name not in known_nodes:
            rep.error(f"node `{node_dir.name}` が machines.yaml の nodes に無い")
        for csv in sorted(node_dir.glob("*.csv")):
            n_files += 1
            info = check_file(csv, None, rep)
            if info and info["node"] != node_dir.name:
                rep.error(
                    f"{csv.name}: ファイル名のノード `{info['node']}` と "
                    f"ディレクトリ `{node_dir.name}` が不一致"
                )

    # --- 重複 ---
    for key, files in sorted(seen.items()):
        if len(files) > 1:
            rep.warn(
                f"同一条件 {key} に {len(files)} ファイル: {', '.join(files)}。"
                "再計測なら意図的か確認を"
            )

    print(f"検査したファイル: {n_files}")
    return rep.dump()


if __name__ == "__main__":
    raise SystemExit(main())
