"""2.・3. β と A：ib = nb/8 の断面と MaxIB、5回の平均と回ごと、不老・弐と EPYC 7543。ギザギザと nb の範囲への感度。
出力 data/b_fits.csv, b_curves.csv, b_sensitivity.csv, fig_kernel_fit.png"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python -I でも common を読めるようにする

import numpy as np
import pandas as pd

from common import DATA, MRE_MAX, OUT, curve_maxib, curve_slice, fit, load_epyc, load_flow2, mean_grid, setup_plot  # noqa: E402

pd.set_option("display.width", 220)
MACH = {"flow2 (EPYC 9965)": load_flow2, "EPYC 7543": load_epyc}
PROC = {"ib=nb/8": curve_slice, "MaxIB": curve_maxib}


def main():
    fits, curves, sens = [], [], []
    keep = {}
    for mach, loader in MACH.items():
        d = loader()
        grids = {"mean5": mean_grid(d), "median5": d.groupby(["nb", "ib"], as_index=False)["GFlops"].median()}
        grids.update({f"r{r}": g[["nb", "ib", "GFlops"]].reset_index(drop=True) for r, g in d.groupby("rep")})
        for proc, fn in PROC.items():
            for tgt, a in grids.items():
                c = fn(a)
                f = fit(c)
                fits.append(dict(machine=mach, proc=proc, target=tgt, beta=f["beta"], A=f["A"], mre=f["mre"],
                                 max_abs=f["max_abs"], n=f["n"], used=f["mre"] <= MRE_MAX))
                if tgt == "mean5":
                    keep[(mach, proc)] = (c, f)
                    cc = c.copy()
                    cc["machine"], cc["proc"] = mach, proc
                    cc["fit"] = f["A"] * cc.nb / (cc.nb + f["beta"])
                    cc["rel"] = cc.fit / cc.GFlops - 1
                    curves.append(cc)
                    # 感度：nb の範囲、8 の倍数とそれ以外、16・32 の倍数
                    sub = {"全部 (nb 64-512)": c, "nb 64-256": c[c.nb <= 256], "nb 128-512": c[c.nb >= 128],
                           "nb 96-512": c[c.nb >= 96],
                           "nb%8==0": c[c.nb % 8 == 0], "nb%8==4": c[c.nb % 8 == 4], "nb%32==0": c[c.nb % 32 == 0]}
                    for k, s in sub.items():
                        g = fit(s)
                        sens.append(dict(machine=mach, proc=proc, subset=k, beta=g["beta"], A=g["A"], mre=g["mre"], n=g["n"]))
    F = pd.DataFrame(fits)
    F.to_csv(DATA / "b_fits.csv", index=False, float_format="%.5g")
    pd.concat(curves).to_csv(DATA / "b_curves.csv", index=False, float_format="%.5g")
    S = pd.DataFrame(sens)
    S.to_csv(DATA / "b_sensitivity.csv", index=False, float_format="%.5g")

    for (mach, proc), g in F.groupby(["machine", "proc"], sort=False):
        m = g[g.target == "mean5"].iloc[0]
        md = g[g.target == "median5"].iloc[0]
        r = g[g.target.str.startswith("r")]
        print(f"{mach:18s} {proc:8s} 平均: β {m.beta:6.1f} A {m.A:6.2f} MRE {100 * m.mre:.2f}% 最大 {100 * m.max_abs:.1f}% n {m.n}"
              f" | 中央値: β {md.beta:6.1f} A {md.A:6.2f}"
              f" | 回ごと β {r.beta.min():.1f}〜{r.beta.max():.1f} A {r.A.min():.2f}〜{r.A.max():.2f} MRE {100 * r.mre.min():.2f}〜{100 * r.mre.max():.2f}%")
    print(S.round(3).to_string(index=False))

    # ギザギザ：断面の曲線で、両隣の平均（nb ± 4）からの相対差を nb mod 8・mod 16・mod 32 で分ける
    for (mach, proc), (c, f) in keep.items():
        c = c.sort_values("nb").reset_index(drop=True)
        y = c.GFlops.to_numpy()
        loc = np.full(len(y), np.nan)
        loc[1:-1] = y[1:-1] / ((y[:-2] + y[2:]) / 2) - 1
        c["loc"] = loc
        c["res"] = -f["rel"] / (1 + f["rel"])          # 実測/当てはめ − 1
        k = c.dropna()
        cls = np.where(k.nb % 32 == 0, "32の倍数", np.where(k.nb % 16 == 0, "16の倍数", np.where(k.nb % 8 == 0, "8の倍数", "それ以外")))
        t = k.groupby(cls)["loc"].agg(["mean", "std", "size"])
        print(f"[{mach} {proc}] 両隣の平均からの差(%) :",
              "  ".join(f"{i} {100 * r['mean']:+.2f}±{100 * r['std']:.2f} (n={int(r['size'])})" for i, r in t.iterrows()))
        band = pd.cut(c.nb, [63, 95, 127, 191, 255, 383, 512])
        print("   実測/当てはめ−1 (%) の nb 帯ごとの平均:",
              "  ".join(f"{str(i)} {100 * v:+.2f}" for i, v in c.groupby(band, observed=True).res.mean().items()))

    # 図：断面と MaxIB の曲線と当てはめ（上）、残差（下）
    plt = setup_plot()
    fig, axs = plt.subplots(2, 2, figsize=(11, 7), sharex=True, gridspec_kw=dict(height_ratios=[2, 1]))
    col = {"ib=nb/8": "#1f77b4", "MaxIB": "#d95f02"}
    for j, mach in enumerate(MACH):
        for proc in PROC:
            c, f = keep[(mach, proc)]
            nb = c.nb.to_numpy(float)
            axs[0, j].plot(nb, c.GFlops, ".", ms=4, color=col[proc], label=f"{proc} 実測（5回の平均）")
            axs[0, j].plot(nb, f["A"] * nb / (nb + f["beta"]), "-", lw=1, color=col[proc],
                           label=f"当てはめ β={f['beta']:.0f}, A={f['A']:.1f}, MRE {100 * f['mre']:.1f}%")
            axs[1, j].plot(nb, 100 * (c.GFlops / (f["A"] * nb / (nb + f["beta"])) - 1), ".-", ms=3, lw=0.6, color=col[proc])
        axs[0, j].set_title(f"{mach}：DTSMQR 1コア、size 4096")
        axs[0, j].set_ylabel("GFlops")
        axs[0, j].legend(fontsize=8)
        axs[1, j].axhline(0, color="k", lw=0.5)
        axs[1, j].set_ylabel("実測/当てはめ − 1 [%]")
        axs[1, j].set_xlabel("nb")
        for a in axs[:, j]:
            a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_kernel_fit.png")


if __name__ == "__main__":
    main()
