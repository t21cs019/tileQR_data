"""b. 予測の最適 nb での性能比（= 実測(予測の nb) / 実測の最大）を、集計ごと・size ごと・A・β の2通りで出す。
11-11 の c_qr_summary.csv（base と mean）と一致するかも確かめる。

出力 data/b_summary.csv（集計 × size × A・β）、data/b_ratio_by_nb.csv（実測/予測 の nb 依存、ib=nb/8 の A・β）、
     data/b_check_1111.csv（11-11 との突き合わせ）、fig_b_ratio.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from common import DATA, OUT, ROOT, band, kernel_params, predict, setup_plot  # noqa: E402

AGGS = ["fast", "slow", "mean", "slow_dt", "median"]


def main():
    c = pd.read_csv(DATA / "a_curves.csv")
    params = kernel_params()
    rows = []
    for k, (A, beta) in params.items():
        c[f"pred_{k}"] = predict(c["size"], c.nb, A, beta)
        for agg in AGGS:
            for s, g in c.groupby("size"):
                g = g.sort_values("nb")
                nb, obs, pred = g.nb.to_numpy(), g[agg].to_numpy(), g[f"pred_{k}"].to_numpy()
                ip = int(np.argmax(pred))
                nb_o, lo, hi = band(nb, obs)
                rows.append(dict(kernel=k, A=A, beta=beta, agg=agg, size=s, nb_pred=int(nb[ip]), nb_obs=nb_o,
                                 band_lo=lo, band_hi=hi, G_obs_peak=np.nanmax(obs), G_at_pred=obs[ip],
                                 perf=obs[ip] / np.nanmax(obs), obs_over_pred_at_pred=obs[ip] / pred[ip],
                                 obs_over_pred_at_obs=np.nanmax(obs) / pred[np.nanargmax(obs)]))
    S = pd.DataFrame(rows)
    S.to_csv(DATA / "b_summary.csv", index=False, float_format="%.5g")
    print(S.round(4).to_string(index=False))

    # 11-11 との突き合わせ（base = fast、mean = mean）
    old = pd.read_csv(ROOT / "analysis/2026-11-11_flow2-dtsmqr-1core/data/c_qr_summary.csv")
    old["agg"] = old["agg"].map({"base": "fast", "mean": "mean"})
    m = old.merge(S, on=["kernel", "agg", "size"], suffixes=("_1111", ""))
    chk = m[["kernel", "agg", "size", "nb_pred_1111", "nb_pred", "nb_obs_1111", "nb_obs", "perf_1111", "perf"]].copy()
    chk["perf_diff"] = chk.perf - chk.perf_1111
    chk.to_csv(DATA / "b_check_1111.csv", index=False, float_format="%.6g")
    print("11-11 との最大差：perf", chk.perf_diff.abs().max(), " nb_pred 不一致", (chk.nb_pred != chk.nb_pred_1111).sum(),
          " nb_obs 不一致", (chk.nb_obs != chk.nb_obs_1111).sum())

    grid = [32, 48, 64, 96, 128, 160, 192, 256, 320, 384, 448, 512]
    t = c[c.nb.isin(grid)]
    out = []
    for agg in AGGS:
        w = (t[agg] / t["pred_ib=nb/8"]).to_frame("r").assign(size=t["size"], nb=t.nb).pivot(index="size", columns="nb", values="r")
        w.insert(0, "agg", agg)
        out.append(w.reset_index())
    R = pd.concat(out)
    R.to_csv(DATA / "b_ratio_by_nb.csv", index=False, float_format="%.4f")
    print(R.round(3).to_string(index=False))

    plt = setup_plot()
    fig, axs = plt.subplots(1, 4, figsize=(15, 3.8), sharey=True)
    sty = {"fast": ("#1f77b4", "-", "速い水準（base）"), "slow": ("#d62728", "-", "遅い水準だけ（ex > 6 ms）"),
           "mean": ("#2ca02c", "-", "5回の平均"), "slow_dt": ("#d62728", ":", "感度：base + ΔT")}
    A, beta = params["ib=nb/8"]
    for ax, (s, g) in zip(axs, c.groupby("size")):
        g = g.sort_values("nb")
        for agg, (col, ls, lab) in sty.items():
            ax.plot(g.nb, g[agg] / g[agg].max(), ls, color=col, lw=1.1, label=lab)
        ax.plot(g.nb, g["pred_ib=nb/8"] / g["pred_ib=nb/8"].max(), "--", color="k", lw=1, label="予測（最大で割る）")
        ip = int(np.argmax(g["pred_ib=nb/8"].to_numpy()))
        ax.axvline(g.nb.iloc[ip], color="k", lw=0.5)
        ax.set_title(f"size {s}（予測の nb = {g.nb.iloc[ip]}）")
        ax.set_xlabel("nb")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("GFlops / 各曲線の最大")
    axs[0].legend(fontsize=7)
    fig.suptitle(f"不老・弐 QR（p = 192）：集計ごとの曲線と当てはめなしのモデル（A = {A:.1f}、β = {beta:.0f}）", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig_b_ratio.png")


if __name__ == "__main__":
    main()
