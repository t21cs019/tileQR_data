#!/usr/bin/env python3
"""
Kurzak (2008) のモデルと本研究のモデルの照合。数値をすべて標準出力に出す。

**derived/ は書き換えない。** これは検証用のレポート生成であって、
パイプラインの一部ではない。ingest.py の出力に依存するだけ。
結果の散文は tileQR_research/notes/kurzak_verification.md にある。

タスク1 … SSRFB 実測 beta と、Kurzak 4パラメータからの逆算 beta の突き合わせ
タスク2 … ib=nb/8 に畳んだときに失う精度
タスク3 … 並列項のコア数指数 mu
タスク4 … 崖位置のサイズ指数 delta

使い方:
    python scripts/kurzak_verify.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, kurzak  # noqa: E402

pd.set_option("display.width", 250)

# SSRFB を threads=1 で測れている機種。i5-7400 だけ threads=4 で汚染。
CLEAN_SSRFB = ("epyc", "i5-8500", "ryzen5-7400f")


def hr(title):
    print("\n" + "=" * 110)
    print(title)
    print("=" * 110)


def task12():
    hr("タスク1・2  SSRFB カーネル")
    s = io.load_ssrfb()
    s = s.groupby(["node", "threads", "size", "nb", "ib"], as_index=False)["GFlops"].mean()
    rows = []
    for (node, th, size), g in s.groupby(["node", "threads", "size"]):
        g = g.sort_values(["nb", "ib"])
        # ib/nb が 1/16 を下回る隅は PLASMA が実際には使わない領域。
        # ここを入れるとフィットが隅の外れ値に引っ張られる。
        prac = g[(g["nb"] >= 64) & (g["ib"] >= g["nb"] / 16)]
        nb = prac["nb"].to_numpy(float)
        ib = prac["ib"].to_numpy(float)
        y = prac["GFlops"].to_numpy()
        p = kurzak.fit_kernel(nb, ib, y)
        k_rel = kurzak.kurzak_kernel(p, nb, ib) / y - 1.0

        sl = kurzak.ib_rule_slice(g, rho=8.0)
        snb = sl["nb"].to_numpy(float)
        sy = sl["GFlops"].to_numpy()
        amp, beta = kurzak.fit_E(snb, sy)
        e_rel = amp * snb / (snb + beta) / sy - 1.0
        p_sl = kurzak.fit_kernel(snb, sl["ib"].to_numpy(float), sy)
        k_sl = kurzak.kurzak_kernel(p_sl, snb, sl["ib"].to_numpy(float)) / sy - 1.0

        # ib=nb/8 という規則そのものの代償（同じ nb で最良 ib と比べた損失）
        best = g.loc[g.groupby("nb")["GFlops"].idxmax()][["nb", "ib", "GFlops"]]
        best.columns = ["nb", "ib_best", "G_best"]
        cmp_ = sl.merge(best, on="nb")
        loss = (1 - cmp_["GFlops"] / cmp_["G_best"]) * 100
        at_peak = cmp_.loc[cmp_["G_best"].idxmax()]

        rows.append(dict(
            node=node, threads=th, size=size, n=len(prac),
            a=p[0], b=p[1], c=p[2], d=p[3],
            beta_inv=kurzak.beta_from_kurzak(p, 8.0),
            beta_meas=beta,
            ratio=kurzak.beta_from_kurzak(p, 8.0) / beta,
            K_rmse=np.sqrt(np.mean(k_rel**2)) * 100,
            K_mae=np.mean(np.abs(k_rel)) * 100,
            E_rmse=np.sqrt(np.mean(e_rel**2)) * 100,
            E_mae=np.mean(np.abs(e_rel)) * 100,
            Kslice_rmse=np.sqrt(np.mean(k_sl**2)) * 100,
            Kslice_mae=np.mean(np.abs(k_sl)) * 100,
            ibfix_mean=loss.mean(),
            ibfix_at_peak=float(1 - at_peak["GFlops"] / at_peak["G_best"]) * 100,
            nb_peak=float(at_peak["nb"]),
            ib_best_at_peak=float(at_peak["ib_best"]),
        ))
    df = pd.DataFrame(rows)
    fmt = lambda x: f"{x:.4g}"  # noqa: E731
    print("\n[タスク1] Kurzak 4パラメータ → beta=(8c+d)/(1+b/8) と、E 形の直接フィット beta")
    print(df[["node", "threads", "size", "n", "a", "b", "c", "d",
              "beta_inv", "beta_meas", "ratio"]].to_string(index=False, float_format=fmt))
    ok = df[df["node"].isin(CLEAN_SSRFB)]
    print(f"\n  汚染なし3機種のみ: beta_inv/beta_meas = "
          f"{ok['ratio'].mean():.3f} (範囲 {ok['ratio'].min():.3f}〜{ok['ratio'].max():.3f})")
    print("\n[タスク2] 相対誤差 %  K=4パラメータ(格子全体) / E=1パラメータ+振幅(ib=nb/8断面) / "
          "Kslice=4パラメータを同じ断面で引き直し")
    print(df[["node", "threads", "size", "K_rmse", "K_mae", "E_rmse", "E_mae",
              "Kslice_rmse", "Kslice_mae"]].to_string(index=False, float_format=fmt))
    print("\n[タスク2] ib=nb/8 という規則そのものの代償（同じ nb での最良 ib に対する損失 %）")
    print(df[["node", "threads", "size", "ibfix_mean", "nb_peak", "ib_best_at_peak",
              "ibfix_at_peak"]].to_string(index=False, float_format=fmt))

    # beta は ib 規則の分母 rho に依存する。実測の最適比は nb/5 前後。
    opt = io.load_optima()
    rho_emp = float((opt["nb_opt"] / opt["ib_opt"]).median())
    print(f"\n  実測最適の nb_opt/ib_opt 中央値 = {rho_emp:.2f}（規則の 8 ではない）")
    print("  rho を変えたときの逆算 beta:")
    for _, r in df[df["node"].isin(CLEAN_SSRFB)].iterrows():
        p = (r["a"], r["b"], r["c"], r["d"])
        vals = "  ".join(f"rho={rho}: {kurzak.beta_from_kurzak(p, rho):.0f}"
                         for rho in (4, 5, 6, 8, 12))
        print(f"    {r['node']:14s} size={r['size']:<6d} {vals}")
    return df


def task34():
    df = kurzak.load_qr_curves()
    no_aoba = df[~df["config"].str.startswith("aoba")]
    hr("タスク3・4  並列項の指数")
    print(f"点数 {df['g'].nunique()}（config x size）、曲線上の点 {len(df)}")

    variants = {
        "自由（本研究）": dict(),
        "Kurzak P^1.0 (mu=1)": dict(mu_fixed=1.0),
        "Kurzak タイル比 (delta=1)": dict(fixed=dict(delta=1.0)),
        "Kurzak 両方": dict(mu_fixed=1.0, fixed=dict(delta=1.0)),
        "Kurzak そのまま (k=2.5)": dict(mu_fixed=1.0, fixed=dict(delta=1.0, k0=2.5)),
    }
    print("\n[指数] kappa=nb, mu=P, sigma=size")
    print(f"{'変種':26s} {'kappa':>7s} {'mu':>7s} {'sigma':>7s} {'m':>7s} {'delta':>7s} {'rms':>9s}")
    for name, kw in variants.items():
        r = kurzak.fit(df, **kw)
        print(f"{name:26s} {r['kappa']:7.3f} {r['mu']:7.3f} {r['sigma']:7.3f} "
              f"{r['m']:7.3f} {r['delta']:7.3f} {r['rms']:9.5f}")
    print(f"{'Kurzak (発表値)':26s} {2.5:7.3f} {1.0:7.3f} {2.5:7.3f} {0.4:7.3f} {1.0:7.3f}")

    print("\n[LOOCV] (config,size) を1点抜き、残りで指数を引き直してゼロショット予測")
    print(f"{'変種':26s} {'性能比平均':>10s} {'最悪':>8s} {'nbMRE%':>8s} "
          f"{'95%帯命中':>9s} {'recall':>8s} {'最悪':>8s} {'幅比':>7s}")
    for name, kw in variants.items():
        cv = kurzak.loocv(df, **kw)
        print(f"{name:26s} {cv['perf'].mean():10.4f} {cv['perf'].min():8.4f} "
              f"{cv['nb_relerr'].mean()*100:8.1f} {cv['hit'].mean():9.3f} "
              f"{cv['recall'].mean():8.4f} {cv['recall'].min():8.3f} {cv['width'].mean():7.3f}")

    print("\n[頑健性] beta の扱いを変えたときの指数")
    cases = [
        ("beta 自由 (<=500)", df, dict()),
        ("beta 自由 (上限なし)", df, dict(beta_hi=20000.0)),
        ("beta を SSRFB 実測に固定", df, dict(beta_fixed=kurzak.BETA_MEASURED)),
        ("AOBA を除く (p<=32)", no_aoba, dict()),
        ("AOBA のみ (p=64/128)", df[df["config"].str.startswith("aoba")], dict(beta_hi=20000.0)),
    ]
    print(f"{'条件':28s} {'点数':>5s} {'kappa':>7s} {'mu':>7s} {'sigma':>7s} {'delta':>7s}")
    for name, d, kw in cases:
        r = kurzak.fit(d, **kw)
        print(f"{name:28s} {d['g'].nunique():5d} {r['kappa']:7.3f} {r['mu']:7.3f} "
              f"{r['sigma']:7.3f} {r['delta']:7.3f}")

    print("\n[構成を1つ抜いたときの指数のばらつき] (beta 自由 <=500)")
    rows = []
    for c in sorted(df["config"].unique()):
        r = kurzak.fit(df[df["config"] != c], )
        rows.append(dict(dropped=c, kappa=r["kappa"], mu=r["mu"],
                         sigma=r["sigma"], delta=r["delta"]))
    L = pd.DataFrame(rows)
    print(L.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(L[["kappa", "mu", "sigma", "delta"]].agg(["min", "max", "mean"])
          .to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n[交絡のない唯一のコア数対比] AOBA-B 64コア vs 128コア（同一 EPYC 7702）")
    opt = io.load_optima()
    a = opt[opt["config"].str.startswith("aoba")]
    for size in (4096, 8192):
        s1 = a[(a["size"] == size) & (a["config"] == "aoba-b_s1_smt-off")]["nb_opt"]
        s2 = a[(a["size"] == size) & (a["config"] == "aoba-b_s2_smt-off")]["nb_opt"]
        la, lb = np.log(s1.to_numpy()), np.log(s2.to_numpy())
        d_ = la.mean() - lb.mean()
        se = np.sqrt(la.var(ddof=1) / len(la) + lb.var(ddof=1) / len(lb))
        m, mse = d_ / np.log(2), se / np.log(2)
        print(f"  size={size}: nb_opt {s1.mean():.0f} (n={len(s1)}) -> {s2.mean():.0f} "
              f"(n={len(s2)})  m = {m:.2f} ± {mse:.2f}  (95%CI {m-1.96*mse:.2f}〜{m+1.96*mse:.2f})")
    print("  参考: 本研究の m=0.24、Kurzak の mu=1.0 は kappa≈2.4 のとき m≈0.41 に相当")

    print("\n[モデルに依らないサイズ指数] log nb_opt = 傾き * log size + 構成固定効果")
    x, y, cfg = [], [], []
    for c, sub in df.groupby("config"):
        pts = sub.loc[sub.groupby("size")["GFlops"].idxmax()]
        x += list(np.log(pts["size"].to_numpy(float)))
        y += list(np.log(pts["nb"].to_numpy(float)))
        cfg += [c] * len(pts)
    x, y, cfg = np.array(x), np.array(y), np.array(cfg)
    cs = sorted(set(cfg))
    m_ = np.zeros((len(y), len(cs) + 1))
    m_[:, 0] = x
    for i, c in enumerate(cs):
        m_[cfg == c, i + 1] = 1
    b, *_ = np.linalg.lstsq(m_, y, rcond=None)
    res = y - m_ @ b
    s2 = res @ res / (len(y) - m_.shape[1])
    se = float(np.sqrt(s2 * np.linalg.pinv(m_.T @ m_)[0, 0]))
    print(f"  傾き = {b[0]:.3f} ± {se:.3f}  (95%CI {b[0]-1.96*se:.3f}〜{b[0]+1.96*se:.3f})")
    print(f"  Kurzak のタイル比は傾き 1.0 を要求する → t = {(b[0]-1)/se:.1f}")


def main() -> int:
    task12()
    task34()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
