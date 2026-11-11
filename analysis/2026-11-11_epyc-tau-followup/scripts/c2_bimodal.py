"""計測 C2 と C1（中身 0）：libgomp・p = 32 の τ がプロセスごとにどちらの値か。"""
import sys
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import C1_CSV, C2_CSV, OUT

c2 = pd.read_csv(C2_CSV); c2["src"] = "C2"
c1 = pd.read_csv(C1_CSV); c1["src"] = "C1"
c1 = c1[(c1.runtime == "libgomp") & (c1.threads == 32) & (c1.work_ns == 0)]
d = pd.concat([c2, c1])
w = d.pivot_table(index=["src", "tiles", "process"], columns="iter", values="tau_us").reset_index()
w.columns = ["src", "tiles", "process", "it1", "it2", "it3"]
w["spread"] = w[["it1", "it2", "it3"]].max(axis=1) - w[["it1", "it2", "it3"]].min(axis=1)
w["med"] = w[["it1", "it2", "it3"]].median(axis=1)
w["mode"] = pd.cut(w.med, [0, 4.2, 5.2, 5.95, 99], labels=["3.8-3.9", "4.5", "5.7-5.8", "6.0-6.2"])
w.to_csv(OUT / "c2_gomp_p32_by_process.csv", index=False, float_format="%.4f")
print("全プロセスの med（昇順）, C2:", " ".join(f"{v:.2f}" for v in sorted(w[w.src == "C2"].med)))
print("C1 tiles 64 :", " ".join(f"{v:.2f}" for v in sorted(w[(w.src == "C1") & (w.tiles == 64)].med)))
print("C1 tiles 128:", " ".join(f"{v:.2f}" for v in sorted(w[(w.src == "C1") & (w.tiles == 128)].med)))
print(w.groupby(["src", "tiles", "mode"], observed=True).agg(n=("med", "size"), lo=("med", "min"), hi=("med", "max"), max_spread=("spread", "max")).to_string(float_format=lambda v: f"{v:.2f}"))
print("同じプロセスの3回の幅の最大:", f"{w.spread.max():.3f}", " 0.1 を超えるプロセス数:", int((w.spread > 0.1).sum()), "/", len(w))
print("C2 の実行順:", " ".join(f"{v:.1f}" for v in w[w.src == "C2"].sort_values("process").med))
