"""runs.csv（plain・ref・perf の時間と page-faults）と strace -c の集計。"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

R = read_runs(D_PERF)
by = defaultdict(list)
for r in R:
    by[(r["kind"], r["threads"], r["size"], r["nb"])].append(r)
conds = sorted({(k[1], k[2], k[3]) for k in by})
out = []
print("p size nb | plain[s] (min-max) | perf/plain | ref/plain | minflt(plain) | A+tile 想定 2·size²·8/4096 | stime[s] | 他ユーザーCPU最大")
for c in conds:
    pl = [r["Time_sec"] for r in by[("plain",) + c]]
    pf = [r["Time_sec"] for r in by[("perf",) + c]]
    rf = [r["Time_sec"] for r in by.get(("ref",) + c, [])]
    flt = median([r["minflt"] for r in by[("plain",) + c]])
    stm = median([r["stime"] for r in by[("plain",) + c]])
    oc = max(r["other_cpu_before"] for k, v in by.items() if k[1:] == c for r in v)
    exp = 2 * c[1] ** 2 * 8 / 4096
    row = dict(p=c[0], size=c[1], nb=c[2], plain_med=median(pl), plain_min=min(pl), plain_max=max(pl), perf_over_plain=median(pf) / median(pl),
               ref_over_plain=(median(rf) / median(pl)) if rf else "", minflt=flt, pages_2x=exp, stime=stm, other_cpu_max=oc)
    out.append(row)
    print(f"{c[0]:>2} {c[1]:>5} {c[2]:>3} | {row['plain_med']:.4f} ({row['plain_min']:.4f}-{row['plain_max']:.4f}) | {row['perf_over_plain']:.3f} | "
          f"{row['ref_over_plain'] if rf == [] else round(row['ref_over_plain'], 3)} | {flt:.0f} | {exp:.0f} | {stm:.2f} | {oc:.0f}%")
with open(DATA / "a_runs_summary.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    for r in out:
        w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})

print("\n--- strace -f -c（round ごとの中央値。回数。秒は strace の -c（システム時間））")
S = defaultdict(lambda: defaultdict(list))
SS = defaultdict(lambda: defaultdict(list))
for fn in sorted((D_STR / "raw").glob("strace_*.strace.txt")):
    m = re.match(r"strace_p(\d+)_s(\d+)_nb(\d+)_r(\d+)", fn.name)
    p, size, nb, rnd = map(int, m.groups())
    seen = {}
    for line in open(fn):
        t = line.split()
        if len(t) >= 5 and re.match(r"[\d.]+$", t[0]) and t[-1].isalpha() or (len(t) >= 5 and re.match(r"[\d.]+$", t[0]) and re.match(r"\w+$", t[-1])):
            try:
                calls = int(t[3]); secs = float(t[1]); seen[t[-1]] = (calls, secs)
            except ValueError:
                pass
    for sc, (calls, secs) in seen.items():
        S[(p, size, nb)][sc].append(calls); SS[(p, size, nb)][sc].append(secs)
WANT = ["futex", "mmap", "munmap", "madvise", "brk", "clone", "clone3", "sched_yield", "mprotect", "openat", "read", "write"]
rows = []
for key in sorted(S):
    line = {"p": key[0], "size": key[1], "nb": key[2]}
    for sc in WANT:
        line[sc + "_calls"] = median(S[key].get(sc, [0]))
        line[sc + "_sec"] = median(SS[key].get(sc, [0.0]))
    rows.append(line)
print("p size nb | " + " ".join(f"{s}" for s in WANT))
for r in rows:
    print(f"{r['p']:>2} {r['size']:>5} {r['nb']:>3} | " + " ".join(f"{int(r[s + '_calls'])}" for s in WANT))
print("（秒）")
for r in rows:
    print(f"{r['p']:>2} {r['size']:>5} {r['nb']:>3} | " + " ".join(f"{r[s + '_sec']:.3f}" for s in WANT))
if rows:
    with open(DATA / "a_strace_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
