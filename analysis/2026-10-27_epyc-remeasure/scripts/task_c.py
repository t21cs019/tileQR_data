"""
タスクC: c, k を計測なしで決められるか。並列効率項の定式を差し替えて性能比を比べる。

  current_full : c=2.564, k=1.352 (40 条件の全点フィット)
  current_loao : 中間40 は leave-one-arch-out の c,k (derived/fold_constants.csv)、追加は full
  i            : c=√7.5, k=2
  ii           : c=√7.5 固定, k だけ 40 条件でフィット (kurzak.fit)。LOAO 版も出す
  iii          : η = 1/(1 + p·D/W), D=30N−34, W=4N³ (N=size/nb の連続値)
  iv           : η = min(1, W/(p·D))
  sim_*        : DAG を p コアで貪欲スケジューリングした η (greedy_sched.c)。
                 N=1..128 の整数点を線形補間。N>128 は 1−η ∝ 1/N² で外挿。

β と p は task_a と同じ。nb は実測格子 [32, 512] の argmax。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import (BASE, BETA_FOLD, C_FIT, CONFIGS40, GEN3_FIXED, K_FIT, OUT, ROOT, SIZES40, eta_brent,
                    eta_min, eta_x, kurzak, load_curves)

DATA = OUT / "data"


def sim_eta_fn(path):
    s = pd.read_csv(path, sep=" ")
    tabs = {p: g.sort_values("N")[["N", "eta"]].to_numpy() for p, g in s.groupby("p")}

    def f(nb, size, p):
        t = tabs[int(round(p))]
        N = size / nb
        e = np.interp(N, t[:, 0], t[:, 1])
        Nm, em = t[-1]
        big = N > Nm
        e[big] = 1 - (1 - em) * (Nm / N[big]) ** 2
        return e
    return f


def fit_k_only(df, exclude_config=None):
    d = df[df.config.isin(CONFIGS40) & df["size"].isin(SIZES40)]
    if exclude_config:
        d = d[d.config != exclude_config]
    fixed = dict(GEN3_FIXED, c2=np.sqrt(7.5))
    r = kurzak.fit(d, fixed=fixed, beta_fixed=BETA_FOLD)
    return r["kappa"]


def main():
    tab = pd.read_csv(DATA / "task_a_table.csv")
    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)].reset_index(drop=True)
    obs = kurzak.observed(df)

    k_ii = fit_k_only(df)
    k_ii_loao = {c: fit_k_only(df, c) for c in CONFIGS40}
    print(f"(ii) c=√7.5 固定で k = {k_ii:.4f}  LOAO: "
          + ", ".join(f"{k:.3f}" for k in k_ii_loao.values()))

    sims = {
        "sim_fifo": sim_eta_fn(BASE / "data" / "sched_bouwmeester_fifo.txt"),
        "sim_cp": sim_eta_fn(BASE / "data" / "sched_bouwmeester_cp.txt"),
        "sim_plasma": sim_eta_fn(BASE / "data" / "sched_plasma_fifo.txt"),
    }
    fold = pd.read_csv(ROOT / "derived/fold_constants.csv")
    fold_ck = dict(zip(CONFIGS40, zip(fold.c[:10], fold.k[:10])))
    c0 = np.sqrt(7.5)

    rows = []
    for r in tab.itertuples():
        t = obs[(r.config, r.size)]
        nb, size, p, beta = t["nb"], float(r.size), float(r.p), r.beta
        in40 = r.set == "中間40"
        cl, kl = fold_ck[r.config] if in40 else (C_FIT, K_FIT)
        etas = {
            "current_full": eta_x(nb, size, p, C_FIT, K_FIT),
            "current_loao": eta_x(nb, size, p, cl, kl),
            "i": eta_x(nb, size, p, c0, 2.0),
            "ii": eta_x(nb, size, p, c0, k_ii),
            "ii_loao": eta_x(nb, size, p, c0, k_ii_loao[r.config] if in40 else k_ii),
            "iii": eta_brent(nb, size, p),
            "iv": eta_min(nb, size, p),
            # HT 構成の p を論理スレッド数にした場合 (現行 c,k)
            "current_p=threads": eta_x(nb, size, float(r.threads), C_FIT, K_FIT),
        }
        for name, fn in sims.items():
            etas[name] = fn(nb, size, p)
        for name, eta in etas.items():
            f = nb / (nb + beta) * eta
            i = int(np.argmax(f))
            rows.append(dict(config=r.config, label=r.label, set=r.set, p=p, threads=r.threads,
                             size=r.size, method=name, nb_pred=nb[i], nb_opt=t["nb_opt"],
                             perf=t["G"][i] / t["peak"]))
    res = pd.DataFrame(rows)
    res.to_csv(DATA / "task_c_predictions.csv", index=False, float_format="%.4g")

    def summ(d):
        return pd.Series(dict(n=len(d), mean=d.perf.mean() * 100, min=d.perf.min() * 100,
                              n95=int((d.perf >= 0.95).sum())))

    out = []
    add = res[res.set == "追加"]
    n_all = res.config.nunique() and len(res[res.method == "current_full"])
    for scope, d in [("中間40", res[res.set == "中間40"]),
                     (f"追加{len(add[add.method == 'current_full'])}", add),
                     (f"全{n_all}", res)]:
        s = d.groupby("method").apply(summ).reset_index()
        s.insert(0, "scope", scope)
        out.append(s)
    summary = pd.concat(out)
    summary.to_csv(DATA / "task_c_summary.csv", index=False, float_format="%.2f")
    pd.set_option("display.width", 200)
    print(summary.to_string(index=False))

    # HT 構成だけ: p=物理 vs p=スレッド
    ht = res[res.config.str.contains("smt-on") & res.method.isin(["current_full", "current_p=threads"])]
    if not ht.empty:
        print(ht.pivot_table(index=["label", "size"], columns="method", values=["nb_pred", "perf"]).to_string())


if __name__ == "__main__":
    main()
