#!/usr/bin/env python3
"""
図: 並列項のコア数指数 mu を Kurzak の 1.0 と本研究の 0.58 で比べる

並列項の分母は 1 + (定数) * p**mu * nb**kappa * size**(-sigma) と書ける。
Kurzak (2008) は mu = 1.0、本研究は mu = m*k0 = 0.24*2.41 = 0.58。
mu 以外を自由にしたまま mu だけ固定して掃引し、

  (左)  当てはまりの悪さ（正規化 RMS）が mu をどう見るか
  (中)  LOOCV ゼロショット予測の性能比が mu をどう見るか
  (右)  同一CPU・コア数だけ違う唯一の対比（AOBA-B 64 vs 128 コア）

を1枚に並べる。右パネルを入れているのは、左中の谷が
「機種をまたぐ変動」に依存していて beta と交絡しているため。
交絡のない対比を並べて置かないと、指数を言い切れない。

使い方:
    python figures/fig_kurzak_p_exponent.py --preset slide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, kurzak, style  # noqa: E402

STEM = "fig_kurzak_p_exponent"

MUS = np.array([0.0, 0.15, 0.24, 0.4, 0.5, 0.58, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0])
MU_KURZAK = 1.0
MU_OURS = 0.58


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="slide", choices=["slide", "paper"])
    args = ap.parse_args()
    style.use(args.preset)

    df = kurzak.load_qr_curves()
    no_aoba = df[~df["config"].str.startswith("aoba")]

    variants = [
        ("全31点 (beta 自由)", df, dict()),
        ("AOBA を除く (p<=32)", no_aoba, dict()),
        ("beta を SSRFB 実測に固定", df, dict(beta_fixed=kurzak.BETA_MEASURED)),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.3))

    # --- (a) 当てはまり ---
    ax = axes[0]
    for label, d, kw in variants:
        rms = np.array([kurzak.fit(d, mu_fixed=mu, **kw)["rms"] for mu in MUS])
        ax.plot(MUS, rms / rms.min(), marker="o", label=label)
    ax.axvline(MU_OURS, color="#1F77B4", ls="--", lw=1.5)
    ax.axvline(MU_KURZAK, color="#D62728", ls="--", lw=1.5)
    ax.text(MU_OURS, 0.02, " 本研究 0.58", color="#1F77B4", transform=ax.get_xaxis_transform(),
            va="bottom", ha="left", fontsize=11, rotation=90)
    ax.text(MU_KURZAK, 0.02, " Kurzak 1.0", color="#D62728", transform=ax.get_xaxis_transform(),
            va="bottom", ha="left", fontsize=11, rotation=90)
    ax.set_xlabel("コア数の指数 $\\mu$")
    ax.set_ylabel("正規化 RMS（各系列の最小=1）")
    ax.set_title("(a) 全点同時フィットの当てはまり")
    ax.legend(fontsize=8.5, loc="upper left")

    # --- (b) LOOCV ---
    ax = axes[1]
    mean, worst = [], []
    for mu in MUS:
        cv = kurzak.loocv(df, mu_fixed=mu)
        mean.append(cv["perf"].mean())
        worst.append(cv["perf"].min())
    ax.plot(MUS, mean, marker="o", color="#1F77B4", label="平均")
    ax.plot(MUS, worst, marker="s", color="#AA4EFF", label="最悪")
    ax.axvline(MU_OURS, color="#1F77B4", ls="--", lw=1.5)
    ax.axvline(MU_KURZAK, color="#D62728", ls="--", lw=1.5)
    ax.set_xlabel("コア数の指数 $\\mu$")
    ax.set_ylabel("性能比 $G(nb_{pred})/G_{max}$")
    ax.set_title("(b) LOOCV ゼロショット予測（31点）")
    ax.legend(fontsize=10)

    # --- (c) 交絡のない唯一の対比 ---
    ax = axes[2]
    opt = io.load_optima()
    aoba = opt[opt["config"].str.startswith("aoba")]
    txt = []
    for i, size in enumerate([4096, 8192]):
        s1 = aoba[(aoba["size"] == size) & (aoba["config"] == "aoba-b_s1_smt-off")]["nb_opt"]
        s2 = aoba[(aoba["size"] == size) & (aoba["config"] == "aoba-b_s2_smt-off")]["nb_opt"]
        c = ["#1F77B4", "#AA4EFF"][i]
        ax.plot([64] * len(s1), s1, "o", color=c, alpha=0.6, ms=8)
        ax.plot([128] * len(s2), s2, "o", color=c, alpha=0.6, ms=8)
        ax.plot([64, 128], [s1.mean(), s2.mean()], "-", color=c, lw=2.4,
                label=f"size={size}")
        m = np.log(s1.mean() / s2.mean()) / np.log(2)
        txt.append(f"size={size}: $m$={m:.2f}")
    for m, ls, c, lab in [(0.24, ":", "#1F77B4", "本研究 $m$=0.24"),
                          (1.0 / 2.41, "-.", "#D62728", "Kurzak 相当 $m$=0.41")]:
        ref = aoba[(aoba["size"] == 4096) & (aoba["config"] == "aoba-b_s1_smt-off")]["nb_opt"].mean()
        ax.plot([64, 128], [ref, ref * 2 ** (-m)], ls, color=c, lw=2, label=lab)
    ax.set_xscale("log", base=2)
    ax.set_xticks([64, 128])
    ax.set_xticklabels(["64", "128"])
    ax.set_xlabel("物理コア数 $p$（同一CPU: EPYC 7702）")
    ax.set_ylabel("実測 $nb_{opt}$")
    ax.set_title("(c) 同一CPUでのコア数対比\n" + " / ".join(txt))
    ax.legend(fontsize=9, loc="upper right")

    fig.suptitle("並列項のコア数指数: Kurzak $P^{1.0}$ と本研究 $p^{0.58}$", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    for p in style.save(fig, STEM, preset=args.preset):
        print(f"生成: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
