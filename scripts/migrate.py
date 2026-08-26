#!/usr/bin/env python3
"""
既存の benchmark CSV を tileQR_data の命名規則へ移行する。

旧命名の問題:
  par001_size4096_nb20512_t1_20260607_235252.csv
    - t1 はスレッド数ではない（中身は 128 スレッド）
    - nb20512 が 20-512 か 205-12 か曖昧
    - スレッド数がファイル名から読めない

新命名:
  {node}_size{N}_t{threads}_nb{lo}-{hi}_{YYYYMMDD-HHMMSS}.csv

配置先:
  qr_sweep      → raw/qr_sweep/{arch}_s{sockets_used}_smt-{on|off}/
  kernel_dtsmqr → raw/kernel_dtsmqr/{node}/

スレッド数は必ず CSV の中身から判定する（ファイル名を信用しない）。

使い方:
    python scripts/migrate.py SRC_DIR [--out raw] [--apply]

--apply を付けるまでは dry-run（何もコピーしない）。
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# --- 旧ファイル名のパターン ------------------------------------------------

# 例: par001_size4096_nb20512_t1_20260607_235252.csv
RE_SWEEP_OLD = re.compile(
    r"^(?P<node>[A-Za-z0-9\-]+)"
    r"_size(?P<size>\d+)"
    r"_nb(?P<nbraw>\d+)"
    r"_t\d+"
    r"_(?P<date>\d{8})_(?P<time>\d{6})\.csv$"
)

# 例: corei5-13400F-16_benchmark_dtsmqr.csv
RE_KERNEL_OLD = re.compile(
    r"^(?P<node>[A-Za-z0-9\-]+?)-(?P<threads>\d+)_benchmark_dtsmqr\.csv$"
)


def read_csv_facts(path: Path) -> dict:
    """CSV の中身から threads / size / nb 範囲を読む。ファイル名は信用しない。"""
    threads, sizes, nbs = set(), set(), set()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = {"threads", "size", "nb"} - set(
            (reader.fieldnames or [])
        )
        if missing:
            raise ValueError(f"必須列が無い: {sorted(missing)}")
        for row in reader:
            threads.add(int(row["threads"]))
            sizes.add(int(row["size"]))
            nbs.add(int(row["nb"]))
    if not nbs:
        raise ValueError("データ行が 0 件")
    return {
        "threads": sorted(threads),
        "sizes": sorted(sizes),
        "nb_lo": min(nbs),
        "nb_hi": max(nbs),
    }


def resolve_config(node: str, threads: int) -> str:
    """
    ノードとスレッド数から config ディレクトリ名を決める。

    AOBA-B は 2 ソケット 128 物理コア。64 スレッド実行は
    numactl --cpunodebind=0 による片ソケット固定なので s1 とみなす。
    ここは machines.yaml の configs と一致させること。
    """
    if node.startswith("par"):
        sockets_used = 2 if threads > 64 else 1
        return f"aoba-b_s{sockets_used}_smt-off"
    # 単一ソケット機はすべて s1。SMT の有無は要確認のため unknown を立てる。
    return f"{node}_s1_smt-unknown"


def plan(src_dir: Path, out_root: Path) -> tuple[list[tuple[Path, Path]], list[str]]:
    moves: list[tuple[Path, Path]] = []
    warnings: list[str] = []

    for path in sorted(src_dir.glob("*.csv")):
        m_sweep = RE_SWEEP_OLD.match(path.name)
        m_kernel = RE_KERNEL_OLD.match(path.name)

        try:
            facts = read_csv_facts(path)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{path.name}: 読めないので スキップ — {exc}")
            continue

        if len(facts["threads"]) != 1:
            warnings.append(
                f"{path.name}: 1ファイルに複数のスレッド数 {facts['threads']} "
                "が混在。分割が必要。"
            )
            continue
        if len(facts["sizes"]) != 1:
            warnings.append(
                f"{path.name}: 1ファイルに複数の size {facts['sizes']} が混在。"
            )
            continue

        threads = facts["threads"][0]
        size = facts["sizes"][0]
        nb_lo, nb_hi = facts["nb_lo"], facts["nb_hi"]

        if m_sweep:
            node = m_sweep.group("node")
            stamp = f"{m_sweep.group('date')}-{m_sweep.group('time')}"

            # 旧名の nb 表記と実データを突き合わせる
            nbraw = m_sweep.group("nbraw")
            if nbraw != f"{nb_lo}{nb_hi}":
                warnings.append(
                    f"{path.name}: 旧名の nb 表記 '{nbraw}' が実データ "
                    f"{nb_lo}-{nb_hi} と一致しない。実データを採用。"
                )

            config = resolve_config(node, threads)
            newname = f"{node}_size{size}_t{threads}_nb{nb_lo}-{nb_hi}_{stamp}.csv"
            dest = out_root / "qr_sweep" / config / newname

        elif m_kernel:
            node = m_kernel.group("node")
            name_threads = int(m_kernel.group("threads"))
            if name_threads != threads:
                warnings.append(
                    f"{path.name}: 旧名のスレッド数 {name_threads} と "
                    f"実データ {threads} が不一致。実データを採用。"
                )
            # kernel 系は旧名にタイムスタンプが無い
            stamp = "nodate"
            warnings.append(
                f"{path.name}: 計測日時がファイル名に無いため 'nodate'。"
                "判明したら手動でリネームを。"
            )
            newname = f"{node}_size{size}_t{threads}_nb{nb_lo}-{nb_hi}_{stamp}.csv"
            dest = out_root / "kernel_dtsmqr" / node / newname

        else:
            warnings.append(f"{path.name}: 命名規則にマッチせず スキップ")
            continue

        moves.append((path, dest))

    return moves, warnings


def report_coverage(moves: list[tuple[Path, Path]]) -> None:
    """config × threads のカバレッジを出し、欠損を見つけやすくする。"""
    grid: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for _, dest in moves:
        if dest.parent.parent.name != "qr_sweep":
            continue
        config = dest.parent.name
        m = re.search(r"_t(\d+)_", dest.name)
        node = dest.name.split("_")[0]
        if m:
            grid[config][int(m.group(1))].append(node)

    if not grid:
        return
    print("\n--- qr_sweep カバレッジ ---")
    for config in sorted(grid):
        for threads in sorted(grid[config]):
            nodes = sorted(grid[config][threads])
            print(f"  {config:<24} t={threads:<4} {len(nodes)}件  {', '.join(nodes)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="既存 CSV のあるディレクトリ")
    ap.add_argument("--out", type=Path, default=Path("raw"), help="出力ルート")
    ap.add_argument("--apply", action="store_true", help="実際にコピーする")
    args = ap.parse_args()

    if not args.src.is_dir():
        print(f"エラー: {args.src} はディレクトリではありません", file=sys.stderr)
        return 1

    moves, warnings = plan(args.src, args.out)

    print(f"=== 移行計画 ({len(moves)} 件) ===")
    for src, dest in moves:
        print(f"  {src.name}")
        print(f"    -> {dest}")

    if warnings:
        print(f"\n=== 警告 ({len(warnings)} 件) ===")
        for w in warnings:
            print(f"  ! {w}")

    report_coverage(moves)

    if args.apply:
        for src, dest in moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        print(f"\n{len(moves)} 件をコピーしました。")
    else:
        print("\n(dry-run。実行するには --apply を付けてください)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
