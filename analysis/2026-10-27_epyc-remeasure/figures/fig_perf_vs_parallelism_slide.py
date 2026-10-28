"""
性能比と W/(pD) の散布図（2026-10-21 スライド p24 と同じ形式）を、定数 c, k を変えて描く。

    fig_perf_vs_parallelism_refit.png   c = 2.512, k = 1.464（差し替え後のデータで40条件を当てはめ直した値、全点fit）
    fig_perf_vs_parallelism_refit_loao.png  上の LOAO 版。中間40条件は、その機種を抜いて当てはめ直した c, k
                                        （../data/fold_constants.csv）、追加17条件は全点fit の c, k
    fig_perf_vs_parallelism_fit57.png   57条件すべてで当てはめた c, k（../data/fold_constants57.csv の ALL 行）
    fig_perf_vs_parallelism_loao57.png  57条件での LOAO。どの条件も、その機種（全サイズ）を抜いて当てはめた c, k
    fig_perf_vs_parallelism_theory.png  c = √7.5,  k = 2    （Brent の定理からの理論値。p24 と同じモデル）
    --check で、10-21 のデータからスライド p24 の図を描き直す（形式の確認用）

対象は HT 無効・1ソケットの57条件。β と W/(pD) は ../s1_smt-off/data/task_a_table.csv の値。
"""
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm

HERE = Path(__file__).resolve().parent
A = HERE.parent
os.environ["TILEQR_SUBSET"] = "s1_smt-off"
sys.path.insert(0, str(A / "scripts"))
from common import eta_x, kurzak, load_curves  # noqa: E402

fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"

# p24 の画像から取った色
PURPLE, ORANGE, SHADE = "#aa4eff", "#e0601b", "#fbe7dc"
INK, AXIS, GRAY = "#262626", "#595959", "#8c8c8c"
YLIM = (55.5, 101.6)
OFFSETS = {"refit_loao": {("EPYC7702 s1", 4096): (-6, 8), ("EPYC7702 s1", 2048): (-7, 0),
                          ("EPYC7702 s1", 8192): (7, -8)},
           "loao57": {("EPYC7543", 1024): (-7, 0), ("EPYC7702 s1", 2048): (-7, -2),
                      ("EPYC7702 s1", 4096): (7, -9), ("EPYC7702 s1", 8192): (7, 2)},
           "fit57": {("EPYC7543", 1024): (-7, -5), ("EPYC7702 s1", 2048): (-7, 6),
                     ("EPYC7702 s1", 4096): (7, 7), ("EPYC7702 s1", 8192): (7, -5)},
           "refit": {("EPYC7702 s1", 4096): (-6, -9), ("EPYC7702 s1", 8192): (7, -8)}}


def loao_constants():
    """中間40条件の config → その機種を抜いて当てはめた (c, k)。"""
    from common import CONFIGS40
    f = pd.read_csv(A / "data/fold_constants.csv")
    labels = ["EPYC 7702（AOBA-B）", "EPYC 7543", "Xeon Silver 4214", "Core i7-6900K", "Ryzen 5 7400F",
              "Core i5-8500", "Core i3-10100", "Core i7-7700", "Core i5-7400", "Core i3-7100"]
    lab2cfg = dict(zip(labels, CONFIGS40))
    return {lab2cfg[r.held_out_config]: (r.c, r.k) for r in f.itertuples() if r.held_out_config in lab2cfg}


def loao57_constants():
    """config → 57条件からその機種を抜いて当てはめた (c, k)、と ALL 行の (c, k)。"""
    f = pd.read_csv(A / "data/fold_constants57.csv").set_index("held_out_config")
    return {cfg: (r.c, r.k) for cfg, r in f.iterrows() if cfg != "ALL"}, tuple(f.loc["ALL", ["c", "k"]])


def perf_table(c, k, per_config=None, sizes=None):
    """per_config: {config: (c, k)}。sizes のサイズにだけ使う（既定は中間40条件の size ≤ 8192）。"""
    from common import SIZES40
    sizes = sizes or SIZES40
    per_config = per_config or {}
    tab = pd.read_csv(A / "s1_smt-off/data/task_a_table.csv")
    df = load_curves()
    df = df[(df.nb >= 32) & (df.nb <= 512)].reset_index(drop=True)
    obs = kurzak.observed(df)
    rows = []
    for r in tab.itertuples():
        t = obs[(r.config, r.size)]
        cc, kk = per_config.get(r.config, (c, k)) if r.size in sizes else (c, k)
        f = t["nb"] / (t["nb"] + r.beta) * eta_x(t["nb"], float(r.size), float(r.p), cc, kk)
        i = int(np.argmax(f))
        rows.append(dict(label=r.label, size=r.size, p=r.p, WpD=r.WpD, nb_opt=t["nb_opt"],
                         nb_pred=t["nb"][i], perf=100 * t["G"][i] / t["peak"]))
    return pd.DataFrame(rows)


def plot(d, path, offsets=None):
    """offsets: {(label, size): (dx, dy)}。点が近くてラベルが重なるときだけ使う（単位はポイント）。"""
    offsets = offsets or {}
    fig, ax = plt.subplots(figsize=(7.5, 4.75), dpi=200, layout="constrained")
    ax.axvspan(0.1, 1.5, color=SHADE, lw=0, zorder=0)
    ax.text(0.125, 59.3, "W/(pD) < 1.5", color=ORANGE, fontsize=12)
    ax.axhline(95, color=GRAY, ls="--", lw=1, zorder=1)
    ax.text(58, 95.6, "95%", color=GRAY, fontsize=11, ha="right", va="bottom")
    big = d.p >= 24
    for m, col, lab in [(~big, PURPLE, f"p ≤ 12（{(~big).sum()}条件）"),
                        (big, ORANGE, f"p = 32, 64（{big.sum()}条件）")]:
        ax.scatter(d.WpD[m], d.perf[m], s=42, color=col, edgecolor="white", linewidth=0.8, zorder=3, label=lab)
    for r in d[big & (d.perf < 95)].itertuples():
        dx, dy = offsets.get((r.label, r.size), (7, 0))
        ax.annotate(f"{r.label.replace(' s1', '')}  {r.size}", (r.WpD, r.perf), xytext=(dx, dy),
                    textcoords="offset points", va="center", ha="left" if dx >= 0 else "right",
                    fontsize=11, color=INK)
    ax.set_xscale("log"); ax.set_xlim(0.1, 60); ax.set_ylim(*YLIM)
    ax.set_xlabel("W/(pD)　コアあたりの平均並列度（実測最適 nb で計算）", color=INK, fontsize=12)
    ax.set_ylabel("予測 nb の性能比 [%]", color=INK, fontsize=12)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(AXIS)
    ax.tick_params(colors=AXIS, labelsize=12, labelcolor=INK)
    ax.legend(loc="lower right", frameon=False, fontsize=12, labelcolor=INK, handletextpad=1.2,
              borderaxespad=1.0)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def check_1021():
    """10-21 のデータ（task_c の (i) 列）からスライド p24 を描き直す。"""
    o = A.parent / "2026-10-21/s1_smt-off/data"
    tab = pd.read_csv(o / "task_a_table.csv")
    pr = pd.read_csv(o / "task_c_predictions.csv")
    pr = pr[pr.method == "i"][["config", "size", "perf"]]
    d = tab[["config", "label", "size", "p", "WpD"]].merge(pr, on=["config", "size"])
    d["perf"] *= 100
    plot(d, HERE / "check_p24_1021.png")


def summary(name, d):
    big = d.p >= 24
    print(f"{name}: 平均 {d.perf.mean():.1f}% 最低 {d.perf.min():.1f}%  95%未満 {(d.perf < 95).sum()}"
          f"（p≥24 {(big & (d.perf < 95)).sum()}、p≤12 {(~big & (d.perf < 95)).sum()}）")
    print(d[d.perf < 95].sort_values("perf")[["label", "size", "p", "WpD", "nb_opt", "nb_pred", "perf"]]
          .round(2).to_string(index=False))


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_1021()
    else:
        runs = {"refit": (2.512, 1.464, None), "refit_loao": (2.512, 1.464, loao_constants()),
                "theory": (np.sqrt(7.5), 2.0, None)}
        per57, (c57, k57) = loao57_constants()
        runs["fit57"] = (c57, k57, None)
        runs["loao57"] = (c57, k57, per57)
        for name, (c, k, per) in runs.items():
            d = perf_table(c, k, per, sizes=(1024, 2048, 4096, 8192, 16384) if name == "loao57" else None)
            summary(f"{name} c={c:.3f} k={k:.3f}", d)
            d.round(4).to_csv(A / f"s1_smt-off/data/perf_vs_parallelism_{name}.csv", index=False)
            plot(d, HERE / f"fig_perf_vs_parallelism_{name}.png", OFFSETS.get(name))
