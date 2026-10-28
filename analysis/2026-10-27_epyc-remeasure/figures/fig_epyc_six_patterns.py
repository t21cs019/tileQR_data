"""
EPYC 7543 の6パターン（(c, k) 3通り × β 2通り）の予測性能比。スライド用（7.5 × 4.75 in, 200 dpi）。

入力は ../s1_smt-off/data/epyc_six_patterns.csv（scripts/epyc_six_patterns.py の出力）。
    fig_epyc_six_patterns.png       c, k は中間40条件すべてで当てはめた値
    fig_epyc_six_patterns_loao.png  c, k は EPYC 7543 を抜いた36条件で当てはめた値
    fig_epyc_six_patterns57.png / _loao57.png  上の2枚の c, k を57条件で当てはめた版
                                    （epyc_six_patterns.py --set 57 の出力。LOAO は EPYC 7543 を抜いた52条件）
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"

INK, AXIS, GRAY, GRID = "#262626", "#595959", "#8c8c8c", "#ececec"
CK = {"theory": "#2a78d6", "k_fit": "#eb6834", "ck_fit": "#1baf7a"}
SIZES = [1024, 2048, 4096, 8192, 16384]


def ck_label(ck, c, k):
    return {"theory": "c, k 理論値（c = 2.739, k = 2）",
            "k_fit": f"c 理論値・k フィット（k = {k:.3f}）",
            "ck_fit": f"c, k フィット（c = {c:.3f}, k = {k:.3f}）"}[ck]


def plot(d, path):
    fig, ax = plt.subplots(figsize=(7.5, 4.75), dpi=200, layout="constrained")
    groups = SIZES + ["平均"]
    order = [(ck, b) for ck in CK for b in ["1core", "multi"]]
    width = 0.11
    ax.axhline(95, color=GRAY, ls="--", lw=1, zorder=1)
    ax.text(len(groups) - 0.5, 95.3, "95%", color=GRAY, fontsize=11, ha="right", va="bottom")
    for gi, g in enumerate(groups):
        if gi % 2:
            ax.axvspan(gi - 0.5, gi + 0.5, color="#f7f7f7", lw=0, zorder=0)
        placed = []  # この群で横に置いたラベル (向き, 値)
        for j, (ck, b) in enumerate(order):
            s = d[(d.ck == ck) & (d.beta_src == b)]
            v = s.perf.mean() if g == "平均" else s[s["size"] == g].perf.iloc[0]
            x = gi + (j - 2.5) * width
            filled = b == "1core"
            ax.scatter(x, v, s=58, marker="o", zorder=3, color=CK[ck] if filled else "white",
                       edgecolor=CK[ck] if not filled else "white", linewidth=1.8 if not filled else 0.8)
            if v < 95:
                # 1コアの β は左、32コアの β は右に置く（同じ (c, k) の2点は値が近いため）
                # 同じ向きに値の近いラベルがすでにあれば、点の下に置く
                if any(sd == filled and abs(pv - v) < 1.0 for sd, pv in placed):
                    ax.annotate(f"{v:.1f}", (x, v), xytext=(0, -9), textcoords="offset points",
                                ha="center", va="top", fontsize=9, color=INK)
                    continue
                placed.append((filled, v))
                ax.annotate(f"{v:.1f}", (x, v), xytext=(-7 if filled else 7, 0), textcoords="offset points",
                            ha="right" if filled else "left", va="center", fontsize=9, color=INK)
    ax.set_xticks(range(len(groups)), [str(g) for g in groups])
    ax.set_xlim(-0.65, len(groups) - 0.5)
    ax.set_ylim(68, 101.5)
    ax.set_xlabel("行列サイズ", color=INK, fontsize=12)
    ax.set_ylabel("予測 nb の性能比 [%]", color=INK, fontsize=12)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(AXIS)
    ax.tick_params(colors=AXIS, labelsize=11, labelcolor=INK)

    first = d.drop_duplicates("ck").set_index("ck")
    h1 = [Line2D([], [], ls="", marker="o", ms=8, color=CK[ck], label=ck_label(ck, first.c[ck], first.k[ck]))
          for ck in CK]
    h2 = [Line2D([], [], ls="", marker="o", ms=8, color="#595959", label="β：1コア計測（184.2）"),
          Line2D([], [], ls="", marker="o", ms=8, markerfacecolor="white", markeredgecolor="#595959",
                 markeredgewidth=1.8, label="β：32コア同時計測（143.6）")]
    leg = ax.legend(handles=h1 + h2, loc="lower right", frameon=True, fontsize=9.5, labelcolor=INK,
                    handletextpad=0.4, borderpad=0.6, ncol=1)
    leg.get_frame().set_edgecolor("#dddddd")
    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    d = pd.read_csv(HERE.parent / "s1_smt-off/data/epyc_six_patterns.csv")
    d = d[d.beta_src.isin(["1core", "multi"])]
    plot(d[d.scope == "全点"], HERE / "fig_epyc_six_patterns.png")
    plot(d[d.scope == "LOAO"], HERE / "fig_epyc_six_patterns_loao.png")
    d = pd.read_csv(HERE.parent / "s1_smt-off/data/epyc_six_patterns57.csv")
    d = d[d.beta_src.isin(["1core", "multi"])]
    plot(d[d.scope == "全点"], HERE / "fig_epyc_six_patterns57.png")
    plot(d[d.scope == "LOAO"], HERE / "fig_epyc_six_patterns_loao57.png")
