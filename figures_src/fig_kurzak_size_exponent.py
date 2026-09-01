#!/usr/bin/env python3
"""
図: 崖位置のサイズ指数 delta を Kurzak のタイル比 (delta=1) と本研究 (0.715) で比べる

Kurzak の並列項は c*P*(NB/N)**2.5 という **タイル比** の形なので、
nb と size の指数の絶対値が等しい（sigma = kappa、すなわち delta = 1）。
本研究の主張は delta < 1、つまり崖位置が size に比例しないこと。

  (左)  delta だけ固定して掃引したときの当てはまり
  (中)  同じ掃引での LOOCV ゼロショット予測性能
  (右)  モデルを介さない直接証拠。実測 nb_opt の size 依存の傾き

右パネルはモデルに依存しないので、delta<1 の主張の土台になる。

使い方:
    python figures_src/fig_kurzak_size_exponent.py --preset slide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import kurzak, style  # noqa: E402

STEM = "fig_kurzak_size_exponent"

DELTAS = np.array([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3])
D_KURZAK = 1.0
D_OURS = 0.715


def pooled_slope(df):
    """log nb_opt = slope * log size + 構成ごとの切片。傾きと標準誤差を返す。"""
    x, y, cfg = [], [], []
    for c, sub in df.groupby("config"):
        pts = sub.loc[sub.groupby("size")["GFlops"].idxmax()]
        for _, r in pts.iterrows():
            x.append(np.log(float(r["size"])))
            y.append(np.log(float(r["nb"])))
            cfg.append(c)
    x, y, cfg = np.array(x), np.array(y), np.array(cfg)
    cs = sorted(set(cfg))
    m = np.zeros((len(y), len(cs) + 1))
    m[:, 0] = x
    for i, c in enumerate(cs):
        m[cfg == c, i + 1] = 1
    b, *_ = np.linalg.lstsq(m, y, rcond=None)
    res = y - m @ b
    s2 = res @ res / (len(y) - m.shape[1])
    se = float(np.sqrt(s2 * np.linalg.pinv(m.T @ m)[0, 0]))
    return float(b[0]), se


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="slide", choices=["slide", "paper"])
    # 既定は figures/（管理外）。確定版は --outdir figures_final/卒論 のように渡す。
    ap.add_argument("--outdir", default=None,
                    help="出力先。既定は figures/（Git 管理外の探索用）")
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
        rms = np.array([kurzak.fit(d, fixed=dict(delta=v), **kw)["rms"] for v in DELTAS])
        ax.plot(DELTAS, rms / rms.min(), marker="o", label=label)
    ax.axvline(D_OURS, color="#1F77B4", ls="--", lw=1.5)
    ax.axvline(D_KURZAK, color="#D62728", ls="--", lw=1.5)
    ax.text(D_OURS, 0.03, " 本研究 0.715", color="#1F77B4",
            transform=ax.get_xaxis_transform(), va="bottom", ha="left",
            fontsize=11, rotation=90)
    ax.text(D_KURZAK, 0.03, " Kurzak タイル比 1.0", color="#D62728",
            transform=ax.get_xaxis_transform(), va="bottom", ha="left",
            fontsize=11, rotation=90)
    ax.set_xlabel("サイズ指数 $\\delta$")
    ax.set_ylabel("正規化 RMS（各系列の最小=1）")
    ax.set_title("(a) 全点同時フィットの当てはまり")
    ax.legend(fontsize=8.5, loc="upper right")

    # --- (b) LOOCV ---
    ax = axes[1]
    mean, worst = [], []
    for v in DELTAS:
        cv = kurzak.loocv(df, fixed=dict(delta=v))
        mean.append(cv["perf"].mean())
        worst.append(cv["perf"].min())
    ax.plot(DELTAS, mean, marker="o", color="#1F77B4", label="平均")
    ax.plot(DELTAS, worst, marker="s", color="#AA4EFF", label="最悪")
    ax.axvline(D_OURS, color="#1F77B4", ls="--", lw=1.5)
    ax.axvline(D_KURZAK, color="#D62728", ls="--", lw=1.5)
    ax.set_xlabel("サイズ指数 $\\delta$")
    ax.set_ylabel("性能比 $G(nb_{pred})/G_{max}$")
    ax.set_title("(b) LOOCV ゼロショット予測（31点）")
    ax.legend(fontsize=10, loc="lower left")

    # --- (c) モデルに依らない直接証拠 ---
    ax = axes[2]
    for c, sub in df.groupby("config"):
        pts = sub.loc[sub.groupby("size")["GFlops"].idxmax()].sort_values("size")
        ax.plot(pts["size"], pts["nb"], "o-", ms=5, lw=1.3, alpha=0.55,
                color=style.color_for(c))
    slope, se = pooled_slope(df)
    base_x = np.array([1024.0, 16384.0])
    for expo, ls, col, lab in [(slope, "-", "#333333", f"実測の傾き {slope:.2f}±{se:.2f}"),
                               (1.0, "--", "#D62728", "Kurzak タイル比 → 傾き 1.0")]:
        ax.plot(base_x, 122 * (base_x / 1024.0) ** expo, ls, color=col, lw=2.8, label=lab)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.set_xticks([1024, 2048, 4096, 8192, 16384])
    ax.set_xticklabels(["1k", "2k", "4k", "8k", "16k"])
    ax.set_xlabel("行列サイズ $N$")
    ax.set_ylabel("実測 $nb_{opt}$")
    ax.set_title("(c) 実測 $nb_{opt}$ のサイズ依存（両対数）")
    ax.legend(fontsize=10, loc="upper left", title="細線: 9構成それぞれ",
              title_fontsize=9)

    fig.suptitle("崖位置のサイズ指数: Kurzak のタイル比 $(nb/N)$ と本研究 $\\delta<1$", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    for p in style.save(fig, STEM, outdir=args.outdir, preset=args.preset):
        print(f"生成: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
