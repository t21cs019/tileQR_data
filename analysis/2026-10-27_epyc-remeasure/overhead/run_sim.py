"""QR 実測時間と DAG シミュレーション（カーネル実測時間 + o, L）を比べる。結果を sim.csv に出す。"""
import math, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd
HERE = Path(__file__).parent
ROOT = HERE.resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tileqr_data import io

SIM = str(HERE / "sched_ovh")
O = [0, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6, 1e-3]
L = [0, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6, 1e-3, 2e-3]
SIZES = [1024, 2048, 4096]
# config, p, DTSMQR の出所（ssrfb のノード名 or ssrfb_par の CSV）
PAR = {
    "par32": HERE.parent / "data/ssrfb_par/epyc_ssrfb-par32_size1024_nb32-512_t1_20261026_234740.csv",
    "par1": HERE.parent / "data/ssrfb_par/epyc_ssrfb-par1_size1024_nb32-512_t1_20261027_020223.csv",
}
TARGETS = [
    ("epyc_s1_smt-off", 32, "par32"),
    ("epyc_s1_smt-off", 32, "par1"),
    ("epyc_s1_smt-off", 32, "epyc"),
    ("aoba-b_s1_smt-off", 64, "par043"),
    ("i5-8500_s1_smt-off", 6, "i5-8500"),
    ("i3-10100_s1_smt-off", 4, "i3-10100"),
]

def kernel_table(src):
    if src in PAR:
        d = pd.read_csv(PAR[src])
        return d.groupby(["nb", "ib"]).Time_sec.mean()
    s = io.load_ssrfb()
    s = s[(s.node == src) & (s["size"] == 1024)]
    return s.groupby(["nb", "ib"]).Time_sec.mean()

def one(args):
    key, N, e, p, t = args
    f = lambda x: f"{float(x):.9g}"
    cmd = [SIM, str(N), f(e), str(p), f(t * 4 / 12), f(t * 6 / 12), f(t * 6 / 12), f(t),
           str(len(O)), *map(f, O), str(len(L)), *map(f, L)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.split("\n")
    return [(*key, float(a), float(b), float(c)) for a, b, c in (l.split() for l in out if l)]

def main():
    sw = io.load_sweeps()
    jobs = []
    meas = []
    for cfg, p, src in TARGETS:
        kt = kernel_table(src)
        q = sw[(sw.config == cfg) & sw["size"].isin(SIZES)]
        q = q.groupby(["size", "nb", "ib"], as_index=False).GFlops.mean()
        best = q.loc[q.groupby(["size", "nb"]).GFlops.idxmax()]
        for r in best.itertuples():
            if r.nb % 8 or (r.nb, r.ib) not in kt.index:
                continue
            N = math.ceil(r.size / r.nb)
            e = (r.size - (N - 1) * r.nb) / r.nb
            t_meas = (4 / 3) * r.size ** 3 / (r.GFlops * 1e9)
            meas.append(dict(config=cfg, src=src, p=p, size=r.size, nb=r.nb, ib=r.ib, N=N,
                             G=r.GFlops, t_meas=t_meas, t_tsmqr=kt[(r.nb, r.ib)]))
            jobs.append(((cfg, src, r.size, r.nb), N, e, p, kt[(r.nb, r.ib)]))
    jobs.sort(key=lambda j: -j[1])   # 大きい N から
    with ProcessPoolExecutor(4) as ex:
        rows = [x for res in ex.map(one, jobs) for x in res]
    sim = pd.DataFrame(rows, columns=["config", "src", "size", "nb", "o", "L", "t_sim"])
    out = sim.merge(pd.DataFrame(meas), on=["config", "src", "size", "nb"])
    out.to_csv(HERE / "sim.csv", index=False)
    print(len(out), "行")

if __name__ == "__main__":
    main()
