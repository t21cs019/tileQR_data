#!/usr/bin/env python3
"""perf script の出力（標準入力）を、QR の計時区間の中の区分けに集計する。標準ライブラリだけ（EPYC で動く）。

入力：perf script --show-task-events -F comm,tid,time,ip,sym,dso
出力（--out <prefix>）：
  <prefix>_window.json   計時区間の推定（2通り）と、plasmatest が出した Time
  <prefix>_cat.csv       区分ごとの試料数（主スレッド・ワーカー別。区間の中／外）
  <prefix>_catbin.csv    区間を20等分した時間ごとの、区分ごとの試料数
  <prefix>_top.csv       区間の中の (dso, sym) の上位80（区分の分け方を直すため）

試料は cpu-clock（時間で一定）なので、試料数 / freq = オンCPU の秒数。眠っているスレッドは試料に出ない。
区間の推定：
  M1 = ワーカーの FORK が P-1 本そろった時刻 〜 最初のワーカーの EXIT（plasma_workspace_create から plasma_finalize まで。
       区間の終わりは計時の終わり（stop）より少し後になる）
  M2 = 主スレッドの試料のうち、libplasma の中で最初のものの時刻 〜 最後のもの
どちらが Time に合うかは解析側で決める（ここでは選ばず、両方を出す）。
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--threads", type=int, required=True)
ap.add_argument("--time", type=float, default=0.0)
ap.add_argument("--freq", type=int, required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--window", choices=["M1", "M2"], default="M1", help="cat.csv に使う区間")
a = ap.parse_args()

EV = re.compile(r"(\d+\.\d+):\s+PERF_RECORD_(FORK|EXIT)\((\d+):(\d+)\):\((\d+):(\d+)\)")
SMP = re.compile(r"^\s*(.+?)\s+(?:\d+/)?(\d+)\s+(\d+\.\d+):\s+([0-9a-fA-F]+)\s+(.*?)\s+\((.*)\)\s*$")

forks, exits, samples = [], {}, []   # forks=[(t, pid, tid)], exits={tid: t}
for line in sys.stdin:
    m = EV.search(line)
    if m:
        t, kind, pid, tid = float(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        if kind == "FORK":
            forks.append((t, pid, tid))
        elif tid != pid:
            exits.setdefault(tid, t)
        continue
    m = SMP.match(line)
    if m:
        samples.append((float(m.group(3)), int(m.group(2)), m.group(5).strip(), m.group(6)))

if not samples:
    raise SystemExit("[reduce_perf] 試料が 0 個")

# 主スレッド = FORK したスレッドの親。FORK が無ければ最初の試料のスレッド
main_tid = None
thr_forks = sorted((t, tid) for t, pid, tid in forks if tid != pid)
if thr_forks:
    # 親の pid（= 主スレッドの tid）：FORK イベントの pid のうち最も多いもの
    cnt = collections.Counter(pid for _, pid, tid in forks if tid != pid)
    main_tid = cnt.most_common(1)[0][0]
else:
    main_tid = samples[0][1]
t0 = min(s[0] for s in samples)

# --- 区分け ------------------------------------------------------------------
KERNEL_RULES = [
    ("k_pagefault", r"page_fault|handle_mm_fault|do_anonymous|clear_page|clear_huge|clear_user|alloc_pages|get_page_from_freelist|"
                    r"do_user_addr_fault|do_fault|handle_pte|__pte_alloc|__pmd_alloc|lru_cache|memcg|mem_cgroup|charge|rmqueue|"
                    r"pte_|pmd_|folio_add|page_add|do_huge|thp|khugepaged|__handle_mm"),
    ("k_munmap",    r"unmap|zap_|free_pages|free_unref|release_pages|exit_mmap|tlb_|flush_tlb|native_flush|smp_call_function|"
                    r"on_each_cpu|flush_smp_call|__vm_munmap|vm_unmapped|remove_vma|free_pgtables|put_page|folio_put|free_swap"),
    ("k_mmap",      r"mmap|get_unmapped|vma_|mprotect|\bbrk\b|__x64_sys_brk|madvise|mlock|vm_area|anon_vma"),
    ("k_futex",     r"futex|wake_up|try_to_wake|__schedule|\bschedule|__switch_to|finish_task|pick_next|sched_|ttwu|enqueue|dequeue|"
                    r"idle|hrtimer|nanosleep|sched_yield"),
    ("k_clone",     r"clone|copy_process|wake_up_new_task|kernel_clone|dup_task|copy_mm|copy_thread|alloc_thread|cgroup_"),
    ("k_syscall",   r"entry_SYSCALL|do_syscall|syscall_exit|syscall_enter|x64_sys|sysret|entry_SYSRET"),
]


def categorize(sym, dso):
    base = os.path.basename(dso)
    if dso.startswith("[kernel") or dso == "[unknown]" and sym.startswith("[k]"):
        for name, rx in KERNEL_RULES:
            if re.search(rx, sym):
                return name
        return "k_other"
    if base.startswith("libiomp5") or base.startswith("libgomp"):
        if re.search(r"task|steal|execute|alloc|queue|deque|dep_|hash|bootstrap|taskdata", sym, re.I):
            return "omp_task"
        if re.search(r"wait|yield|spin|barrier|sleep|suspend|pause|monitor|relax|flag", sym, re.I):
            return "omp_wait"
        return "omp_other"
    if base.startswith("libopenblas") or base.startswith("libmkl") or "blas" in base and "plasma" not in base:
        return "blas"
    if base.startswith("libplasma_core_blas"):
        if re.search(r"lacpy|laset|dlacpy", sym, re.I):
            return "core_dlacpy"
        return "core_blas"
    if base.startswith("libplasma."):
        if re.search(r"workspace", sym, re.I):
            return "workspace_create"
        if re.search(r"dge2desc|desc2ge|ge2desc|pdge2|pdtr2|2desc|desc2", sym, re.I):
            return "dlacpy_task"
        return "plasma_other"
    if re.search(r"^libc\.|^libc-|libpthread|ld-linux|ld\.so", base):
        if re.search(r"malloc|free|calloc|realloc|arena|brk|sysmalloc|_int_|mmap|munmap|madvise|trim", sym):
            return "libc_malloc"
        if re.search(r"memcpy|memset|memmove|bzero|erms|avx", sym):
            return "libc_mem"
        return "libc_other"
    if base in ("plasmatest",) or "plasmatest" in base:
        return "plasmatest"
    if base.startswith("libgfortran") or base.startswith("liblapack") or "lapacke" in base.lower():
        return "lapack_init"
    return "other_user"


# --- 区間 --------------------------------------------------------------------
P = a.threads
win = {"M1": None, "M2": None, "time_sec": a.time, "main_tid": main_tid, "n_forks": len(thr_forks), "n_samples": len(samples), "t0": t0}
if P >= 2 and len(thr_forks) >= P - 1:
    ft = [t for t, _ in thr_forks]
    k = P - 1
    start = None
    for i in range(len(ft) - k + 1):
        if ft[i + k - 1] - ft[i] < 0.5:
            start = i
            break
    if start is not None:
        workers = {tid for _, tid in thr_forks[start:start + k]}
        ws = ft[start]
        ex = [exits[tid] for tid in workers if tid in exits]
        we = min(ex) if ex else None
        win["M1"] = [ws, we]
# M2
mp = [s[0] for s in samples if s[1] == main_tid and os.path.basename(s[3]).startswith("libplasma.")]
if mp:
    win["M2"] = [min(mp), max(mp)]
for m in ("M1", "M2"):
    w = win[m]
    win[m + "_len"] = (w[1] - w[0]) if w and w[0] is not None and w[1] is not None else None

use = win[a.window]
if not use or use[1] is None:
    use = win["M2"] or [t0, max(s[0] for s in samples)]
    win["used"] = "M2(fallback)" if win["M2"] else "all"
else:
    win["used"] = a.window
ws, we = use
win["used_range"] = [ws, we]

cat_rows = collections.defaultdict(lambda: [0, 0, 0, 0])   # cat -> [main_in, worker_in, main_out, worker_out]
nbin = 20
binw = max((we - ws) / nbin, 1e-9)
catbin = collections.defaultdict(lambda: [0] * nbin)
top = collections.Counter()
for t, tid, sym, dso in samples:
    c = categorize(sym, dso)
    is_main = tid == main_tid
    inside = ws <= t <= we
    cat_rows[c][(0 if is_main else 1) + (0 if inside else 2)] += 1
    if inside:
        b = min(int((t - ws) / binw), nbin - 1)
        catbin[c][b] += 1
        top[(c, os.path.basename(dso), sym)] += 1

with open(a.out + "_window.json", "w") as f:
    json.dump(win, f, indent=1)
with open(a.out + "_cat.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cat", "main_in", "worker_in", "main_out", "worker_out", "freq", "window_used"])
    for c, v in sorted(cat_rows.items()):
        w.writerow([c, *v, a.freq, win["used"]])
with open(a.out + "_catbin.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cat"] + [f"bin{i}" for i in range(nbin)] + ["bin_width_sec", "freq"])
    for c, v in sorted(catbin.items()):
        w.writerow([c, *v, f"{binw:.6f}", a.freq])
with open(a.out + "_top.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cat", "dso", "sym", "samples"])
    for (c, d, s), n in top.most_common(80):
        w.writerow([c, d, s, n])
print(f"[reduce_perf] {os.path.basename(a.out)} window={win['used']} len={we - ws:.4f}s "
      f"M1_len={win['M1_len']} M2_len={win['M2_len']} Time={a.time} samples={len(samples)}")
