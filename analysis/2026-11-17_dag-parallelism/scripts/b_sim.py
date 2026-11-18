"""
b：p = 192 のリストスケジューリングの模擬（方法 (b)）。不老・弐のスイープの格子の全 nb
（size 1024〜4096 は nb 32〜512 の 4 刻み、8192 は nb 64〜512 の 8 刻み。8192 の nb < 64 はタスクが 100 万個を超えるので外した）。
重みはすべて flop/(A·E) なので、模擬は単位 nb³/3 flop で1回行い、A・β ごとに (nb³/3)/(A·E) 倍する（順番は変わらない）。
policy は fifo（準備のできた順。主）と cp（クリティカルパスの残りが長い順。感度）。
出力：data/b_sim_units.csv（単位での T_sim、空きの内訳、最大同時実行数）
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

C = curves()
rows = []
for size in SIZES:
    nbs = sorted(C.loc[C["size"] == size, "nb"].unique())
    if size == 8192:
        nbs = [nb for nb in nbs if nb >= 64]
    for nb in nbs:
        t0 = time.time()
        kind, fl, by, pr = build_dag(size, nb)
        unit = fl / (nb**3 / 3)
        base = dict(size=size, nb=nb, N=len(tile_dims(size, nb)), tasks=len(kind),
                    W_units=unit.sum(), CP_units=critical_path(unit, pr))
        for policy in ["fifo", "cp"]:
            st, fi = simulate(unit, pr, p=P, policy=policy)
            ip = idle_profile(st, fi, unit)
            rows.append({**base, "policy": policy, **ip})
        print(size, nb, len(kind), f"{time.time()-t0:.1f}s", flush=True)
df = pd.DataFrame(rows)
df.to_csv(DATA / "b_sim_units.csv", index=False)
