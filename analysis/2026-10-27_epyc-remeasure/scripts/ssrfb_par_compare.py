"""EPYC 7543 size1024 の DTSMQR：既存の1コア計測、同時実行モジュールでの1本（p=1）、32本同時（p=32）を比べる。"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from tileqr_data import kurzak
D = Path(__file__).resolve().parents[1] / "data/ssrfb_par"
par = pd.read_csv(D / "epyc_ssrfb-par32_size1024_nb32-512_t1_20261026_234740.csv")
p1 = pd.read_csv(D / "epyc_ssrfb-par1_size1024_nb32-512_t1_20261027_020223.csv")
old = pd.read_csv(ROOT / "raw/ssrfb/epyc/epyc_size1024_t1_nb32-512_20260830-080819.csv")
print("p1 rows", len(p1), "missing", int((p1.Time_sec <= 0).sum()), "n_it range", p1.n_it.min(), p1.n_it.max())
g = lambda df: df.groupby(["nb","ib"], as_index=False).GFlops.mean()
m = g(old).rename(columns={"GFlops":"old"}).merge(g(p1).rename(columns={"GFlops":"p1"}), on=["nb","ib"]).merge(g(par).rename(columns={"GFlops":"p32"}), on=["nb","ib"])
for a,b in [("p1","old"),("p32","p1"),("p32","old")]:
    r = m[a]/m[b]
    print(f"{a}/{b}: median {r.median():.3f}  p5 {r.quantile(.05):.3f}  p95 {r.quantile(.95):.3f}")
print("\nsmall nb (<=64) p1/old median", (m.p1/m.old)[m.nb<=64].median(), " nb32ib8:", m[(m.nb==32)&(m.ib==8)][["old","p1","p32"]].values)
sl = lambda col: kurzak.ib_rule_slice(m.rename(columns={col:"GFlops"})[["nb","ib","GFlops"]])
t = sl("old")[["nb","ib","GFlops"]].rename(columns={"GFlops":"old"})
t["p1"] = sl("p1").GFlops.values; t["p32"] = sl("p32").GFlops.values
t["p1/old"]=t.p1/t.old; t["p32/p1"]=t.p32/t.p1
print("\nib=nb/8\n", t[t.nb.isin([32,48,64,96,128,192,256,320,384,448,512])].round(3).to_string(index=False))
for col in ["old","p1","p32"]:
    x = sl(col); x = x[x.nb>=64]
    A,beta = kurzak.fit_E(x.nb.to_numpy(float), x.GFlops.to_numpy(float))
    mre = np.mean(np.abs(A*x.nb/(x.nb+beta)/x.GFlops-1))
    print(f"beta[{col}] = {beta:.1f}  A={A:.2f}  MRE={mre*100:.1f}%")
# best per nb
for col in ["old","p1","p32"]:
    b = m.loc[m.groupby("nb")[col].idxmax()]
    print(col, "peak", round(m[col].max(),2), "at", m.loc[m[col].idxmax(),["nb","ib"]].tolist())
