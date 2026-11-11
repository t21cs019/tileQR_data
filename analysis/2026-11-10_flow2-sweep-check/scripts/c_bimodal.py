"""
C. 2つの水準：二峰性の検定、割合、ΔT、独立性、ほかのデータとの照合。

出力:
  data/c1_mixture.csv        size ごとの、超過時間 ex の 1 山 / 2 山の当てはめ（BIC、Ashman の D、谷/山の比）
  data/c1_pairdiff.csv       同じ点の 5 回から作った 10 組の時間差の分布（base を使わない確認）
  data/c2_fraction.csv       遅い水準の割合と ΔT（size × nb の帯、ib/nb、反復、実行順）
  data/c3_independence.csv   点ごとの「遅い回数」の分布と二項分布、反復間の相関、実行順の隣どうしの相関
  data/c4_other.csv          r0、固定の検査、A/B テストの各実行を、スイープの速い水準と比べたもの
  data/c4_other_machines.csv 研究室の EPYC 7543 と AOBA-B（固定なし）の同じ解析
  fig_c_other_machines.png   その ex のヒストグラム
  fig_c_excess_hist.png      ex のヒストグラム（size ごと）
  fig_c_pairdiff.png         組の時間差のヒストグラム
  fig_c_fraction.png         遅い水準の割合と ΔT（nb ごと）
  fig_c_levels.png           size 1024・2048 の ib = 32 の全実行の時間と速い水準
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom, chi2, norm

from common import (DATA, NB_CLASS, OUT, P, REPS, SIZES, SLOW_MS, add_baseline, base, base_r0, flops_dgeqrf,
                    load_all, nb_band, parse_affinity, read_csv, setup_plot)

REPO = Path(__file__).resolve().parents[3]
AB_DIR = Path.home() / "Download/flow/flow_bind-ab_20261031_082853"
LO, HI = -8.0, 30.0      # 混合分布を当てはめる ex の範囲 [ms]


def em2(x, iters=500):
    """2 成分の正規混合を EM で当てはめる。返り値 (w, mu1, sd1, mu2, sd2, loglik)。"""
    mu = np.array([np.percentile(x, 15), np.percentile(x, 75)])
    sd = np.array([x.std() / 3, x.std() / 3])
    w = np.array([0.4, 0.6])
    for _ in range(iters):
        pdf = np.stack([w[k] * norm.pdf(x, mu[k], sd[k]) for k in (0, 1)]) + 1e-300
        r = pdf / pdf.sum(axis=0)
        n = r.sum(axis=1)
        w = n / n.sum()
        mu = (r * x).sum(axis=1) / n
        sd = np.maximum(np.sqrt((r * (x - mu[:, None]) ** 2).sum(axis=1) / n), 0.05)
    ll = np.log(np.stack([w[k] * norm.pdf(x, mu[k], sd[k]) for k in (0, 1)]).sum(axis=0)).sum()
    if mu[0] > mu[1]:
        w, mu, sd = w[::-1], mu[::-1], sd[::-1]
    return w[1], mu[0], sd[0], mu[1], sd[1], ll


def mixture_row(label, ex):
    x = ex[(ex > LO) & (ex < HI)]
    n = len(x)
    ll1 = norm.logpdf(x, x.mean(), x.std()).sum()
    w, m1, s1, m2, s2, ll2 = em2(x)
    bic1, bic2 = -2 * ll1 + 2 * np.log(n), -2 * ll2 + 5 * np.log(n)
    D = np.sqrt(2) * abs(m2 - m1) / np.sqrt(s1**2 + s2**2)
    # ヒストグラム（1 ms 幅）で、2 つの山の高さと、その間の谷の高さ
    h, e = np.histogram(x, bins=np.arange(LO, HI + 1, 1.0))
    c = (e[:-1] + e[1:]) / 2
    sel1, sel2 = h[(c > m1 - 3) & (c < m1 + 3)], h[(c > m2 - 3) & (c < m2 + 3)]
    p1 = sel1.max() if len(sel1) else np.nan
    p2 = sel2.max() if len(sel2) else np.nan
    between = h[(c > m1 + 1) & (c < m2 - 1)]
    valley = between.min() if len(between) else np.nan
    return dict(data=label, n=n, in_window=n / len(ex), dBIC=bic1 - bic2, w_slow=w, mu_fast=m1, sd_fast=s1,
                mu_slow=m2, sd_slow=s2, dT=m2 - m1, ashman_D=D, valley_over_lower_peak=valley / min(p1, p2))


def pair_diffs(w: pd.DataFrame) -> np.ndarray:
    """w：行 = 点、列 = 反復。全点の |t_i − t_j|（10 組）。"""
    a = w.values
    return np.concatenate([np.abs(a[:, i] - a[:, j]) for i, j in combinations(range(a.shape[1]), 2)])


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    plt = setup_plot()
    d = add_baseline(load_all())
    d["cls"] = d.nb >= d["size"].map(NB_CLASS)          # 水準を判定する範囲
    d["slow"] = d.ex > SLOW_MS
    d["band"] = nb_band(d.nb)
    c = d[d.cls]

    # ---------------- C1 二峰性 ----------------
    rows = [mixture_row(f"size {s}（nb ≥ {NB_CLASS[s]}）", c[c["size"] == s].ex.values) for s in SIZES]
    c1 = pd.DataFrame(rows)
    c1.to_csv(DATA / "c1_mixture.csv", index=False, float_format="%.4g")
    print("== C1 ex = 時間 − 速い水準 の混合分布（−8〜30 ms の範囲）==")
    print(c1.to_string(index=False, float_format="%.3g"))

    # 速い水準の実行だけで見たノイズの幅（相対値）
    f = c[~c.slow & (c.ex > LO)]
    noise = f.groupby("size").apply(lambda x: pd.Series({
        "base_med_ms": x.base.median(), "sd_ms(MAD)": 1.4826 * (x.ex - x.ex.median()).abs().median(),
        "rel_%": 100 * 1.4826 * ((x.ex - x.ex.median()).abs() / x.base).median()}), include_groups=False)
    print("\n速い水準に入った実行のばらつき（MAD から求めた標準偏差）")
    print(noise.round(2))

    # base を使わない確認：同じ点の 5 回から作る 10 組の差
    fig, axes = plt.subplots(1, 4, figsize=(17, 3.6))
    prow = []
    for ax, s in zip(axes, SIZES):
        w = c[c["size"] == s].pivot_table(index=["nb", "ib"], columns="rep", values="t_ms")
        pdiff = pair_diffs(w)
        h, e = np.histogram(pdiff, bins=np.arange(0, 41, 1.0))
        ax.bar(e[:-1], h, width=1.0, align="edge", color="#4477aa")
        ax.set_title(f"size {s}（nb ≥ {NB_CLASS[s]}、{len(pdiff)} 組）")
        ax.set_xlabel("同じ点の 2 回の時間差 |t_i − t_j| [ms]")
        near0 = (pdiff < 5).mean()
        nearD = ((pdiff >= 9) & (pdiff < 20)).mean()
        mid = ((pdiff >= 5) & (pdiff < 9)).mean()
        prow.append(dict(size=s, pairs=len(pdiff), lt5ms=near0, _5to9ms=mid, _9to20ms=nearD, ge20ms=(pdiff >= 20).mean(),
                         peak_ms=e[np.argmax(h[9:]) + 9] + 0.5, peak_count=h[9:].max(), valley_count=h[3:9].min()))
    axes[0].set_ylabel("組の数")
    fig.suptitle("C1. 同じ (nb, ib) の 2 回の時間差（速い水準の見積もりを使わない確認）", y=1.03)
    fig.savefig(OUT / "fig_c_pairdiff.png", bbox_inches="tight")
    c1p = pd.DataFrame(prow)
    c1p.to_csv(DATA / "c1_pairdiff.csv", index=False, float_format="%.4g")
    print("\n同じ点の 2 回の時間差の分布（割合）。2 水準が独立に入るなら「差が ΔT 付近」の割合は 2q(1−q)")
    print(c1p.to_string(index=False, float_format="%.3g"))

    fig, axes = plt.subplots(1, 4, figsize=(17, 3.6))
    for ax, s, r in zip(axes, SIZES, rows):
        x = c[c["size"] == s].ex
        ax.hist(x, bins=np.arange(-10, 40.5, 0.5), color="#4477aa")
        xs = np.linspace(-10, 40, 400)
        n = ((x > LO) & (x < HI)).sum() * 0.5
        ax.plot(xs, n * ((1 - r["w_slow"]) * norm.pdf(xs, r["mu_fast"], r["sd_fast"])
                         + r["w_slow"] * norm.pdf(xs, r["mu_slow"], r["sd_slow"])), "r-", lw=1)
        ax.axvline(SLOW_MS, color="k", ls=":", lw=0.8)
        ax.set_title(f"size {s}（nb ≥ {NB_CLASS[s]}）", fontsize=10)
        ax.set_xlabel("ex = 時間 − 速い水準 [ms]")
    axes[0].set_ylabel("実行の数")
    fig.suptitle("C1. 速い水準からの超過時間（赤 = 2 山の正規混合、点線 = 判定のしきい値 6 ms。"
                 "base は 3×3 近傍の速い実行の中央値）", y=1.03)
    fig.savefig(OUT / "fig_c_excess_hist.png", bbox_inches="tight")

    # ---------------- C2 割合と ΔT ----------------
    def frac_tab(key, name):
        t = c.groupby(["size", key], observed=True).agg(
            runs=("slow", "size"), slow_frac=("slow", "mean"),
            dT_ms=("ex", lambda v: v[(v > SLOW_MS) & (v < HI)].median()),
            base_ms=("base", "median")).reset_index().rename(columns={key: "level"})
        t.insert(1, "by", name)
        return t

    c["ibr"] = pd.cut(c.ib / c.nb, [0, 0.125, 0.25, 0.375, 0.5]).astype(str)
    c["decile"] = c.groupby(["size", "rep"]).seq.transform(lambda v: pd.qcut(v, 10, labels=False))
    c["repnode"] = "r" + c.rep.astype(str) + " " + c.node
    c["all"] = "全体"
    c2 = pd.concat([frac_tab("all", "全体"), frac_tab("band", "nb"), frac_tab("ibr", "ib/nb"),
                    frac_tab("repnode", "反復（ノード）"), frac_tab("decile", "実行順の10等分")], ignore_index=True)
    c2.to_csv(DATA / "c2_fraction.csv", index=False, float_format="%.4g")
    print("\n== C2 遅い水準（ex > 6 ms）の割合と ΔT（遅い側の ex の中央値）==")
    for by in c2.by.unique():
        t = c2[c2.by == by]
        print(f"-- {by} --")
        print(pd.concat([t.pivot(index="level", columns="size", values="slow_frac").round(3),
                         t.pivot(index="level", columns="size", values="dT_ms").round(1).add_prefix("dT_")],
                        axis=1).to_string())

    # nb ごとの図
    fig, axes = plt.subplots(1, 2, figsize=(14, 3.8))
    for s in SIZES[:3]:
        x = c[c["size"] == s]
        g = x.groupby("nb")
        axes[0].plot(g.slow.mean(), lw=1, label=f"size {s}")
        axes[1].plot(g.ex.apply(lambda v: v[(v > SLOW_MS) & (v < HI)].median()), lw=1, label=f"size {s}")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("遅い水準の割合")
    axes[1].set_ylim(0, 25)
    axes[1].set_ylabel("ΔT [ms]（遅い側の ex の中央値）")
    for ax in axes:
        ax.set_xlabel("nb")
        ax.legend()
    fig.suptitle("C2. 遅い水準の割合と ΔT は nb によらない（nb ごとに ib と 5 回をまとめた）", y=1.02)
    fig.savefig(OUT / "fig_c_fraction.png", bbox_inches="tight")

    # size 1024・2048 の ib = 32 の全実行
    fig, axes = plt.subplots(1, 2, figsize=(16, 4.2))
    for ax, s, top in zip(axes, (1024, 2048), (80, 140)):
        x = d[(d["size"] == s) & (d.nb >= 96) & (d.ib == 32)]
        ax.scatter(x.nb, x.t_ms, s=7, c=np.where(x.ex > SLOW_MS, "#cc3311", "#0077bb"), linewidths=0)
        b = x.drop_duplicates("nb").sort_values("nb")
        ax.plot(b.nb, b.base, "k-", lw=0.8, label="速い水準 base")
        ax.plot(b.nb, b.base + SLOW_MS, "k:", lw=0.8, label="しきい値 base + 6 ms")
        ax.set_ylim(10, top)
        ax.set_xlabel("nb")
        ax.set_title(f"size {s}・ib = 32 の全実行（各 nb に 5 回）。青 = 速い水準、赤 = 遅い水準")
        ax.legend()
    axes[0].set_ylabel("時間 [ms]")
    fig.savefig(OUT / "fig_c_levels.png", bbox_inches="tight")

    # ---------------- C3 独立性 ----------------
    rows = []
    print("\n== C3 同じ点の 5 回のうち、遅い水準に入った回数 k の分布 ==")
    for s in SIZES[:3]:
        x = c[c["size"] == s]
        w = x.pivot_table(index=["nb", "ib"], columns="rep", values="slow").astype(int)
        k = w.sum(axis=1)
        q = x.slow.mean()
        obs = k.value_counts().reindex(range(6), fill_value=0).values
        exp = binom.pmf(range(6), 5, q) * len(k)
        chi = ((obs - exp) ** 2 / exp).sum()
        corr = w.corr().values[np.triu_indices(5, 1)]
        # 実行順の隣どうし（同じジョブの中）
        lag = [np.corrcoef(v.values[:-1], v.values[1:])[0, 1]
               for _, v in x.sort_values("seq").groupby("rep").slow]
        # 条件で決まるなら 1、独立なら 0 になる指標：点の間の分散の超過
        icc = (k.var() - 5 * q * (1 - q)) / (5 * q * (1 - q) * 4)
        rows.append(dict(size=s, points=len(k), q=q, **{f"k{i}_obs": obs[i] for i in range(6)},
                         **{f"k{i}_binom": exp[i] for i in range(6)}, chi2=chi, p_value=chi2.sf(chi, 4),
                         rep_corr_mean=corr.mean(), rep_corr_min=corr.min(), rep_corr_max=corr.max(),
                         icc=icc, lag1_corr_mean=np.mean(lag)))
        print(f"size {s}: q = {q:.3f}  観測 {obs.tolist()}  二項分布 {exp.round(0).astype(int).tolist()}  "
              f"反復間の相関 {corr.mean():.3f}（{corr.min():.3f}〜{corr.max():.3f}）  ICC {icc:.3f}  "
              f"実行順の隣どうしの相関 {np.mean(lag):.3f}")
    c3 = pd.DataFrame(rows)
    c3.to_csv(DATA / "c3_independence.csv", index=False, float_format="%.4g")

    # ---------------- C4 ほかのデータ ----------------
    bmap = d.drop_duplicates(["size", "nb", "ib"]).set_index(["size", "nb", "ib"]).base
    rows = []
    # r0（size 1024、9 点）
    r0 = read_csv(Path(str(base_r0()) + ".csv"))
    for _, x in r0.iterrows():
        t = flops_dgeqrf(1024) / x.GFlops / 1e6
        rows.append(dict(src="r0（t1-debug、11-10）", cond="close", size=1024, nb=x.nb, ib=x.ib, GFlops=x.GFlops,
                         t_ms=t, base_ms=bmap[(1024, x.nb, x.ib)]))
    # 固定の検査（size 2048・nb 128・ib 32、各ジョブで sweep の直前に 1 回）
    for s in SIZES:
        for r in REPS:
            a = parse_affinity(Path(str(base(s, r)) + "_affinity.txt"))
            first = "ジョブで最初" if s != 2048 else "size 1024 のあと"
            rows.append(dict(src=f"固定の検査（本番 size{s} r{r}、{first}）", cond="close", size=2048, nb=128, ib=32,
                             GFlops=a["check_gflops"], t_ms=a["check_time_s"] * 1e3, base_ms=bmap[(2048, 128, 32)]))
    a = parse_affinity(Path(str(base_r0()) + "_affinity.txt"))
    rows.append(dict(src="固定の検査（r0、t1-debug、ジョブで最初）", cond="close", size=2048, nb=128, ib=32,
                     GFlops=a["check_gflops"], t_ms=a["check_time_s"] * 1e3, base_ms=bmap[(2048, 128, 32)]))
    for cond in ("bind-close", "bind-none"):
        a = parse_affinity(AB_DIR / f"affinity_{cond}.txt")
        rows.append(dict(src="固定の検査（A/B 10-31、t1-debug。none が先）", cond=cond.replace("bind-", ""), size=2048,
                         nb=128, ib=32, GFlops=a["check_gflops"], t_ms=a["check_time_s"] * 1e3,
                         base_ms=bmap[(2048, 128, 32)]))
    # A/B テスト
    for cond in ("bind-close", "bind-close-intlv", "bind-none"):
        for s in (2048, 4096, 8192):
            x = pd.read_csv(AB_DIR / f"{cond}_size{s}.csv")
            for _, y in x.iterrows():
                rows.append(dict(src="A/B（10-31、t1250）", cond=cond.replace("bind-", ""), size=s, nb=y.nb, ib=y.ib,
                                 GFlops=y.GFlops, t_ms=flops_dgeqrf(s) / y.GFlops / 1e6,
                                 base_ms=bmap[(s, y.nb, y.ib)]))
    c4 = pd.DataFrame(rows)
    c4["ex_ms"] = c4.t_ms - c4.base_ms
    c4.to_csv(DATA / "c4_other.csv", index=False, float_format="%.5g")
    print("\n== C4 r0 の 9 点（スイープの速い水準との差）==")
    print(c4[c4.src.str.startswith("r0")][["nb", "ib", "GFlops", "t_ms", "base_ms", "ex_ms"]].round(1).to_string(index=False))
    print("\n固定の検査で流れた size 2048・nb 128・ib 32（スイープの同じ点の速い水準 "
          f"{bmap[(2048, 128, 32)]:.1f} ms）")
    chk = c4[c4.src.str.startswith("固定の検査")]
    print(chk[["src", "cond", "GFlops", "t_ms", "ex_ms"]].round(1).to_string(index=False))
    sw = d[(d["size"] == 2048) & (d.nb == 128) & (d.ib == 32)]
    print("スイープの同じ点の 5 回 [ms]:", sw.t_ms.round(1).tolist())
    ab = c4[c4.src.str.startswith("A/B")]
    print("\nA/B テスト：スイープの速い水準からの超過 ex [ms]（5 回を小さい順に）")
    t = ab.groupby(["size", "nb", "cond"]).agg(base_ms=("base_ms", "first"),
                                               ex=("ex_ms", lambda v: " ".join(f"{e:.0f}" for e in sorted(v))),
                                               ex_med=("ex_ms", "median")).reset_index()
    print(t.pivot(index=["size", "nb", "base_ms"], columns="cond", values="ex").to_string())
    print("\nA/B テスト：ex の中央値 [ms]")
    print(t.pivot(index=["size", "nb"], columns="cond", values="ex_med").round(1).to_string())
    ab2 = ab[ab.nb >= 128]
    print("\nA/B テスト（nb ≥ 128）：ex ≤ 6 ms（速い水準）に入った実行の割合")
    print(ab2.assign(fast=ab2.ex_ms <= SLOW_MS).pivot_table(index="size", columns="cond", values="fast",
                                                         aggfunc=["mean", "size"]).round(2).to_string())

    # ほかの機種（固定なし）：研究室の EPYC 7543（p = 32、libiomp5）、AOBA-B（p = 64・128、libgomp）
    q = pd.read_parquet(REPO / "derived/qr_sweep.parquet")
    q = q[q["size"].isin([1024, 2048]) & (q.GFlops > 0)]
    rows = []
    cfgs = [("epyc_s1_smt-off", "EPYC 7543 p=32（10-27）", "20261027"), ("aoba-b_s1_smt-off", "AOBA-B p=64", ""),
            ("aoba-b_s2_smt-off", "AOBA-B 2ソケット p=128", "")]
    fig, axes = plt.subplots(2, 3, figsize=(15, 6.4))
    for col, (cfg, label, pat) in enumerate(cfgs):
        e = q[(q.config == cfg) & q.source_file.str.contains(pat)].copy()
        e["rep"] = e.groupby("size").source_file.transform(lambda v: v.rank(method="dense")).astype(int)
        e = e.drop_duplicates(["size", "nb", "ib", "rep"])
        e["t_ms"] = flops_dgeqrf(e["size"]) / e.GFlops / 1e6
        e = add_baseline(e)
        for rowi, s in enumerate((1024, 2048)):
            x = e[(e["size"] == s) & (e.nb >= 96)]
            w = x.pivot_table(index=["nb", "ib"], columns="rep", values="t_ms").dropna()
            pdiff = pair_diffs(w)
            rows.append(dict(data=f"{label} size {s}（nb ≥ 96）", runs=x.rep.nunique(), n=len(x),
                             base_med_ms=x.base.median(), pair_lt2ms=(pdiff < 2).mean(),
                             pair_2to9ms=((pdiff >= 2) & (pdiff < 9)).mean(),
                             pair_9to20ms=((pdiff >= 9) & (pdiff < 20)).mean(), pair_ge20ms=(pdiff >= 20).mean(),
                             ex_gt6ms=(x.ex > SLOW_MS).mean(), ex_p50=x.ex.median(), ex_p90=x.ex.quantile(0.9),
                             ex_p99=x.ex.quantile(0.99)))
            ax = axes[rowi, col]
            ax.hist(x.ex, bins=np.arange(-5, 40.5, 0.5), color="#4477aa")
            ax.set_title(f"{label} size {s}（nb ≥ 96、{x.rep.nunique()} 回）", fontsize=10)
            ax.set_xlabel("ex = 時間 − 速い水準 [ms]")
    fig.tight_layout()
    fig.savefig(OUT / "fig_c_other_machines.png", bbox_inches="tight")
    c4e = pd.DataFrame(rows)
    c4e.to_csv(DATA / "c4_other_machines.csv", index=False, float_format="%.4g")
    print("\n== C4 ほかの機種（固定なし）の同じ解析 ==")
    print(c4e.to_string(index=False, float_format="%.3g"))

if __name__ == "__main__":
    main()
