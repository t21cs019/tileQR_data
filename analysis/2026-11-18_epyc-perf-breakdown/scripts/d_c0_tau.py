"""c0 側（nb によらない）と τ 側（タスク数に比例）への分け。
区分 X のコア秒 C_X(size, nb, p) が C_X = c0_X + τ_X · タスク数 と書けると仮定し、同じ size・p の nb = 32 と 192 の2点から解く。
  τ_X = (C32 − C192) / (N32 − N192)   c0_X = C192 − τ_X · N192
これは「2点を通る直線」であって、当てはまりの確認ではない。計算の区分（blas_compute・core_blas）は nb で効率が変わる（E_カーネル）ので、
c0・τ の解釈に使わない（表には出すが、"計算" として別扱い）。単位は「壁の時間の相当」＝ コア秒 / p。
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
import c_breakdown_lib as cb

OVER = ["blas_alloc", "omp_task", "omp_other", "omp_wait", "plasma", "libc", "kernel_unres", "other_user", "offcpu"]
COMP = ["blas_compute", "core_blas"]
rows = cb.table()
idx = {(r["p"], r["size"], r["nb"]): r for r in rows}
out = []
print("壁の時間相当 [ms]（コア秒/p × 1000）。τ は µs/タスク（壁の相当）")
for p in (32, 8):
    for size in (4096, 8192):
        a, b = idx[(p, size, 32)], idx[(p, size, 192)]
        n32, n192 = a["tasks"], b["tasks"]
        tot32, tot192 = a["T"], b["T"]
        tau_all = (tot32 - tot192) / (n32 - n192) * 1e6
        line = {"p": p, "size": size, "N32": n32, "N192": n192, "T32_ms": tot32 * 1e3, "T192_ms": tot192 * 1e3, "tau_total_us": tau_all}
        for k in OVER + COMP:
            c32, c192 = a[k] / p, b[k] / p
            tau = (c32 - c192) / (n32 - n192)
            c0 = c192 - tau * n192
            line[k + "_c0_ms"] = c0 * 1e3
            line[k + "_tau_us"] = tau * 1e6
            line[k + "_at192_ms"] = c192 * 1e3
        out.append(line)
        print(f"\np={p} size={size}: T(nb32)={tot32 * 1e3:.0f} ms T(nb192)={tot192 * 1e3:.0f} ms  τ全体={tau_all:.2f} µs（(T32−T192)/(N32−N192)）")
        print(f"  {'区分':14} {'nb192での値[ms]':>14} {'c0側[ms]':>10} {'τ[µs/タスク]':>12}")
        for k in OVER + COMP:
            print(f"  {k:14} {line[k + '_at192_ms']:14.1f} {line[k + '_c0_ms']:10.1f} {line[k + '_tau_us']:12.3f}")
        so = sum(line[k + "_tau_us"] for k in OVER)
        print(f"  overhead区分の τ の合計 = {so:.2f} µs、そのうち blas_alloc = {line['blas_alloc_tau_us']:.2f} µs")
with open(DATA / "d_c0_tau.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    for r in out:
        w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

print("\nc0 側の size 依存（p 一定、nb192 の値。size²なら 4096→8192 で 4.0 倍）")
for p in (32, 8):
    a, b = idx[(p, 4096, 192)], idx[(p, 8192, 192)]
    print(f" p={p}: T {b['T'] / a['T']:.2f}倍（計算は 8.0 倍）, " + ", ".join(f"{k} {b[k] / a[k]:.1f}倍" for k in ("kernel_unres", "libc", "plasma", "omp_task", "blas_alloc", "offcpu")))
print("\n起動だけ（size 512, nb 32）の壁の時間相当 [ms] と、その T")
for p in (32, 8):
    r = idx[(p, 512, 32)]
    print(f" p={p}: T={r['T'] * 1e3:.1f} ms; " + ", ".join(f"{k} {r[k] / p * 1e3:.2f}" for k in OVER))
