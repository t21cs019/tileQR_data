"""perf の内訳：計時区間の中の区分ごとのオンCPU の秒数（コア秒）と、p × Time に対する割合。
主：round 1（perf script の生の出力から、区間 ＝ ワーカー FORK の時刻から Time の長さに取り直したもの。data/b_r1_fixed/）
再現性：round 1〜5 の M1 区間（Time より 2〜8% 長い尻尾を含む）で、同じ割合を出して幅を見る。
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
from c_breakdown_lib import split, GROUPS

def main():
    fixed = perf_runs(DATA / "b_r1_fixed")
    allr = perf_runs()
    rows = []
    for r in sorted(fixed, key=lambda r: (r["p"], r["size"], r["nb"])):
        g, tot, wlen = split(r, "T")
        rows.append(dict(p=r["p"], size=r["size"], nb=r["nb"], tasks=ntasks(r["size"], r["nb"]), T=wlen, core_s=tot,
                         **{k: g[k] for k in GROUPS}))
    with open(DATA / "c_breakdown_sec_r1.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})
    print("コア秒（round 1、区間 ＝ Time）。割合は p × Time に対する %")
    print(f"{'p':>3} {'size':>5} {'nb':>4} {'T[s]':>7} " + " ".join(f"{k[:11]:>11}" for k in GROUPS))
    for r in rows:
        print(f"{r['p']:>3} {r['size']:>5} {r['nb']:>4} {r['T']:7.3f} " + " ".join(f"{100 * r[k] / r['core_s']:10.1f}%" for k in GROUPS))
    # 再現性：M1 区間の割合の幅（round 1〜5）
    print("\n再現性（M1 区間、round 1〜5 の min–max、% of p × M1_len）：blas_alloc / omp_task / kernel_unres")
    by = defaultdict(list)
    for r in allr:
        g, tot, _ = split(r, "M1")
        by[(r["p"], r["size"], r["nb"])].append({k: 100 * g[k] / tot for k in GROUPS})
    rep = []
    for key in sorted(by):
        v = by[key]
        line = [key[0], key[1], key[2], len(v)]
        for k in ("blas_alloc", "omp_task", "kernel_unres"):
            xs = [d[k] for d in v]
            line += [round(min(xs), 1), round(max(xs), 1)]
        rep.append(line)
        print(line)
    with open(DATA / "c_breakdown_repro.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["p", "size", "nb", "n", "alloc_min", "alloc_max", "omptask_min", "omptask_max", "kernel_min", "kernel_max"])
        w.writerows(rep)

    # 尻尾（M1 − Time）に何が入っているか：round 1 の M1 と M1T の差
    print("\n尻尾（round 1、M1 − M1T のコア秒）")
    m1 = {(r["p"], r["size"], r["nb"]): r for r in allr if r["round"] == 1}
    for r in sorted(fixed, key=lambda r: (r["p"], r["size"], r["nb"])):
        k = (r["p"], r["size"], r["nb"])
        gt, _, _ = split(r, "T")
        gm, _, _ = split(m1[k], "M1")
        d = {n: gm[n] - gt[n] for n in GROUPS if n != "offcpu"}
        big = sorted(d.items(), key=lambda x: -x[1])[:3]
        print(k, "尻尾", round(m1[k]["window"]["M1_len"] - m1[k]["window"]["time_sec"], 3), "s", [(n, round(v, 3)) for n, v in big])


main()
