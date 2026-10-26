"""
タスクB: クリティカルパス長 D と総仕事量 W を DAG から計算して式と照合する。
タスクCの補助図 (η の定式比較) もここで描く。

出力:
  data/task_b_check.csv
  fig_b_dag_3x3.png
  fig_c_eta_forms.png
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import C_FIT, K_FIT, OUT
from dag import W8, build, longest_path

DATA = OUT / "data"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"


def check_table():
    rows = []
    for N in range(2, 65):
        Wb, Db, _ = longest_path(N, "bouwmeester")
        _, Dp, _ = longest_path(N, "plasma")
        rows.append(dict(N=N, W_dag=Wb, W_formula=4 * N**3, D_dag=Db, D_formula=30 * N - 34,
                         D_plasma_dag=Dp, n_tasks=len(build(N)[0])))
    t = pd.DataFrame(rows)
    t.to_csv(DATA / "task_b_check.csv", index=False)
    print("W 一致:", (t.W_dag == t.W_formula).all(), " D 一致 (N=3..64):",
          (t[t.N >= 3].D_dag == t[t.N >= 3].D_formula).all(),
          " PLASMA D − 式:", sorted(set(t.D_plasma_dag - t.D_formula)))
    return t


def fig_dag():
    N = 3
    tasks, preds = build(N, "bouwmeester")
    _, predp = build(N, "plasma")
    _, _, path = longest_path(N, "bouwmeester")
    on = set(path)
    # ASAP 開始時刻を x に
    start = [0] * len(tasks)
    for i, t in enumerate(tasks):
        start[i] = max((start[j] + W8[tasks[j][0]] for j in preds[i]), default=0)
    # 区間が重ならないレーンに詰める (クリティカルパスはレーン0に固定)
    lane_end = [0.0]
    y = [None] * len(tasks)
    for i in sorted(range(len(tasks)), key=lambda i: (tasks[i] not in on, start[i])):
        if tasks[i] in on:
            y[i] = 0
            continue
        for L in range(1, 20):
            busy = [j for j in range(len(tasks)) if y[j] == L and
                    start[j] < start[i] + W8[tasks[i][0]] and start[i] < start[j] + W8[tasks[j][0]]]
            if not busy:
                y[i] = L
                break
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=160)
    pos = {i: (start[i] + W8[tasks[i][0]] / 2, -y[i]) for i in range(len(tasks))}
    for i in range(len(tasks)):
        for j in predp[i]:
            if j in preds[i]:
                continue
            (x0, y0), (x1, y1) = pos[j], pos[i]
            ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=INK2,
                        lw=0.8, ls="--", shrinkA=16, shrinkB=16))
        for j in preds[i]:
            crit = tasks[i] in on and tasks[j] in on
            (x0, y0), (x1, y1) = pos[j], pos[i]
            ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(
                arrowstyle="-|>", color=ORANGE if crit else "#b5b3ad", lw=2.2 if crit else 0.9,
                shrinkA=16, shrinkB=16))
    for i, t in enumerate(tasks):
        kind, m, n, k = t
        x, yy = pos[i]
        w = W8[kind]
        crit = t in on
        ax.add_patch(plt.Rectangle((start[i] + 0.25, yy - 0.3), w - 0.5, 0.6,
                                   facecolor="#fde3d6" if crit else "#eef3fb",
                                   edgecolor=ORANGE if crit else BLUE, lw=1.6 if crit else 0.9,
                                   zorder=3))
        lab = f"{kind}\n({m},{n}) k={k}" if kind in ("TSMQR", "UNMQR") else f"{kind}\n({m},{n}) k={k}"
        ax.text(x, yy, lab, ha="center", va="center", fontsize=6.5, color=INK, zorder=4)
    ax.set_xlim(-1, 58)
    ax.set_ylim(-max(y) - 0.6, 0.6)
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xticks(range(0, 57, 4))
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_xlabel("ASAP 開始時刻（単位 nb³/3 flops。箱の幅 = カーネル重み 4/6/6/12）",
                  fontsize=9, color=INK)
    ax.set_title("3×3 タイル（フラットツリー TS）の DAG。オレンジ = クリティカルパス "
                 "4+6+12+12+6+12+4 = 56 = 30·3−34。破線 = PLASMA の depend で加わる WAR 依存",
                 fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_b_dag_3x3.png")
    plt.close(fig)


def fig_eta():
    s = pd.read_csv(DATA / "sched_bouwmeester_fifo.txt", sep=" ")
    s = s[s.N >= 3]
    s["u"] = 4.0 * s.N**3 / (s.p * (30.0 * s.N - 34))
    u = np.logspace(-2, 2, 400)
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for p, col in ((4, BLUE), (32, ORANGE), (128, AQUA)):
        d = s[s.p == p]
        ax.scatter(d.u, d.eta, s=12, color=col, edgecolor="white", lw=0.6, zorder=3,
                   label=f"DAG 貪欲スケジューリング p={p}")
    ax.plot(u, np.minimum(1, u), color=INK, lw=1.4, ls=":", label="(iv) min(1, W/(pD))")
    ax.plot(u, 1 / (1 + 1 / u), color=INK, lw=1.4, ls="--", label="(iii) 1/(1+pD/W)  (Brent)")
    ax.plot(u, 1 / (1 + (C_FIT**2 / 7.5 / u) ** (K_FIT / 2)), color=INK2, lw=2,
            label=f"現行フィット c={C_FIT:.3f}, k={K_FIT:.3f}")
    ax.set_xscale("log")
    ax.set_xlim(1e-2, 1e2)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("W/(p·D)  （W=4N³, D=30N−34）", fontsize=9, color=INK)
    ax.set_ylabel("並列効率 η", fontsize=9, color=INK)
    ax.set_title("η の定式の比較（現行フィットは x ≈ √(7.5p)/N の近似で横軸に換算）",
                 fontsize=10, color=INK, loc="left")
    ax.legend(fontsize=7.5, frameon=False, loc="upper left")
    ax.tick_params(colors=INK2, labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_c_eta_forms.png")
    plt.close(fig)


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]
    t = check_table()
    print(t[t.N.isin([2, 3, 4, 5, 6, 8, 10, 16, 32, 48, 64])].to_string(index=False))
    for N in (3, 4):
        for v in ("bouwmeester", "plasma"):
            W, D, path = longest_path(N, v)
            print(v, N, D, " → ".join(f"{k}({m},{n};k={kk})[{W8[k]}]" for k, m, n, kk in path))
    fig_dag()
    fig_eta()
