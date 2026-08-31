#!/usr/bin/env python3
"""spotcheck.py — 既存 qr_sweep データの代表点を再計測して比を出す。

計測機の構成が当時と変わっていないかを 10 分で確かめるための道具。
2026-08-31 に i5-7400 のシングルチャネル汚染を検出したのがこの手順。

    python3 studies/i5-7400_memory_channel/spotcheck.py \
        --config i5-7400_s1_smt-off --size 4096 --out /tmp/ch.csv

比が 1.00±0.02 に収まればそのデータは検証済みとしてよい。
外れた場合、まず帯域と負荷時クロックを実測して交絡を切り分けること
（チャネル構成・ターボ・サーマルのいずれでも比はずれる）。

注意: 計測順はトライアルごとにランダム化している。nb 昇順で回すと
熱ドリフトが nb 依存のバイアスとして紛れ込み、nb* を歪める。
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import random
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Workspace/plasma-bench/src"))
from plasma_perf.benchmarks.tileqr.runner import TileQRBenchmark  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_reference(config: str, size: int) -> dict:
    """raw/qr_sweep/{config}/ から (nb, ib) -> トライアル平均 を作る。"""
    acc = defaultdict(list)
    pattern = os.path.join(ROOT, "raw", "qr_sweep", config, f"*size{size}_*.csv")
    for path in glob.glob(pattern):
        with open(path) as fh:
            for row in csv.DictReader(fh):
                acc[(int(row["nb"]), int(row["ib"]))].append(float(row["GFlops"]))
    if not acc:
        sys.exit(f"[ERROR] 参照データが無い: {pattern}")
    return {k: st.mean(v) for k, v in acc.items()}


def pick_points(ref: dict, n: int) -> list:
    """nb 方向に散らして n 点選ぶ。各 nb では最良の ib を採る。

    ピーク近傍だけを見ると構成差を見落とす。構成の影響は nb 依存で出るので、
    小 nb（タスクオーバーヘッド律速）から大 nb（DRAM 律速）まで拾う。
    """
    best_ib = {}
    for (nb, ib), g in ref.items():
        if nb not in best_ib or g > ref[(nb, best_ib[nb])]:
            best_ib[nb] = ib
    nbs = sorted(best_ib)
    picked = [nbs[round(i * (len(nbs) - 1) / (n - 1))] for i in range(n)]
    return [(nb, best_ib[nb]) for nb in sorted(set(picked))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="i5-7400_s1_smt-off",
                    help="raw/qr_sweep/ 直下のディレクトリ名")
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--threads", type=int, default=os.cpu_count())
    ap.add_argument("--points", type=int, default=10)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--out", default=None, help="トライアル単位の生データ出力先 CSV")
    args = ap.parse_args()

    ref = load_reference(args.config, args.size)
    pts = pick_points(ref, args.points)

    bench = TileQRBenchmark()
    env = bench.make_env(args.threads)
    print(f"参照: {args.config} size={args.size} / 再計測: threads={args.threads} "
          f"{len(pts)}点 x {args.trials}トライアル", flush=True)

    got = defaultdict(list)
    rows = []
    for trial in range(1, args.trials + 1):
        order = pts[:]
        random.shuffle(order)
        for nb, ib in order:
            r = bench.run_point(nb, ib, threads=args.threads, size=args.size,
                                env=env, timeout=300, wrapper=None)
            if r.ok:
                got[(nb, ib)].append(r.values["GFlops"])
                rows.append([trial, args.threads, args.size, nb, ib, r.values["GFlops"]])
        print(f"  trial {trial}/{args.trials} 完了", flush=True)

    print(f"\n{'nb':>5}{'ib':>5}{'参照':>10}{'今回':>10}{'比':>8}")
    print("-" * 38)
    ratios = []
    for nb, ib in pts:
        if not got[(nb, ib)]:
            continue
        a, b = ref[(nb, ib)], st.mean(got[(nb, ib)])
        ratios.append(b / a)
        print(f"{nb:>5}{ib:>5}{a:>10.2f}{b:>10.2f}{b / a:>8.3f}")
    print("-" * 38)
    print(f"平均 {st.mean(ratios):.3f} / 範囲 {min(ratios):.3f}〜{max(ratios):.3f}")
    if max(ratios) - min(ratios) > 0.04:
        print("\n[警告] 比が nb によってばらついている。一様なオフセットではないので、"
              "\n       クロック差ではなくメモリ構成やキャッシュ条件の変化を疑うこと。")
    elif abs(st.mean(ratios) - 1.0) > 0.02:
        print("\n[警告] 比が一様にずれている。クロック/ターボ設定の変化を疑うこと。")
    else:
        print("\n参照データは検証済みとしてよい。")

    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["trial", "threads", "size", "nb", "ib", "GFlops"])
            w.writerows(sorted(rows, key=lambda x: (x[0], x[3], x[4])))
        print(f"生データ: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
