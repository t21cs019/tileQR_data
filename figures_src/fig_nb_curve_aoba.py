#!/usr/bin/env python3
"""
図: AOBA-B の nb-性能曲線（ノード間ばらつき）

同一ハードのノード間でどれだけ個体差が出るかを見る図。
95% 性能帯を帯で重ねて、最適 nb の「幅」も同時に見えるようにしている。

使い方:
    python figures_src/fig_nb_curve_aoba.py --preset slide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, style  # noqa: E402

STEM = "fig_nb_curve_aoba"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="slide", choices=["slide", "paper"])
    # 既定は figures/（管理外）。確定版は --outdir figures_final/卒論 のように渡す。
    ap.add_argument("--outdir", default=None,
                    help="出力先。既定は figures/（Git 管理外の探索用）")
    args = ap.parse_args()

    style.use(args.preset)

    df = io.load_sweeps()
    df = df[df["config"].str.startswith("aoba-b")]
    if df.empty:
        print("aoba-b のデータがありません", file=sys.stderr)
        return 1

    # 各 (config, node, nb) で ib を最適化した性能
    best = df.groupby(["config", "node", "nb"], as_index=False)["GFlops"].max()

    configs = sorted(best["config"].unique())
    fig, axes = plt.subplots(
        1, len(configs), figsize=(9.5, 4.0), sharey=True
    )
    if len(configs) == 1:
        axes = [axes]

    for ax, config in zip(axes, configs):
        sub = best[best["config"] == config]
        for node in sorted(sub["node"].unique()):
            s = sub[sub["node"] == node].sort_values("nb")
            ax.plot(s["nb"], s["GFlops"], label=node, alpha=0.85)

        threads = 128 if "_s2_" in config else 64
        ax.set_title(f"{config}\n(threads={threads})")
        ax.set_xlabel("タイルサイズ nb")
        ax.legend(fontsize=9, ncol=2, loc="lower center")

    axes[0].set_ylabel("GFlops")
    fig.suptitle("AOBA-B  size=4096  nb-性能曲線のノード間ばらつき")
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    for p in style.save(fig, STEM, outdir=args.outdir, preset=args.preset):
        print(f"生成: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
