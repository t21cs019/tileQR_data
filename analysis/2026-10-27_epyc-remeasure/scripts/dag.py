"""
タイルQR分解（フラットツリー, TS カーネル）のタスク DAG と最長経路。

二つの依存の定義を持つ:

  "bouwmeester" … Bouwmeester et al. (SC'11) の FlatTree(TS) の依存。
                  データの真の流れ (RAW) だけを辿る。
  "plasma"      … PLASMA 25.5.27 (548e0bd) compute/pdgeqrf.c と core_blas の
                  `#pragma omp task depend(...)` をそのまま写したもの。
                  bouwmeester との違いは1点だけ:
                    core_dunmqr は depend(in: A(k,k))、core_dtsqrt は depend(inout: A(k,k))
                    なので、OpenMP は TSQRT(k+1,k) を全 UNMQR(k,n) の後に回す (WAR)。
                  実際の dunmqr が読むのは A(k,k) の下三角 (V)、dtsqrt が書くのは
                  上三角 (R) なので数値的には不要な依存だが、タイル単位の depend
                  では区別できない。

カーネル重み (nb^3/3 flops 単位): GEQRT=4, UNMQR=6, TSQRT=6, TSMQR=12。
"""

from __future__ import annotations

W8 = {"GEQRT": 4, "UNMQR": 6, "TSQRT": 6, "TSMQR": 12}


def build(N: int, variant: str = "bouwmeester"):
    """
    N x N タイルの DAG。タスクは PLASMA の投入順 (pdgeqrf.c のループ順) に並ぶ。
    戻り値: (tasks, preds)  tasks[i] = (kind, m, n, k), preds[i] = 先行タスク id のリスト
    """
    tasks, preds, idx = [], [], {}

    def add(key, deps):
        idx[key] = len(tasks)
        tasks.append(key)
        preds.append([idx[d] for d in deps if d in idx])

    for k in range(N):
        # 直前ステップでこのタイルを最後に書いたタスク
        prev = lambda m, n: ("TSMQR", m, n, k - 1)
        add(("GEQRT", k, k, k), [prev(k, k)])
        for n in range(k + 1, N):
            add(("UNMQR", k, n, k), [("GEQRT", k, k, k), prev(k, n)])
        for m in range(k + 1, N):
            up = ("GEQRT", k, k, k) if m == k + 1 else ("TSQRT", m - 1, k, k)
            deps = [up, prev(m, k)]
            if variant == "plasma" and m == k + 1:
                deps += [("UNMQR", k, n, k) for n in range(k + 1, N)]
            add(("TSQRT", m, k, k), deps)
            for n in range(k + 1, N):
                top = ("UNMQR", k, n, k) if m == k + 1 else ("TSMQR", m - 1, n, k)
                add(("TSMQR", m, n, k), [("TSQRT", m, k, k), top, prev(m, n)])
    return tasks, preds


def longest_path(N: int, variant: str = "bouwmeester"):
    """(W, D, path)。path はクリティカルパス上のタスク列。"""
    tasks, preds = build(N, variant)
    fin, arg = [0] * len(tasks), [-1] * len(tasks)
    for i, (kind, *_rest) in enumerate(tasks):   # 投入順はトポロジカル順
        best, b = 0, -1
        for j in preds[i]:
            if fin[j] > best:
                best, b = fin[j], j
        fin[i] = best + W8[kind]
        arg[i] = b
    W = sum(W8[t[0]] for t in tasks)
    end = max(range(len(tasks)), key=lambda i: fin[i])
    path, i = [], end
    while i >= 0:
        path.append(tasks[i])
        i = arg[i]
    return W, fin[end], path[::-1]


def dump_edges(N: int, variant: str, path: str):
    """C のスケジューラに渡す形式: 1行目 n_tasks, 以降 'weight npred p1 p2 ...'。"""
    tasks, preds = build(N, variant)
    with open(path, "w") as f:
        f.write(f"{len(tasks)}\n")
        for t, ps in zip(tasks, preds):
            f.write(f"{W8[t[0]]} {len(ps)} {' '.join(map(str, ps))}\n")


if __name__ == "__main__":
    import sys
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for v in ("bouwmeester", "plasma"):
        W, D, p = longest_path(N, v)
        print(v, N, W, D, " -> ".join(f"{t[0]}({t[1]},{t[2]};k={t[3]})" for t in p))
