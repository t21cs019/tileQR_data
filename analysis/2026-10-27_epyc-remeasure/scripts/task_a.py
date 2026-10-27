"""
タスクA: 予測モデル (第3世代, c=2.564, k=1.352) が崩れる条件の調査。

出力 (analysis/2026-10-21/):
  data/beta_arch.csv, data/beta_curves.csv
  data/task_a_table.csv, data/task_a_table.md
  fig_a_perf_vs_parallelism.png, fig_a_nbratio_vs_x.png, fig_a_curves.png
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import (BETA_FOLD, C_FIT, CONFIGS40, K_FIT, LABEL, OUT, ROOT, SIZES40, keep_config,
                    D_formula, W_formula, beta_from_ssrfb, eta_x, kurzak, load_curves,
                    predict_nb)

DATA = OUT / "data"
DATA.mkdir(exist_ok=True)

# 図の配色 (dataviz reference palette, 散布図は3色まで)
COL = {"p≤8": "#2a78d6", "p=12–32": "#eb6834", "p=64–128": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def pgroup(p):
    return "p≤8" if p <= 8 else ("p=12–32" if p <= 32 else "p=64–128")


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def build_table():
    arch_beta, curves_beta = beta_from_ssrfb()
    arch_beta.to_csv(DATA / "beta_arch.csv", index=False)
    curves_beta.to_csv(DATA / "beta_curves.csv", index=False)
    beta_ssrfb = dict(zip(arch_beta.arch, arch_beta.beta))

    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)].reset_index(drop=True)
    obs = kurzak.observed(df)
    fold = pd.read_csv(ROOT / "derived/fold_constants.csv")
    label2cfg = dict(zip(
        ["EPYC 7702（AOBA-B）", "EPYC 7543", "Xeon Silver 4214", "Core i7-6900K", "Ryzen 5 7400F",
         "Core i5-8500", "Core i3-10100", "Core i7-7700", "Core i5-7400", "Core i3-7100"], CONFIGS40))
    fold_ck = {label2cfg[r.held_out_config]: (r.c, r.k)
               for r in fold.itertuples() if r.held_out_config in label2cfg}

    rows = []
    for (cfg, size), sub in df.groupby(["config", "size"]):
        if not keep_config(cfg):
            continue
        t = obs[(cfg, size)]
        p = float(sub.p.iloc[0])
        arch = sub.arch.iloc[0]
        in40 = cfg in CONFIGS40 and size in SIZES40
        if arch in BETA_FOLD:
            beta, beta_src = BETA_FOLD[arch], "fold_constants.py"
        elif arch in beta_ssrfb:
            beta, beta_src = beta_ssrfb[arch], "raw/ssrfb (MRE≤5%平均)"
        else:
            continue
        nb = t["nb"]
        i, _ = predict_nb(nb, beta, eta_x(nb, size, p, C_FIT, K_FIT))
        nb_pred = nb[i]
        perf_full = t["G"][i] / t["peak"]
        if in40:
            c, k = fold_ck[cfg]
            j, _ = predict_nb(nb, beta, eta_x(nb, size, p, c, k))
            perf_cv, nb_cv = t["G"][j] / t["peak"], nb[j]
        else:
            perf_cv, nb_cv = np.nan, np.nan
        nb_opt = t["nb_opt"]
        Nopt, Npred = size / nb_opt, size / nb_pred
        W, D = W_formula(Nopt), D_formula(Nopt)
        rows.append(dict(
            config=cfg, label=LABEL.get(cfg, cfg), set="中間40" if in40 else "追加",
            p=p, threads=int(sub.threads.iloc[0]), size=size, beta=beta, beta_src=beta_src,
            nb_opt=nb_opt, band_lo=t["lo"], band_hi=t["hi"], nb_pred=nb_pred, perf=perf_full,
            nb_pred_cv=nb_cv, perf_cv=perf_cv,
            perf_zs=perf_cv if in40 else perf_full,
            N_opt=Nopt, N_pred=Npred, WD=W / D, WpD=W / (p * D),
            x_opt=C_FIT * np.sqrt(p) * nb_opt / size, x_pred=C_FIT * np.sqrt(p) * nb_pred / size,
            nb_min=nb.min(), nb_max=nb.max(),
        ))
    tab = pd.DataFrame(rows)
    order = {c: i for i, c in enumerate(LABEL)}
    tab["o"] = tab.config.map(order)
    tab = tab.sort_values(["set", "o", "size"], ascending=[False, True, True]).drop(columns="o")
    tab = tab.sort_values(["set", "p", "config", "size"], ascending=[True, False, True, True])
    tab.to_csv(DATA / "task_a_table.csv", index=False, float_format="%.4g")
    return tab, df, obs


def md_table(tab):
    head = ("| 構成 | 区分 | p | size | β | 実測最適nb | 予測nb | 性能比(全点fit) | 性能比(LOAO) "
            "| N_opt | N_pred | W/D | W/(pD) | x |\n|" + "---|" * 14 + "\n")
    lines = []
    for r in tab.itertuples():
        cv = f"{r.perf_cv*100:.1f}%" if r.set == "中間40" else "—"
        flag = " ⚠" if r.perf_zs < 0.95 else ""
        lines.append(
            f"| {r.label} | {r.set} | {r.p:g} | {r.size} | {r.beta:.1f} | {r.nb_opt:g} | {r.nb_pred:g} "
            f"| {r.perf*100:.1f}%{flag if r.set=='追加' else ''} | {cv}{flag if r.set=='中間40' else ''} "
            f"| {r.N_opt:.1f} | {r.N_pred:.1f} | {r.WD:.1f} | {r.WpD:.2f} | {r.x_opt:.3f} |")
    s = head + "\n".join(lines) + "\n"
    (DATA / "task_a_table.md").write_text(s, encoding="utf-8")
    return s


def fig_a(tab):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
    style(ax)
    for g, col in COL.items():
        for ht, mk in ((False, "o"), (True, "^")):
            s = tab[(tab.p.map(pgroup) == g) & (tab.config.str.contains("smt-on") == ht)]
            if s.empty:
                continue
            ax.scatter(s.WpD, s.perf_zs * 100, s=30, marker=mk, color=col,
                       edgecolor="white", lw=1.0, zorder=3,
                       label=f"{g}{' (HT有効)' if ht else ''}")
    ax.axhline(95, color=INK2, lw=1, ls="--")
    ax.text(ax.get_xlim()[0] if False else 0.02, 95.4, "95%", color=INK2, fontsize=8,
            transform=ax.get_yaxis_transform())
    bad = tab[tab.perf_zs < 0.92]
    for r in bad.itertuples():
        ax.annotate(f"{r.label} {r.size}", (r.WpD, r.perf_zs * 100), xytext=(5, -3),
                    textcoords="offset points", fontsize=7, color=INK)
    ax.set_xscale("log")
    ax.set_xlabel("W/(p·D)  （実測最適 nb での N、D = 30N − 34）", color=INK, fontsize=9)
    ax.set_ylabel("性能比 [%]（中間40はLOAO、追加は全点fit）", color=INK, fontsize=9)
    ax.set_title("性能比と、コアあたりの平均並列度（ラベルは性能比 92% 未満）", color=INK, fontsize=11, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_a_perf_vs_parallelism.png")
    plt.close(fig)


def fig_b(tab):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
    style(ax)
    for g, col in COL.items():
        for ht, mk in ((False, "o"), (True, "^")):
            s = tab[(tab.p.map(pgroup) == g) & (tab.config.str.contains("smt-on") == ht)]
            if s.empty:
                continue
            ax.scatter(s.x_opt, s.nb_opt / s.nb_pred, s=30, marker=mk, color=col,
                       edgecolor="white", lw=1.0, zorder=3,
                       label=f"{g}{' (HT有効)' if ht else ''}")
    ax.axhline(1, color=INK2, lw=1, ls="--")
    for r in tab[tab.perf_zs < 0.92].itertuples():
        ax.annotate(f"{r.label} {r.size}", (r.x_opt, r.nb_opt / r.nb_pred), xytext=(5, -3),
                    textcoords="offset points", fontsize=7, color=INK)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("x = c·√p·nb_opt / size  （c = 2.564）", color=INK, fontsize=9)
    ax.set_ylabel("実測最適 nb / 予測 nb（全点fit）", color=INK, fontsize=9)
    ax.set_title("nb の予測のずれと x（ラベルは性能比 92% 未満）", color=INK, fontsize=11, loc="left")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_a_nbratio_vs_x.png")
    plt.close(fig)


def fig_c(tab, obs, picks):
    fig, axes = plt.subplots(1, len(picks), figsize=(4.0 * len(picks), 3.6), dpi=160)
    for ax, (cfg, size) in zip(np.atleast_1d(axes), picks):
        style(ax)
        r = tab[(tab.config == cfg) & (tab["size"] == size)].iloc[0]
        t = obs[(cfg, size)]
        nb = t["nb"]
        _, f = predict_nb(nb, r.beta, eta_x(nb, size, r.p, C_FIT, K_FIT))
        ax.plot(nb, t["G"] / t["peak"], color="#2a78d6", lw=2, label="実測")
        ax.plot(nb, f / f.max(), color="#eb6834", lw=2, label="モデル (c=2.564, k=1.352)")
        ax.axvline(r.nb_opt, color="#2a78d6", lw=1, ls=":")
        ax.axvline(r.nb_pred, color="#eb6834", lw=1, ls=":")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{r.label}  p={r.p:g}  size={size}\n実測最適 {r.nb_opt:g} / 予測 {r.nb_pred:g}"
                     f" / 性能比 {r.perf*100:.1f}%", fontsize=9, color=INK, loc="left")
        ax.set_xlabel("nb", color=INK, fontsize=9)
    np.atleast_1d(axes)[0].set_ylabel("ピークで正規化した性能", color=INK, fontsize=9)
    np.atleast_1d(axes)[0].legend(fontsize=8, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_a_curves.png")
    plt.close(fig)


def main():
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]
    tab, df, obs = build_table()
    md_table(tab)
    fig_a(tab)
    fig_b(tab)
    # 代表: 多コア・小行列で最悪の2条件と、逆向きにずれる HT 構成の最悪1条件
    many = tab[tab.p >= 24].sort_values("perf_zs").head(2)
    ht = tab[tab.config.str.contains("smt-on")].sort_values("perf_zs").head(1)
    if ht.empty:   # HT 構成が無いときは p<24 の最悪条件 (逆向きのずれの代表)
        ht = tab[tab.p < 24].sort_values("perf_zs").head(1)
    picks = list(zip(many.config, many["size"])) + list(zip(ht.config, ht["size"]))
    fig_c(tab, obs, picks)
    pd.set_option("display.width", 250)
    print(tab[["label", "set", "p", "size", "beta", "nb_opt", "nb_pred", "perf", "nb_pred_cv",
               "perf_cv", "N_opt", "WD", "WpD", "x_opt", "nb_min", "nb_max"]].to_string())


if __name__ == "__main__":
    main()
