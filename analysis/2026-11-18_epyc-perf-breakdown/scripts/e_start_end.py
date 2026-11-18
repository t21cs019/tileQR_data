"""区間を20等分した時間ビン（b_r1_fixed）で、起動直後・終わりの偏りを見る。
 kernel_unres（dso が [unknown] の試料）の最初の2ビンの割合、omp_wait+omp_task の最初・最後の2ビンの割合。"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

rows = []
for wj in sorted((DATA / "b_r1_fixed").glob("*_window.json")):
    tag = wj.name[:-12]
    p, size, nb = map(int, re.match(r"perf_p(\d+)_s(\d+)_nb(\d+)_r1", tag).groups())
    T = json.load(open(wj))["time_sec"]
    # kernel_unres は cat 単位では取れない（other_user に混ざる）ので、catbin の other_user を使う（他は 1% 未満）
    cb = {}
    for r in csv.DictReader(open(DATA / "b_r1_fixed" / f"{tag}_catbin.csv")):
        cb[r["cat"]] = [int(r[f"bin{i}"]) for i in range(20)]
        freq = int(r["freq"])
    ou = cb.get("other_user", [0] * 20)
    w = [a + b for a, b in zip(cb.get("omp_wait", [0] * 20), cb.get("omp_task", [0] * 20))]
    allb = [sum(v[i] for v in cb.values()) for i in range(20)]
    tot_ou, tot_w = sum(ou), sum(w)
    rows.append(dict(p=p, size=size, nb=nb, T_ms=T * 1e3, bin_ms=T * 1e3 / 20,
                     ou_first2_pct=100 * sum(ou[:2]) / max(tot_ou, 1), ou_core_ms=tot_ou / freq * 1e3 / p,
                     ou_first_bin_ms_wall_eq=ou[0] / freq * 1e3 / p,
                     w_first2_pct=100 * sum(w[:2]) / max(tot_w, 1), w_last2_pct=100 * sum(w[-2:]) / max(tot_w, 1),
                     w_core_ms=tot_w / freq * 1e3 / p,
                     cpu_first_bin_pct=100 * allb[0] / (p * T / 20 * freq), cpu_last_bin_pct=100 * allb[-1] / (p * T / 20 * freq)))
with open(DATA / "e_start_end.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
print("p size nb | T[ms] | カーネル(unknown)壁相当[ms] 最初の2ビンに占める% | omp_wait+omp_task 壁相当[ms] 最初2/最後2ビン% | CPU使用率 最初/最後のビン")
for r in sorted(rows, key=lambda r: (r["p"], r["size"], r["nb"])):
    print(f"{r['p']:>2} {r['size']:>5} {r['nb']:>3} | {r['T_ms']:8.1f} | {r['ou_core_ms']:6.1f} {r['ou_first2_pct']:5.0f}% | {r['w_core_ms']:6.1f} {r['w_first2_pct']:4.0f}% {r['w_last2_pct']:4.0f}% | {r['cpu_first_bin_pct']:4.0f}% {r['cpu_last_bin_pct']:4.0f}%")
