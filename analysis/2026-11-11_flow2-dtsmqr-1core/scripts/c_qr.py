"""4. 不老・弐の QR（p = 192、size 1024〜8192）と、当てはめなしのモデル p·A·E(nb)·η理論(nb) の比較。
A・β は b_fit.py の値（data/b_fits.csv、5回の平均）。η理論 = 1/(1 + (c·√p·nb/size)^k)、c = √7.5、k = 2
（analysis/2026-10-27_gen4-kernel-term/scripts/eta_eff.py と同じ式）。
QR の集計は analysis/2026-11-10_flow2-sweep-check/scripts/common.py の add_baseline（base）を主に、5回の平均も計算する。
出力 data/c_qr_curves.csv, c_qr_summary.csv, c_ratio_by_nb.csv, fig_qr_ratio.png"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python -I でも common を読めるようにする

import numpy as np
import pandas as pd

from common import DATA, OUT, ROOT, setup_plot  # noqa: E402

pd.set_option("display.width", 220)
P, C_TH, K_TH = 192, np.sqrt(7.5), 2.0
BAND = 0.95

_spec = importlib.util.spec_from_file_location(
    "sweep_common", ROOT / "analysis/2026-11-10_flow2-sweep-check/scripts/common.py")
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)


def qr_curves() -> pd.DataFrame:
    """(size, nb) ごとの QR の曲線。G_base：base（速い水準）の時間を GFlops に直し ib について最大。
    G_mean：(nb, ib) ごとに 5 回の GFlops を平均し ib について最大（ingest.py と同じ）。"""
    d = sw.add_baseline(sw.load_all())
    pt = d.groupby(["size", "nb", "ib"], as_index=False).agg(mean=("GFlops", "mean"), base_ms=("base", "first"))
    pt["base"] = sw.flops_dgeqrf(pt["size"]) / (pt.base_ms * 1e-3) / 1e9
    c = pt.groupby(["size", "nb"], as_index=False).agg(G_base=("base", "max"), G_mean=("mean", "max"))
    return c


def band(nb, g):
    i = int(np.argmax(g))
    ok = g >= BAND * g[i]
    lo = hi = i
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < len(g) - 1 and ok[hi + 1]:
        hi += 1
    return int(nb[i]), int(nb[lo]), int(nb[hi])


def main():
    F = pd.read_csv(DATA / "b_fits.csv")
    F = F[F.machine.str.startswith("flow2") & (F.target == "mean5")].set_index("proc")
    params = {"ib=nb/8": (F.loc["ib=nb/8", "A"], F.loc["ib=nb/8", "beta"]), "MaxIB": (F.loc["MaxIB", "A"], F.loc["MaxIB", "beta"])}
    c = qr_curves()
    c["N"] = c["size"] / c.nb
    c["eta_th"] = 1 / (1 + (C_TH * np.sqrt(P) * c.nb / c["size"]) ** K_TH)
    for k, (A, beta) in params.items():
        tag = "slice" if k == "ib=nb/8" else "maxib"
        c[f"pred_{tag}"] = P * A * c.nb / (c.nb + beta) * c.eta_th
    c.to_csv(DATA / "c_qr_curves.csv", index=False, float_format="%.5g")

    rows = []
    for (k, (A, beta)), tag in zip(params.items(), ["slice", "maxib"]):
        for agg in ["G_base", "G_mean"]:
            for s, g in c.groupby("size"):
                g = g.sort_values("nb")
                nb, obs, pred = g.nb.to_numpy(), g[agg].to_numpy(), g[f"pred_{tag}"].to_numpy()
                ip = int(np.argmax(pred))
                nb_o, lo, hi = band(nb, obs)
                rows.append(dict(kernel=k, agg=agg[2:], size=s, nb_pred=int(nb[ip]), nb_obs=nb_o, band_lo=lo, band_hi=hi,
                                 in_band=lo <= nb[ip] <= hi, perf=obs[ip] / obs.max(), G_obs_peak=obs.max(),
                                 G_pred_peak=pred[ip], obs_over_pred_at_pred=obs[ip] / pred[ip],
                                 obs_over_pred_peak=obs.max() / pred.max()))
    S = pd.DataFrame(rows)
    S.to_csv(DATA / "c_qr_summary.csv", index=False, float_format="%.5g")
    print(S.round(3).to_string(index=False))

    # η_eff / η理論 = 実測 / 予測 の nb 依存（断面の A・β）
    grid = [32, 48, 64, 96, 128, 160, 192, 256, 320, 384, 448, 512]
    t = c[c.nb.isin(grid)].copy()
    out = []
    for agg in ["G_base", "G_mean"]:
        for tag in ["slice", "maxib"]:
            t["ratio"] = t[agg] / t[f"pred_{tag}"]
            w = t.pivot(index="size", columns="nb", values="ratio")
            w.insert(0, "kernel", tag)
            w.insert(0, "agg", agg[2:])
            out.append(w.reset_index())
    R = pd.concat(out)
    R.to_csv(DATA / "c_ratio_by_nb.csv", index=False, float_format="%.4f")
    print(R[(R.kernel == "slice")].round(3).to_string(index=False))
    print(R[(R.kernel == "maxib") & (R["agg"] == "base")].round(3).to_string(index=False))

    plt = setup_plot()
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    col = {1024: "#1f77b4", 2048: "#2ca02c", 4096: "#d95f02", 8192: "#7570b3"}
    for s, g in c.groupby("size"):
        g = g.sort_values("nb")
        axs[0].plot(g.nb, g.G_base / g.pred_slice, "-", lw=1.2, color=col[s], label=f"size {s}（base）")
        axs[0].plot(g.nb, g.G_mean / g.pred_slice, ":", lw=0.9, color=col[s])
        sc = g.G_base.max()
        axs[1].plot(g.nb, g.G_base / sc, "-", lw=1.2, color=col[s], label=f"size {s} 実測（base）")
        axs[1].plot(g.nb, g.pred_slice / sc, "--", lw=1, color=col[s])
    axs[0].axhline(1, color="k", lw=0.5)
    axs[0].set_title("実測 / 予測 = η_eff / η理論（実線 base、点線 5回の平均）")
    axs[0].set_xlabel("nb")
    axs[0].set_ylabel("G_QR / (p·A·E·η理論)")
    axs[1].set_title("実測（実線）と予測（破線）。実測の最大で割った値")
    axs[1].set_xlabel("nb")
    axs[1].set_ylabel("GFlops / 実測の最大（対数）")
    axs[1].set_yscale("log")
    for a in axs:
        a.grid(alpha=0.3)
        a.legend(fontsize=8)
    fig.suptitle(f"不老・弐 QR（p = 192）と当てはめなしのモデル（A = {params['ib=nb/8'][0]:.1f}、β = {params['ib=nb/8'][1]:.0f}、1コアのクロックのまま）", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig_qr_ratio.png")


if __name__ == "__main__":
    main()
