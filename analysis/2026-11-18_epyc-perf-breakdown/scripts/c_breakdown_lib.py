"""（c_breakdown.py と共通）perf の内訳：計時区間の中の区分ごとのオンCPU の秒数（コア秒）と、p × Time に対する割合。
主：round 1（perf script の生の出力から、区間 ＝ ワーカー FORK の時刻から Time の長さに取り直したもの。data/b_r1_fixed/）
再現性：round 1〜5 の M1 区間（Time より 2〜8% 長い尻尾を含む）で、同じ割合を出して幅を見る。
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

GROUPS = ["blas_alloc", "blas_compute", "core_blas", "omp_task", "omp_other", "omp_wait", "plasma", "libc", "kernel_unres", "other_user", "offcpu"]


def split(r, use_window_len):
    """区分ごとのコア秒。blas の alloc/free と、dso が [unknown]（カーネル・解決できなかったもの）は top から取る"""
    f = r["freq"]
    c = {k: (v[0] + v[1]) / f for k, v in r["cats"].items()}
    alloc = sum(n for cat, d, s, n in r["top"] if cat == "blas" and s in ("blas_memory_alloc", "blas_memory_free")) / f
    unk = sum(n for cat, d, s, n in r["top"] if d == "[unknown]") / f
    g = dict.fromkeys(GROUPS, 0.0)
    g["blas_alloc"] = alloc
    g["blas_compute"] = c.get("blas", 0) - alloc
    g["core_blas"] = c.get("core_blas", 0) + c.get("core_dlacpy", 0)
    g["omp_task"] = c.get("omp_task", 0)
    g["omp_other"] = c.get("omp_other", 0)
    g["omp_wait"] = c.get("omp_wait", 0)
    g["plasma"] = c.get("plasma_other", 0) + c.get("workspace_create", 0) + c.get("dlacpy_task", 0)
    g["libc"] = c.get("libc_malloc", 0) + c.get("libc_mem", 0) + c.get("libc_other", 0)
    g["kernel_unres"] = unk
    g["other_user"] = c.get("other_user", 0) - unk + c.get("plasmatest", 0) + c.get("lapack_init", 0)
    wlen = r["window"]["time_sec"] if use_window_len == "T" else r["window"]["M1_len"]
    tot = r["p"] * wlen
    g["offcpu"] = tot - sum(g[k] for k in GROUPS if k != "offcpu")
    return g, tot, wlen




def table():
    rows = []
    for r in sorted(perf_runs(DATA / "b_r1_fixed"), key=lambda r: (r["p"], r["size"], r["nb"])):
        g, tot, wlen = split(r, "T")
        rows.append(dict(p=r["p"], size=r["size"], nb=r["nb"], tasks=ntasks(r["size"], r["nb"]), T=wlen, core_s=tot, **{k: g[k] for k in GROUPS}))
    return rows
