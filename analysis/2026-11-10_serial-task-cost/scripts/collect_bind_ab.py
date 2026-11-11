"""
スレッド固定の A/B テスト（不老・弐、AOBA-B、研究室の EPYC 7543）の全点を1つの表にまとめる。

元のファイルはまだ tileQR_data に入っていない（~/Download にある）。場所は環境変数 BIND_AB_SRC で変えられる。
  flow/flow_bind-ab_20261031_082853/bind-<条件>_size<size>.csv   不老・弐（EPYC 9965、p = 192）
  aoba/flow_bind-ab_20261101_163609/bind-<条件>_size<size>.csv   AOBA-B（EPYC 7702、p = 64）
  ab_epyc7543.log                                                研究室（EPYC 7543、p = 32）。結果のディレクトリは研究室の機械にある

出力: data/bind_ab_points.csv（machine, p, cond, size, nb, ib, rep, GFlops）
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

SRC = Path(os.environ.get("BIND_AB_SRC", Path.home() / "Download"))
DATA = Path(__file__).resolve().parents[1] / "data"
DIRS = {"flow": (192, "flow/flow_bind-ab_20261031_082853"), "aoba": (64, "aoba/flow_bind-ab_20261101_163609")}
LINE = re.compile(r"rep\s+(\d+)\s+size\s+(\d+)\s+nb\s+(\d+)\s+bind-(\S+)\s+([\d.]+)\r? GFlops")  # ログの数値のあとに CR が入っている


def main():
    rows = []
    for machine, (p, d) in DIRS.items():
        for f in sorted((SRC / d).glob("bind-*_size*.csv")):
            cond = re.match(r"bind-(.*)_size", f.name).group(1)
            t = pd.read_csv(f)
            t["rep"] = t.groupby(["size", "nb"]).cumcount() + 1
            for r in t.itertuples():
                rows.append(dict(machine=machine, p=p, cond=cond, size=r.size, nb=r.nb, ib=r.ib, rep=r.rep, GFlops=r.GFlops))
    for line in (SRC / "ab_epyc7543.log").read_bytes().decode().split("\n"):  # read_text() や splitlines() は CR でも行を切る
        m = LINE.match(line)
        if m:
            rows.append(dict(machine="epyc", p=32, cond=m.group(4), size=int(m.group(2)), nb=int(m.group(3)), ib=32,
                             rep=int(m.group(1)), GFlops=float(m.group(5))))
    out = pd.DataFrame(rows).sort_values(["machine", "size", "nb", "cond", "rep"])
    out.to_csv(DATA / "bind_ab_points.csv", index=False)
    print(out.groupby(["machine", "cond"]).size().unstack())


if __name__ == "__main__":
    main()
