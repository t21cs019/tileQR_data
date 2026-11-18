"""
共通層：PLASMA 548e0bd の dgeqrf の DAG を作り、p ワーカーのリストスケジューリングで模擬する。

- DAG：compute/pdgeqrf.c:39-76 のループの順にタスクを作り、core_blas の depend 句
  （core_dgeqrt.c:178、core_dormqr.c:244、core_dtsqrt.c:220、core_dtsmqr.c:260）を
  OpenMP の規則（in は直前の書き手を待つ、out/inout は直前の書き手と、それ以降の読み手をすべて待つ）で依存に直す。
  war=False にすると、読み手を待つ依存（WAR）を外す（DORMQR→DTSQRT の A(k,k) の依存だけが該当）
- タイル写し（compute/pdge2desc.c・pddesc2ge.c の dlacpy タスク）は copies_bw [B/s/コア] を与えたときだけ入れる
- 重み：kernel の flop 数 / (A·E(nb))、E = nb/(nb+β)。A・β は DTSMQR 1コア（11-11）の値
  flop 数（d_i はタイル i の行数・列数。最後のタイルは size − (N−1)·nb）
    DGEQRT 2·d_k³ − 2/3·d_k³ = 4/3·d_k³、DORMQR 2·d_k²·d_n、DTSQRT 2·d_m·d_k²、DTSMQR 4·d_m·d_n·d_k
- 模擬：空いたワーカーが、準備のできたタスクを「準備ができた時刻の早い順（同時ならタスクを作った順）」に取る（policy='fifo'）。
  policy='cp' はクリティカルパスの残りが長い順（感度）。release[i] を与えると、タスク i はその時刻より前には始まらない
  （主スレッドがタスクを1個ずつ作る (c) の確認用）
- モデル：G = p·A·E·η、η = 1/(1+(c√p·nb/size)^k)、c = √7.5、k = 2（3agg の common.predict をそのまま使う）
"""
from __future__ import annotations

import heapq
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]                       # tileQR_data
DATA = OUT / "data"
DATA.mkdir(exist_ok=True)
P = 192
SIZES = [1024, 2048, 4096, 8192]
AGGS = ["fast", "slow", "mean"]            # 速い水準／遅い水準だけ／5回の平均（3agg の a_curves.csv の列）
AGG_JA = {"fast": "速い水準", "slow": "遅い水準だけ", "mean": "5回の平均"}

AGG3 = ROOT / "analysis/2026-11-17_flow2-perf-ratio-3agg"
_spec = importlib.util.spec_from_file_location("agg3_common", AGG3 / "scripts/common.py")
agg3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agg3)
flops_dgeqrf = agg3.sw.flops_dgeqrf
predict = agg3.predict

GEQRT, ORMQR, TSQRT, TSMQR, COPYIN, COPYOUT = range(6)
KIND = ["DGEQRT", "DORMQR", "DTSQRT", "DTSMQR", "copy_in", "copy_out"]


def kernel_params() -> dict:
    return agg3.kernel_params()          # {"ib=nb/8": (A, beta), "MaxIB": (A, beta)}


def curves() -> pd.DataFrame:
    """3agg の集計済み曲線（size, nb, fast, slow, mean, ...）。GFlops、ib について最大。"""
    return pd.read_csv(AGG3 / "data/a_curves.csv")


def tile_dims(size: int, nb: int) -> list[int]:
    N = math.ceil(size / nb)
    return [nb] * (N - 1) + [size - (N - 1) * nb]


def build_dag(size: int, nb: int, war: bool = True, copies: bool = False):
    """タスクを作った順に (kind, flops, bytes, preds) を返す。"""
    d = tile_dims(size, nb)
    N = len(d)
    kind, flops, nbytes, preds = [], [], [], []
    last_w: dict = {}
    readers: dict = {}

    def task(k, f, b, acc):
        t = len(kind)
        pr = set()
        for key, mode in acc:
            w = last_w.get(key)
            if w is not None:
                pr.add(w)
            if mode == "in":
                readers.setdefault(key, []).append(t)
            else:
                if war:
                    pr.update(readers.get(key, ()))
                readers[key] = []
                last_w[key] = t
        kind.append(k); flops.append(f); nbytes.append(b); preds.append(sorted(pr))

    if copies:
        for m in range(N):
            for n in range(N):
                task(COPYIN, 0.0, 16.0 * d[m] * d[n], [(("A", m, n), "out")])
    for k in range(N):
        dk = d[k]
        task(GEQRT, 4 / 3 * dk**3, 0, [(("A", k, k), "inout"), (("T", k, k), "out")])
        for n in range(k + 1, N):
            task(ORMQR, 2.0 * dk * dk * d[n], 0,
                 [(("A", k, k), "in"), (("T", k, k), "in"), (("A", k, n), "inout")])
        for m in range(k + 1, N):
            task(TSQRT, 2.0 * d[m] * dk * dk, 0,
                 [(("A", k, k), "inout"), (("A", m, k), "inout"), (("T", m, k), "out")])
            for n in range(k + 1, N):
                task(TSMQR, 4.0 * d[m] * d[n] * dk, 0,
                     [(("A", k, n), "inout"), (("A", m, n), "inout"),
                      (("A", m, k), "in"), (("T", m, k), "in")])
    if copies:
        for m in range(N):
            for n in range(N):
                task(COPYOUT, 0.0, 16.0 * d[m] * d[n], [(("A", m, n), "in")])
    return np.array(kind), np.array(flops), np.array(nbytes), preds


def weights(flops, nbytes, nb, A, beta, copies_bw=None):
    E = nb / (nb + beta)
    w = flops / (A * 1e9 * E)
    if copies_bw:
        w = w + nbytes / copies_bw
    return w


def critical_path(w, preds) -> float:
    fin = np.zeros(len(w))
    for t, pr in enumerate(preds):          # 作った順は位相順
        fin[t] = w[t] + (max(fin[q] for q in pr) if pr else 0.0)
    return float(fin.max())


def bottom_level(w, preds) -> np.ndarray:
    bl = np.array(w, dtype=float)
    for t in range(len(w) - 1, -1, -1):
        for q in preds[t]:
            if bl[t] + w[q] > bl[q]:
                bl[q] = bl[t] + w[q]
    return bl


def simulate(w, preds, p=P, policy="fifo", release=None):
    """リストスケジューリング。start, finish の配列を返す。"""
    n = len(w)
    succ = [[] for _ in range(n)]
    indeg = np.zeros(n, dtype=np.int64)
    for t, pr in enumerate(preds):
        indeg[t] = len(pr)
        for q in pr:
            succ[q].append(t)
    rel = np.zeros(n) if release is None else np.asarray(release, float)
    prio = -bottom_level(w, preds) if policy == "cp" else None
    start = np.empty(n); finish = np.empty(n)
    ready, future, running = [], [], []

    def make_ready(t, rt):
        key = (rt, t) if prio is None else (prio[t], t)
        heapq.heappush(ready, key)

    for t in range(n):
        if indeg[t] == 0:
            if rel[t] <= 0:
                make_ready(t, 0.0)
            else:
                heapq.heappush(future, (rel[t], t))
    time, free, done = 0.0, p, 0
    while done < n:
        while free > 0 and ready:
            _, t = heapq.heappop(ready)
            start[t] = time
            finish[t] = time + w[t]
            heapq.heappush(running, (finish[t], t))
            free -= 1
        nxt = min(running[0][0] if running else math.inf, future[0][0] if future else math.inf)
        time = nxt
        while running and running[0][0] <= time:
            _, t = heapq.heappop(running)
            free += 1; done += 1
            for s in succ[t]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    if rel[s] <= time:
                        make_ready(s, time)
                    else:
                        heapq.heappush(future, (rel[s], s))
        while future and future[0][0] <= time:
            rt, t = heapq.heappop(future)
            make_ready(t, rt)
    return start, finish


def idle_profile(start, finish, w, p=P) -> dict:
    """ワーカーの空き（ワーカー・秒）を、初め／中／終わりに分ける。
    初め = 時刻 0 から、走っているタスクが初めて p 個になるまで。
    終わり = 走っているタスクが最後に p 個だった時刻から終わりまで。
    一度も p 個にならなければ、全部を「全体（一度も埋まらない）」とする。"""
    T = float(finish.max())
    ev_t = np.concatenate([start, finish])
    ev_d = np.concatenate([np.ones(len(start)), -np.ones(len(finish))])
    order = np.lexsort((ev_d, ev_t))           # 同時刻は終わり（−1）を先に
    ev_t, ev_d = ev_t[order], ev_d[order]
    busy = np.cumsum(ev_d)
    # 区間 [ev_t[i], ev_t[i+1]) で busy[i] 個が走る
    seg_len = np.diff(np.append(ev_t, T))
    idle = (p - busy) * seg_len
    full = np.where((busy >= p) & (seg_len > 0))[0]
    out = {"T_sim": T, "max_busy": int(busy.max()), "idle_total": float(idle.sum())}
    if len(full) == 0:
        out.update(idle_start=np.nan, idle_mid=np.nan, idle_end=np.nan, idle_never=float(idle.sum()),
                   t_full=np.nan, t_last=np.nan)
    else:
        i0, i1 = full[0], full[-1]
        out.update(idle_start=float(idle[:i0].sum()), idle_mid=float(idle[i0:i1 + 1].sum()),
                   idle_end=float(idle[i1 + 1:].sum()), idle_never=0.0,
                   t_full=float(ev_t[i0]), t_last=float(ev_t[i1] + seg_len[i1]))
    return out
