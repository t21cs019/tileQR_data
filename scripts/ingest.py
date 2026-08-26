#!/usr/bin/env python3
"""
raw/ → derived/ を生成する。

出力:
  derived/qr_sweep.parquet       全 sweep を結合したもの
  derived/kernel_dtsmqr.parquet  カーネル計測を結合したもの
  derived/optima.csv             構成×ノード×スレッド×サイズごとの最適 nb
  COVERAGE.md                    カバレッジと欠損

**最適 nb の定義はこのファイルだけが持つ。** 図もダッシュボードも
derived/ を読むだけにすること。定義を変えたいときはここを直す。

使い方:
    python scripts/ingest.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, paths  # noqa: E402

# 性能帯の閾値。ピークの何割以上を「実用上ほぼ最適」とみなすか。
BAND = 0.95

GROUP_KEYS = ["config", "node", "threads", "size"]


def best_over_ib(df: pd.DataFrame) -> pd.DataFrame:
    """各 (group, nb) について ib を最適化した性能を取る。"""
    keys = GROUP_KEYS + ["nb"]
    idx = df.groupby(keys, observed=True)["GFlops"].idxmax()
    return df.loc[idx].reset_index(drop=True)


def band_range(sub: pd.DataFrame, peak: float) -> tuple[int, int]:
    """
    ピークの BAND 倍以上を満たす nb の連続区間を返す。

    飛び地がある場合はピークを含む連続区間だけを取る。
    探索範囲の上下界を議論するとき、離れた点を含めると意味が薄れるため。
    """
    s = sub.sort_values("nb").reset_index(drop=True)
    ok = s["GFlops"] >= peak * BAND
    peak_pos = s["GFlops"].idxmax()

    lo = peak_pos
    while lo - 1 >= 0 and ok.iloc[lo - 1]:
        lo -= 1
    hi = peak_pos
    while hi + 1 < len(s) and ok.iloc[hi + 1]:
        hi += 1

    return int(s.loc[lo, "nb"]), int(s.loc[hi, "nb"])


def build_optima(sweeps: pd.DataFrame) -> pd.DataFrame:
    per_nb = best_over_ib(sweeps)
    rows = []

    for keys, sub in per_nb.groupby(GROUP_KEYS, observed=True):
        peak_row = sub.loc[sub["GFlops"].idxmax()]
        lo, hi = band_range(sub, float(peak_row["GFlops"]))
        rows.append(
            dict(
                zip(GROUP_KEYS, keys),
                nb_opt=int(peak_row["nb"]),
                ib_opt=int(peak_row["ib"]),
                GFlops_max=float(peak_row["GFlops"]),
                nb_lo95=lo,
                nb_hi95=hi,
                nb_scanned_lo=int(sub["nb"].min()),
                nb_scanned_hi=int(sub["nb"].max()),
                n_nb=int(sub["nb"].nunique()),
            )
        )

    return pd.DataFrame(rows).sort_values(GROUP_KEYS).reset_index(drop=True)


def write_coverage(optima: pd.DataFrame, kernel: pd.DataFrame | None) -> None:
    lines = [
        "# COVERAGE",
        "",
        "`scripts/ingest.py` が自動生成する。手で編集しない。",
        "",
        "## qr_sweep",
        "",
        "| config | threads | size | ノード数 | ノード |",
        "|---|---|---|---|---|",
    ]

    grid = defaultdict(list)
    for _, r in optima.iterrows():
        grid[(r["config"], r["threads"], r["size"])].append(r["node"])

    for (config, threads, size), nodes in sorted(grid.items()):
        nodes = sorted(nodes)
        lines.append(
            f"| `{config}` | {threads} | {size} | {len(nodes)} | {', '.join(nodes)} |"
        )

    # 同一 config 内でノードの揃い方に差があれば欠損として挙げる
    lines += ["", "## 欠損の候補", ""]
    by_config = defaultdict(set)
    for (config, threads, size), nodes in grid.items():
        by_config[config] |= set(nodes)

    found_gap = False
    for (config, threads, size), nodes in sorted(grid.items()):
        missing = sorted(by_config[config] - set(nodes))
        if missing:
            found_gap = True
            lines.append(
                f"- `{config}` threads={threads} size={size}: "
                f"未計測 {', '.join(missing)}"
            )
    if not found_gap:
        lines.append("- なし")

    if kernel is not None and not kernel.empty:
        lines += ["", "## kernel_dtsmqr", "", "| node | threads | nb 範囲 |", "|---|---|---|"]
        g = kernel.groupby(["node", "threads"], observed=True)["nb"].agg(["min", "max"])
        for (node, threads), r in g.iterrows():
            lines.append(f"| {node} | {threads} | {int(r['min'])}-{int(r['max'])} |")

    paths.COVERAGE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    paths.DERIVED.mkdir(parents=True, exist_ok=True)

    sweeps = io.load_sweeps(use_parquet=False)
    sweeps.to_parquet(paths.SWEEP_PARQUET, index=False)
    print(f"書き出し: {paths.SWEEP_PARQUET.name}  ({len(sweeps):,} 行)")

    try:
        kernel = io.load_kernel(use_parquet=False)
        kernel.to_parquet(paths.KERNEL_PARQUET, index=False)
        print(f"書き出し: {paths.KERNEL_PARQUET.name}  ({len(kernel):,} 行)")
    except FileNotFoundError:
        kernel = None
        print("kernel_dtsmqr のデータなし。スキップ。")

    optima = build_optima(sweeps)
    optima.to_csv(paths.OPTIMA_CSV, index=False)
    print(f"書き出し: {paths.OPTIMA_CSV.name}  ({len(optima)} 行)")

    write_coverage(optima, kernel)
    print(f"書き出し: {paths.COVERAGE_MD.name}")

    print(f"\n--- 最適 nb と {int(BAND * 100)}% 性能帯 ---")
    cols = ["config", "node", "threads", "size", "nb_opt", "GFlops_max",
            "nb_lo95", "nb_hi95"]
    print(optima[cols].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
