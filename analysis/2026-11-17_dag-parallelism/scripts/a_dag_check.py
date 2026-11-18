"""
a：DAG の形の確認。タイル数 N ごとに、タスク数（種類別）、クリティカルパスの長さ（単位 nb³/3 flop、
WAR の依存あり／なし）を出し、STATUS の D = 30N − 28 と比べる。さらに、
p = 192 で「準備のできたタスク数」が p に届くか（重みを単位にした模擬での最大同時実行数）を出す。
出力：data/a_dag_shape.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

rows = []
for N in [2, 3, 4, 5, 6, 8, 10, 12, 16, 21, 24, 32, 48, 64, 128]:
    nb = 64
    kind, fl, by, pr = build_dag(N * nb, nb, war=True)
    unit = fl / (nb**3 / 3)
    cp_war = critical_path(unit, pr)
    _, _, _, pr0 = build_dag(N * nb, nb, war=False)
    cp_nowar = critical_path(unit, pr0)
    st, fi = simulate(unit, pr, p=P)
    ip = idle_profile(st, fi, unit)
    rows.append(dict(N=N, tasks=len(kind),
                     **{f"n_{KIND[i]}": int((kind == i).sum()) for i in range(4)},
                     W_units=unit.sum(), W_formula_4N3=4 * N**3,
                     CP_war=cp_war, CP_nowar=cp_nowar, D_status=30 * N - 28,
                     max_busy_p192=ip["max_busy"]))
df = pd.DataFrame(rows)
df.to_csv(DATA / "a_dag_shape.csv", index=False)
print(df.to_string(index=False))
